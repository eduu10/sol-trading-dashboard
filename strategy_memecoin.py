"""
Estrategia 2: TRADING DE MEME COINS COM ANALISE DE LIQUIDEZ
=============================================================
Identifica meme coins da Solana com liquidez real, volume crescente
e tempo de mercado, focando em entradas e saidas rapidas baseadas em momentum.

Risco: ALTO | Retorno: ALTO
Tempo de operacao: Minutos a horas
Ferramentas: DexScreener, Birdeye, Jupiter Aggregator
Ideal para: Traders experientes em analise on-chain e sentimento de mercado
"""

import asyncio
import logging
import time
import random
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from typing import List, Dict, Optional

logger = logging.getLogger("StrategyMemeCoin")

BR_TZ = timezone(timedelta(hours=-3))


@dataclass
class MemeCoinSignal:
    token_address: str
    token_name: str
    detected_at: float
    entry_price: float = 0.0
    current_price: float = 0.0
    exit_price: float = 0.0
    status: str = "watching"  # watching, entered, exited, stopped
    pnl_pct: float = 0.0
    liquidity_usd: float = 0.0
    volume_24h: float = 0.0
    volume_change_pct: float = 0.0
    holders: int = 0
    market_cap: float = 0.0
    momentum_score: float = 0.0
    social_score: float = 0.0


class MemeCoinStrategy:
    """
    Estrategia de trading de meme coins com analise de liquidez.

    Modo TESTE (simulacao):
    - Monitora meme coins populares da Solana
    - Analisa liquidez, volume e momentum
    - Calcula score de entrada baseado em multiplos fatores
    - Simula entradas/saidas baseadas em momentum
    """

    NAME = "Meme Coins Liquidez"
    RISK_LEVEL = "ALTO"
    RETURN_LEVEL = "ALTO"
    TIME_FRAME = "Min a Horas"
    DESCRIPTION = (
        "Identifica meme coins da Solana com liquidez real, volume crescente "
        "e momentum. Entradas e saidas rapidas baseadas em analise on-chain."
    )
    TOOLS = ["DexScreener", "Birdeye", "Jupiter Aggregator"]

    # Meme coins populares para simular
    TRACKED_TOKENS = [
        {"name": "BONK", "base_price": 0.000028, "volatility": 0.15},
        {"name": "WIF", "base_price": 2.50, "volatility": 0.20},
        {"name": "POPCAT", "base_price": 0.85, "volatility": 0.25},
        {"name": "MEW", "base_price": 0.008, "volatility": 0.18},
        {"name": "MYRO", "base_price": 0.12, "volatility": 0.22},
        {"name": "BOME", "base_price": 0.009, "volatility": 0.30},
        {"name": "SLERF", "base_price": 0.35, "volatility": 0.35},
        {"name": "SAMO", "base_price": 0.02, "volatility": 0.16},
    ]

    INITIAL_CAPITAL = 100.0

    def __init__(self):
        self.signals: List[MemeCoinSignal] = []
        self.capital = self.INITIAL_CAPITAL
        self.total_invested = 0.0
        self.total_gains = 0.0
        self.total_losses = 0.0
        self.daily_history: List[Dict] = []
        self._today_str = datetime.now(BR_TZ).strftime("%Y-%m-%d")
        self._today_start_capital = self.capital
        self.stats = {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "avg_pnl": 0.0,
            "best_trade": 0.0,
            "worst_trade": 0.0,
            "total_pnl": 0.0,
            "win_rate": 0.0,
            "avg_hold_time_min": 0,
            "tokens_tracked": len(self.TRACKED_TOKENS),
            "high_momentum_count": 0,
        }
        self.config = {
            "min_liquidity_usd": 50000,     # Min $50k liquidez
            "min_volume_24h": 100000,       # Min $100k volume 24h
            "min_volume_change_pct": 30,    # Volume crescendo 30%+
            "min_holders": 100,             # Minimo 100 holders
            "momentum_threshold": 0.6,     # Score minimo de momentum
            "take_profit_pct": 30.0,       # TP em 30%
            "stop_loss_pct": -15.0,        # SL em -15%
            "max_position_pct": 10.0,      # Max 10% do capital
            "trailing_stop_pct": 8.0,      # Trailing 8%
        }

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

    async def simulate_analysis(self) -> Dict:
        """
        Simula analise de meme coins.
        Em producao: usaria DexScreener/Birdeye APIs para dados reais.
        Capital ficticio: $100 inicial.
        """
        self._check_new_day()
        now = time.time()
        token = random.choice(self.TRACKED_TOKENS)

        # Simula metricas
        vol_change = random.uniform(-40, 200)
        momentum = random.uniform(0, 1)
        liquidity = random.uniform(20000, 500000)
        volume = random.uniform(50000, 2000000)
        holders = random.randint(50, 5000)
        social = random.uniform(0, 1)
        price_change = random.uniform(-25, 60) * token["volatility"]

        signal = MemeCoinSignal(
            token_address=f"sim_{token['name'].lower()}_{int(now)}",
            token_name=token["name"],
            detected_at=now,
            entry_price=token["base_price"],
            current_price=token["base_price"] * (1 + price_change / 100),
            liquidity_usd=liquidity,
            volume_24h=volume,
            volume_change_pct=vol_change,
            holders=holders,
            market_cap=liquidity * random.uniform(3, 15),
            momentum_score=momentum,
            social_score=social,
        )

        # Decide se entra
        enters = (
            liquidity >= self.config["min_liquidity_usd"]
            and volume >= self.config["min_volume_24h"]
            and vol_change >= self.config["min_volume_change_pct"]
            and holders >= self.config["min_holders"]
            and momentum >= self.config["momentum_threshold"]
        )

        if enters:
            signal.status = "entered"
            signal.pnl_pct = price_change

            # Tamanho da posicao: 10% do capital
            trade_size = self.capital * (self.config["max_position_pct"] / 100)
            if trade_size < 0.01:
                trade_size = 0.01
            trade_pnl_usd = trade_size * (price_change / 100)

            if price_change >= self.config["take_profit_pct"]:
                signal.status = "exited"
                signal.exit_price = signal.current_price
                self.stats["wins"] += 1
            elif price_change <= self.config["stop_loss_pct"]:
                signal.status = "stopped"
                signal.exit_price = signal.current_price
                self.stats["losses"] += 1
            else:
                # Ainda segurando - PnL nao realizado
                pass

            # Atualiza capital (trades finalizados)
            if signal.status in ("exited", "stopped"):
                self.total_invested += trade_size
                if trade_pnl_usd > 0:
                    self.total_gains += trade_pnl_usd
                else:
                    self.total_losses += abs(trade_pnl_usd)
                self.capital += trade_pnl_usd

            self.stats["total_trades"] += 1
            if momentum >= 0.7:
                self.stats["high_momentum_count"] += 1
        else:
            signal.status = "watching"

        self.signals.append(signal)
        if len(self.signals) > 100:
            self.signals = self.signals[-100:]

        self._update_stats()
        return self.get_dashboard_data()

    def _update_stats(self):
        completed = [s for s in self.signals if s.status in ("exited", "stopped")]
        if completed:
            pnls = [s.pnl_pct for s in completed]
            self.stats["avg_pnl"] = sum(pnls) / len(pnls)
            self.stats["best_trade"] = max(pnls)
            self.stats["worst_trade"] = min(pnls)
            self.stats["total_pnl"] = sum(pnls)
            total = self.stats["wins"] + self.stats["losses"]
            self.stats["win_rate"] = (self.stats["wins"] / total) * 100 if total else 0

    def get_dashboard_data(self) -> Dict:
        recent = self.signals[-10:] if self.signals else []
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
            "recent_signals": [
                {
                    "name": s.token_name,
                    "status": s.status,
                    "pnl_pct": round(s.pnl_pct, 2),
                    "momentum": round(s.momentum_score, 2),
                    "volume_24h": round(s.volume_24h, 0),
                    "vol_change": round(s.volume_change_pct, 1),
                    "liquidity": round(s.liquidity_usd, 0),
                    "holders": s.holders,
                    "time": datetime.fromtimestamp(s.detected_at, tz=BR_TZ).strftime("%H:%M:%S"),
                }
                for s in reversed(recent)
            ],
            "config": self.config.copy(),
        }
