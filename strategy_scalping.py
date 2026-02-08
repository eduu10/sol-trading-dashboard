"""
Estrategia 4: SCALPING EM TOKENS ESTABELECIDOS
=================================================
Multiplas operacoes rapidas (1-5 minutos) em tokens Solana com boa liquidez
(RAY, JUP, BONK, WIF) aproveitando micro-movimentos de preco.

Risco: MEDIO-BAIXO | Retorno: BAIXO MAS CONSISTENTE
Tempo de operacao: 1-5 minutos por trade
Ferramentas: Jupiter para melhor rota, graficos em tempo real
Ideal para: Traders disciplinados com estrategia definida de stop-loss
"""

import asyncio
import logging
import time
import random
import math
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from typing import List, Dict, Optional

logger = logging.getLogger("StrategyScalping")

BR_TZ = timezone(timedelta(hours=-3))


@dataclass
class ScalpTrade:
    token: str
    detected_at: float
    direction: str  # long, short
    entry_price: float
    current_price: float = 0.0
    exit_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    status: str = "open"  # open, tp_hit, sl_hit, timeout, manual
    pnl_pct: float = 0.0
    pnl_usd: float = 0.0
    hold_time_s: int = 0
    spread_cost_pct: float = 0.0
    rsi_at_entry: float = 50.0
    volume_ratio: float = 1.0


class ScalpingStrategy:
    """
    Estrategia de Scalping em tokens estabelecidos.

    Modo TESTE (simulacao):
    - Monitora tokens de alta liquidez na Solana
    - Detecta micro-movimentos usando RSI rapido + EMA curta
    - Simula entradas/saidas rapidas (1-5 min)
    - Foco em consistencia vs alto retorno
    """

    NAME = "Scalping Tokens"
    RISK_LEVEL = "MEDIO-BAIXO"
    RETURN_LEVEL = "BAIXO CONSISTENTE"
    TIME_FRAME = "1-5 min"
    DESCRIPTION = (
        "Multiplas operacoes rapidas em tokens com alta liquidez (SOL, JUP, BONK). "
        "Aproveita micro-movimentos de preco com stop-loss rigido."
    )
    TOOLS = ["Jupiter Router", "Graficos 1m/5m", "Order Book"]

    SCALP_TOKENS = [
        {"token": "SOL", "price": 180.0, "spread": 0.02, "volatility_1m": 0.08},
        {"token": "JUP", "price": 1.20, "spread": 0.05, "volatility_1m": 0.12},
        {"token": "RAY", "price": 4.50, "spread": 0.04, "volatility_1m": 0.10},
        {"token": "BONK", "price": 0.000028, "spread": 0.08, "volatility_1m": 0.15},
        {"token": "WIF", "price": 2.50, "spread": 0.06, "volatility_1m": 0.14},
        {"token": "ORCA", "price": 3.80, "spread": 0.04, "volatility_1m": 0.09},
    ]

    INITIAL_CAPITAL = 100.0

    def __init__(self):
        self.trades: List[ScalpTrade] = []
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
            "timeouts": 0,
            "avg_pnl_pct": 0.0,
            "total_pnl_pct": 0.0,
            "total_pnl_usd": 0.0,
            "win_rate": 0.0,
            "best_trade_pct": 0.0,
            "worst_trade_pct": 0.0,
            "avg_hold_time_s": 0,
            "trades_per_hour": 0.0,
            "sharpe_estimate": 0.0,
            "profit_factor": 0.0,
            "consecutive_wins": 0,
            "consecutive_losses": 0,
            "max_drawdown_pct": 0.0,
        }
        self.config = {
            "scalp_size_pct": 15.0,      # Usa 15% do capital por scalp
            "take_profit_pct": 0.5,      # TP 0.5% (pequeno mas frequente)
            "stop_loss_pct": 0.3,        # SL 0.3% (stop rigido!)
            "max_hold_time_s": 300,      # Max 5 min
            "min_rsi_long": 35,          # RSI < 35 para long
            "max_rsi_short": 65,         # RSI > 65 para short
            "min_volume_ratio": 0.8,     # Volume minimo
            "max_spread_pct": 0.10,      # Spread max aceitavel
            "cooldown_after_loss_s": 30, # Cooldown apos loss
            "max_trades_per_hour": 20,   # Max 20 trades/hora
            "trailing_micro_pct": 0.15,  # Micro trailing stop
        }
        self._start_time = time.time()
        self._equity_curve = [0.0]
        self._consecutive_wins = 0
        self._consecutive_losses = 0

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

    async def simulate_scalp(self) -> Dict:
        """
        Simula uma operacao de scalping.
        Em producao: usaria dados tick-by-tick e order book.
        Capital ficticio: $100 inicial.
        """
        self._check_new_day()
        now = time.time()
        token_data = random.choice(self.SCALP_TOKENS)

        # Simula RSI rapido (periodo 7)
        rsi = random.uniform(20, 80)
        volume_ratio = random.uniform(0.3, 2.5)

        # Determina direcao
        if rsi <= self.config["min_rsi_long"] and volume_ratio >= self.config["min_volume_ratio"]:
            direction = "long"
        elif rsi >= self.config["max_rsi_short"] and volume_ratio >= self.config["min_volume_ratio"]:
            direction = "short"
        else:
            # Sem setup - nao opera
            return self.get_dashboard_data()

        entry = token_data["price"]
        spread_cost = token_data["spread"] / 100
        vol = token_data["volatility_1m"] / 100

        # Simula movimento de preco em 1-5 min
        hold_time = random.randint(30, 300)
        ticks = hold_time // 10
        price_path = [entry]
        for _ in range(ticks):
            change = random.gauss(0, vol * math.sqrt(10/60))
            price_path.append(price_path[-1] * (1 + change))

        # Calcula SL e TP
        if direction == "long":
            sl = entry * (1 - self.config["stop_loss_pct"] / 100)
            tp = entry * (1 + self.config["take_profit_pct"] / 100)
        else:
            sl = entry * (1 + self.config["stop_loss_pct"] / 100)
            tp = entry * (1 - self.config["take_profit_pct"] / 100)

        # Simula execucao
        exit_price = entry
        status = "timeout"
        for p in price_path:
            if direction == "long":
                if p <= sl:
                    exit_price = sl
                    status = "sl_hit"
                    break
                elif p >= tp:
                    exit_price = tp
                    status = "tp_hit"
                    break
            else:
                if p >= sl:
                    exit_price = sl
                    status = "sl_hit"
                    break
                elif p <= tp:
                    exit_price = tp
                    status = "tp_hit"
                    break
        else:
            exit_price = price_path[-1]
            status = "timeout"

        # Calcula PnL
        if direction == "long":
            pnl_pct = ((exit_price - entry) / entry) * 100 - spread_cost * 100
        else:
            pnl_pct = ((entry - exit_price) / entry) * 100 - spread_cost * 100

        scalp_size = self.capital * (self.config["scalp_size_pct"] / 100)
        if scalp_size < 0.01:
            scalp_size = 0.01
        pnl_usd = scalp_size * (pnl_pct / 100)

        # Atualiza capital
        self.total_invested += scalp_size
        if pnl_usd > 0:
            self.total_gains += pnl_usd
        else:
            self.total_losses += abs(pnl_usd)
        self.capital += pnl_usd

        trade = ScalpTrade(
            token=token_data["token"],
            detected_at=now,
            direction=direction,
            entry_price=entry,
            current_price=exit_price,
            exit_price=exit_price,
            stop_loss=sl,
            take_profit=tp,
            status=status,
            pnl_pct=pnl_pct,
            pnl_usd=pnl_usd,
            hold_time_s=hold_time,
            spread_cost_pct=spread_cost * 100,
            rsi_at_entry=rsi,
            volume_ratio=volume_ratio,
        )

        self.trades.append(trade)
        if len(self.trades) > 200:
            self.trades = self.trades[-200:]

        # Atualiza contadores
        self.stats["total_trades"] += 1
        if status == "tp_hit":
            self.stats["wins"] += 1
            self._consecutive_wins += 1
            self._consecutive_losses = 0
        elif status == "sl_hit":
            self.stats["losses"] += 1
            self._consecutive_losses += 1
            self._consecutive_wins = 0
        else:
            if pnl_pct > 0:
                self.stats["wins"] += 1
            else:
                self.stats["losses"] += 1
                self.stats["timeouts"] += 1

        self.stats["consecutive_wins"] = self._consecutive_wins
        self.stats["consecutive_losses"] = self._consecutive_losses

        self._equity_curve.append(self._equity_curve[-1] + pnl_usd)

        self._update_stats()
        return self.get_dashboard_data()

    def _update_stats(self):
        completed = [t for t in self.trades if t.status != "open"]
        if completed:
            pnls = [t.pnl_pct for t in completed]
            pnls_usd = [t.pnl_usd for t in completed]
            hold_times = [t.hold_time_s for t in completed]

            self.stats["avg_pnl_pct"] = sum(pnls) / len(pnls)
            self.stats["total_pnl_pct"] = sum(pnls)
            self.stats["total_pnl_usd"] = sum(pnls_usd)
            self.stats["best_trade_pct"] = max(pnls)
            self.stats["worst_trade_pct"] = min(pnls)
            self.stats["avg_hold_time_s"] = sum(hold_times) / len(hold_times)

            total = self.stats["wins"] + self.stats["losses"]
            self.stats["win_rate"] = (self.stats["wins"] / total) * 100 if total else 0

            elapsed_h = (time.time() - self._start_time) / 3600
            if elapsed_h > 0:
                self.stats["trades_per_hour"] = len(completed) / elapsed_h

            # Profit factor
            gross_wins = sum(p for p in pnls_usd if p > 0)
            gross_losses = abs(sum(p for p in pnls_usd if p < 0))
            self.stats["profit_factor"] = gross_wins / gross_losses if gross_losses > 0 else 0

            # Sharpe estimate
            if len(pnls) > 1:
                avg = sum(pnls) / len(pnls)
                variance = sum((p - avg) ** 2 for p in pnls) / len(pnls)
                std = math.sqrt(variance) if variance > 0 else 1
                self.stats["sharpe_estimate"] = round((avg / std) * math.sqrt(252), 2)

            # Max drawdown
            peak = 0
            max_dd = 0
            for eq in self._equity_curve:
                if eq > peak:
                    peak = eq
                dd = peak - eq
                if dd > max_dd:
                    max_dd = dd
            self.stats["max_drawdown_pct"] = round(max_dd, 2)

    def get_dashboard_data(self) -> Dict:
        recent = self.trades[-10:] if self.trades else []
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
            "recent_trades": [
                {
                    "token": t.token,
                    "direction": t.direction,
                    "status": t.status,
                    "pnl_pct": round(t.pnl_pct, 3),
                    "pnl_usd": round(t.pnl_usd, 2),
                    "hold_time": t.hold_time_s,
                    "rsi": round(t.rsi_at_entry, 1),
                    "time": datetime.fromtimestamp(t.detected_at, tz=BR_TZ).strftime("%H:%M:%S"),
                }
                for t in reversed(recent)
            ],
            "equity_curve": self._equity_curve[-50:],
            "config": self.config.copy(),
        }
