"""
Estrategia 1: SNIPING DE NOVOS TOKENS (PUMP.FUN)
==================================================
Detecta e compra tokens no momento exato do lancamento no Pump.fun,
antes que aparecam para usuarios comuns (vantagem de 0.01s vs 60s).

Risco: ALTO | Retorno: MUITO ALTO
Tempo de operacao: Ultra-rapido (segundos)
Ferramentas: Solana Sniper Bot, MEV Bots
Ideal para: Traders agressivos com capital para testar multiplos lancamentos
"""

import asyncio
import logging
import time
import random
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Optional

logger = logging.getLogger("StrategySniping")

BR_TZ = timezone(timedelta(hours=-3))


@dataclass
class SnipeTarget:
    token_address: str
    token_name: str
    detected_at: float
    buy_price: float = 0.0
    current_price: float = 0.0
    status: str = "detected"  # detected, bought, sold, failed, rugged
    pnl_pct: float = 0.0
    liquidity_sol: float = 0.0
    holders: int = 0
    buy_tx: str = ""
    sell_tx: str = ""


class SnipingStrategy:
    """
    Estrategia de Sniping em novos tokens Pump.fun.

    Modo TESTE (simulacao):
    - Monitora novos tokens via API publica
    - Simula compra instantanea no preco de lancamento
    - Rastreia evolucao do preco
    - Calcula PnL virtual se tivesse comprado
    - Capital ficticio de $100 para day trade
    """

    NAME = "Sniping Pump.fun"
    RISK_LEVEL = "ALTO"
    RETURN_LEVEL = "MUITO ALTO"
    TIME_FRAME = "Segundos"
    DESCRIPTION = (
        "Detecta e compra tokens no momento exato do lancamento no Pump.fun, "
        "antes que aparecam para usuarios comuns. Vantagem de milissegundos."
    )
    TOOLS = ["Solana Sniper Bot", "MEV Bots", "Pump.fun API"]

    INITIAL_CAPITAL = 100.0

    def __init__(self):
        self.targets: List[SnipeTarget] = []
        self.capital = self.INITIAL_CAPITAL
        self.total_invested = 0.0
        self.total_gains = 0.0
        self.total_losses = 0.0
        self.daily_history: List[Dict] = []
        self._today_str = datetime.now(BR_TZ).strftime("%Y-%m-%d")
        self._today_start_capital = self.capital
        self.stats = {
            "total_snipes": 0,
            "successful": 0,
            "failed": 0,
            "rugged": 0,
            "avg_pnl": 0.0,
            "best_pnl": 0.0,
            "worst_pnl": 0.0,
            "total_pnl": 0.0,
            "win_rate": 0.0,
            "avg_hold_time_s": 0,
            "tokens_monitored": 0,
        }
        self.config = {
            "max_buy_sol": 0.5,         # Max SOL por snipe
            "min_liquidity_sol": 1.0,   # Liquidez minima
            "max_slippage_pct": 15.0,   # Slippage maximo aceitavel
            "auto_sell_pct": 100.0,     # Vender com 100% lucro
            "stop_loss_pct": -50.0,     # Stop loss em -50%
            "max_hold_time_s": 300,     # Max 5 min holding
            "rug_detection": True,      # Detectar rug pulls
            "min_holders": 5,           # Minimo de holders antes de comprar
            "blacklist_devs": [],       # Devs conhecidos por rug
            "trade_size_pct": 10.0,     # Usa 10% do capital por snipe
        }
        self._running = False

    def _check_new_day(self):
        today = datetime.now(BR_TZ).strftime("%Y-%m-%d")
        if today != self._today_str:
            self.daily_history.append({
                "date": self._today_str,
                "start_capital": self._today_start_capital,
                "end_capital": self.capital,
                "pnl": self.capital - self._today_start_capital,
            })
            if len(self.daily_history) > 30:
                self.daily_history = self.daily_history[-30:]
            self._today_str = today
            self._today_start_capital = self.capital

    async def simulate_monitoring(self) -> Dict:
        """
        Simula monitoramento de novos tokens.
        Em producao: conectaria ao websocket do Pump.fun para detectar lancamentos.
        Em teste: gera dados simulados baseados em padroes reais.
        Capital ficticio: $100 inicial, cada snipe usa % do capital.
        """
        self._check_new_day()
        now = time.time()
        simulated_tokens = [
            {"name": "DOGE2024", "liq": 5.2, "holders": 12, "price_change": random.uniform(-80, 500)},
            {"name": "MOONCAT", "liq": 2.1, "holders": 8, "price_change": random.uniform(-90, 1000)},
            {"name": "SOLMEME", "liq": 0.8, "holders": 3, "price_change": random.uniform(-95, 200)},
            {"name": "PEPE3", "liq": 15.0, "holders": 45, "price_change": random.uniform(-60, 800)},
            {"name": "RUGGY", "liq": 0.3, "holders": 2, "price_change": -99.0},  # Rug pull
        ]

        token = random.choice(simulated_tokens)
        is_rug = token["price_change"] <= -90 and token["liq"] < 1.0

        # Calcula tamanho do trade baseado no capital disponivel
        trade_size = self.capital * (self.config["trade_size_pct"] / 100)
        if trade_size < 0.01:
            trade_size = 0.01  # minimo

        target = SnipeTarget(
            token_address=f"sim_{int(now)}_{random.randint(1000,9999)}",
            token_name=token["name"],
            detected_at=now,
            buy_price=random.uniform(0.00001, 0.001),
            liquidity_sol=token["liq"],
            holders=token["holders"],
        )

        # Simula resultado
        trade_pnl_usd = 0.0
        if is_rug:
            target.status = "rugged"
            target.pnl_pct = -99.0
            trade_pnl_usd = trade_size * (target.pnl_pct / 100)
            self.stats["rugged"] += 1
        elif token["liq"] < self.config["min_liquidity_sol"]:
            target.status = "failed"
            target.pnl_pct = 0.0
            self.stats["failed"] += 1
        else:
            target.status = "sold"
            target.pnl_pct = token["price_change"]
            trade_pnl_usd = trade_size * (target.pnl_pct / 100)
            if target.pnl_pct > 0:
                self.stats["successful"] += 1
            else:
                self.stats["failed"] += 1

        # Atualiza capital
        if target.status != "failed":
            self.total_invested += trade_size
            if trade_pnl_usd > 0:
                self.total_gains += trade_pnl_usd
            else:
                self.total_losses += abs(trade_pnl_usd)
            self.capital += trade_pnl_usd

        target.current_price = target.buy_price * (1 + target.pnl_pct / 100)
        self.targets.append(target)
        if len(self.targets) > 100:
            self.targets = self.targets[-100:]

        self.stats["total_snipes"] += 1
        self.stats["tokens_monitored"] += 1
        self._update_stats()

        return self.get_dashboard_data()

    def _update_stats(self):
        completed = [t for t in self.targets if t.status in ("sold", "rugged", "failed") and t.pnl_pct != 0]
        if completed:
            pnls = [t.pnl_pct for t in completed]
            self.stats["avg_pnl"] = sum(pnls) / len(pnls)
            self.stats["best_pnl"] = max(pnls)
            self.stats["worst_pnl"] = min(pnls)
            self.stats["total_pnl"] = sum(pnls)
            wins = sum(1 for p in pnls if p > 0)
            self.stats["win_rate"] = (wins / len(pnls)) * 100 if pnls else 0

    def get_dashboard_data(self) -> Dict:
        recent = self.targets[-10:] if self.targets else []
        today_pnl = self.capital - self._today_start_capital
        return {
            "strategy_name": self.NAME,
            "risk_level": self.RISK_LEVEL,
            "return_level": self.RETURN_LEVEL,
            "time_frame": self.TIME_FRAME,
            "description": self.DESCRIPTION,
            "tools": self.TOOLS,
            "capital": {
                "initial": self.INITIAL_CAPITAL,
                "current": round(self.capital, 2),
                "total_invested": round(self.total_invested, 2),
                "total_gains": round(self.total_gains, 2),
                "total_losses": round(self.total_losses, 2),
                "pnl_usd": round(self.capital - self.INITIAL_CAPITAL, 2),
                "pnl_pct": round(((self.capital - self.INITIAL_CAPITAL) / self.INITIAL_CAPITAL) * 100, 2),
                "today_pnl": round(today_pnl, 2),
            },
            "daily_history": self.daily_history[-7:],
            "stats": self.stats.copy(),
            "recent_targets": [
                {
                    "name": t.token_name,
                    "status": t.status,
                    "pnl_pct": round(t.pnl_pct, 2),
                    "liquidity": round(t.liquidity_sol, 2),
                    "holders": t.holders,
                    "time": datetime.fromtimestamp(t.detected_at, tz=BR_TZ).strftime("%H:%M:%S"),
                }
                for t in reversed(recent)
            ],
            "config": self.config.copy(),
        }
