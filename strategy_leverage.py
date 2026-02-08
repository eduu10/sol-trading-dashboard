"""
Estrategia 5: LEVERAGE TRADING EM DEX SOLANA
===============================================
Usa plataformas como Jupiter Perpetuals para operar com alavancagem
(long/short) em SOL e principais tokens, multiplicando exposicao.

Risco: MUITO ALTO | Retorno: MUITO ALTO
Tempo de operacao: Horas a dias
Ferramentas: Jupiter Perpetuals, Drift Protocol, Mango Markets
Ideal para: Traders experientes com gestao de risco rigorosa
"""

import asyncio
import logging
import time
import random
import math
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from typing import List, Dict, Optional

logger = logging.getLogger("StrategyLeverage")

BR_TZ = timezone(timedelta(hours=-3))


@dataclass
class LeveragePosition:
    token: str
    platform: str
    detected_at: float
    direction: str  # long, short
    leverage: float
    entry_price: float
    current_price: float = 0.0
    liquidation_price: float = 0.0
    margin_usd: float = 0.0
    position_size_usd: float = 0.0
    funding_rate: float = 0.0
    status: str = "open"  # open, tp_hit, sl_hit, liquidated, closed
    pnl_pct: float = 0.0
    pnl_usd: float = 0.0
    hold_time_h: float = 0.0
    max_pnl_pct: float = 0.0
    min_pnl_pct: float = 0.0
    funding_paid: float = 0.0


class LeverageStrategy:
    """
    Estrategia de Leverage Trading em DEX Solana.

    Modo TESTE (simulacao):
    - Simula trades com alavancagem em Jupiter Perpetuals / Drift
    - Calcula liquidacao, funding rates e margem
    - Rastreia PnL com alavancagem
    - Demonstra riscos de liquidacao
    """

    NAME = "Leverage Trading"
    RISK_LEVEL = "MUITO ALTO"
    RETURN_LEVEL = "MUITO ALTO"
    TIME_FRAME = "Horas a Dias"
    DESCRIPTION = (
        "Opera com alavancagem (2x-20x) via Jupiter Perpetuals e Drift Protocol. "
        "Multiplica exposicao - alto risco de liquidacao."
    )
    TOOLS = ["Jupiter Perpetuals", "Drift Protocol", "Mango Markets"]

    PLATFORMS = [
        {"name": "Jupiter Perps", "max_leverage": 100, "fee_pct": 0.06, "funding_8h": 0.01},
        {"name": "Drift Protocol", "max_leverage": 20, "fee_pct": 0.05, "funding_8h": 0.008},
        {"name": "Mango Markets", "max_leverage": 10, "fee_pct": 0.04, "funding_8h": 0.005},
    ]

    LEVERAGE_TOKENS = [
        {"token": "SOL", "price": 180.0, "daily_vol": 3.5},
        {"token": "ETH", "price": 3500.0, "daily_vol": 2.8},
        {"token": "BTC", "price": 95000.0, "daily_vol": 2.0},
        {"token": "JUP", "price": 1.20, "daily_vol": 5.0},
    ]

    def __init__(self):
        self.positions: List[LeveragePosition] = []
        self.stats = {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "liquidations": 0,
            "avg_pnl_pct": 0.0,
            "total_pnl_usd": 0.0,
            "win_rate": 0.0,
            "best_trade_pct": 0.0,
            "worst_trade_pct": 0.0,
            "avg_leverage": 0.0,
            "avg_hold_time_h": 0.0,
            "total_funding_paid": 0.0,
            "total_fees_paid": 0.0,
            "max_drawdown_pct": 0.0,
            "liquidation_rate": 0.0,
            "total_volume_traded": 0.0,
        }
        self.config = {
            "default_leverage": 5,       # 5x padrao
            "max_leverage": 20,          # Max 20x
            "margin_usd": 100,           # $100 margem por trade
            "take_profit_pct": 10.0,     # TP 10% (= 50% com 5x)
            "stop_loss_pct": 5.0,        # SL 5% (= 25% com 5x)
            "max_positions": 2,          # Max 2 posicoes
            "add_margin_pct": 80,        # Adicionar margem se perda > 80% da liq
            "funding_check_interval_h": 8,
            "preferred_platform": "Jupiter Perps",
        }
        self._equity_curve = [0.0]

    async def simulate_leverage_trade(self) -> Dict:
        """
        Simula um trade com alavancagem.
        Em producao: usaria Jupiter Perpetuals API para abrir posicao real.
        """
        now = time.time()
        token_data = random.choice(self.LEVERAGE_TOKENS)
        platform = random.choice(self.PLATFORMS)

        # Parametros
        leverage = random.choice([2, 3, 5, 10, 15, 20])
        leverage = min(leverage, platform["max_leverage"])
        direction = random.choice(["long", "short"])
        margin = self.config["margin_usd"]
        position_size = margin * leverage
        entry = token_data["price"]

        # Calcula liquidacao
        if direction == "long":
            liquidation = entry * (1 - 0.9 / leverage)  # ~90% da margem
        else:
            liquidation = entry * (1 + 0.9 / leverage)

        # Simula movimento (horas a dias)
        hold_hours = random.uniform(1, 48)
        daily_vol = token_data["daily_vol"] / 100
        hourly_vol = daily_vol / math.sqrt(24)

        # Simula caminho de preco
        price_path = [entry]
        for h in range(int(hold_hours * 4)):  # granularidade de 15min
            change = random.gauss(0, hourly_vol * math.sqrt(0.25))
            # Adiciona leve drift baseado em direcao (viés do mercado)
            drift = random.uniform(-0.0005, 0.001)
            new_price = price_path[-1] * (1 + change + drift)
            price_path.append(new_price)

        # Calcula SL/TP e verifica liquidacao
        if direction == "long":
            sl_price = entry * (1 - self.config["stop_loss_pct"] / 100)
            tp_price = entry * (1 + self.config["take_profit_pct"] / 100)
        else:
            sl_price = entry * (1 + self.config["stop_loss_pct"] / 100)
            tp_price = entry * (1 - self.config["take_profit_pct"] / 100)

        exit_price = price_path[-1]
        status = "closed"
        max_pnl = 0
        min_pnl = 0

        for p in price_path:
            # PnL instantaneo
            if direction == "long":
                inst_pnl = ((p - entry) / entry) * leverage * 100
            else:
                inst_pnl = ((entry - p) / entry) * leverage * 100

            max_pnl = max(max_pnl, inst_pnl)
            min_pnl = min(min_pnl, inst_pnl)

            # Verifica liquidacao
            if direction == "long" and p <= liquidation:
                exit_price = liquidation
                status = "liquidated"
                break
            elif direction == "short" and p >= liquidation:
                exit_price = liquidation
                status = "liquidated"
                break

            # Verifica SL
            if direction == "long" and p <= sl_price:
                exit_price = sl_price
                status = "sl_hit"
                break
            elif direction == "short" and p >= sl_price:
                exit_price = sl_price
                status = "sl_hit"
                break

            # Verifica TP
            if direction == "long" and p >= tp_price:
                exit_price = tp_price
                status = "tp_hit"
                break
            elif direction == "short" and p <= tp_price:
                exit_price = tp_price
                status = "tp_hit"
                break

        # Calcula PnL final
        if direction == "long":
            pnl_pct = ((exit_price - entry) / entry) * leverage * 100
        else:
            pnl_pct = ((entry - exit_price) / entry) * leverage * 100

        if status == "liquidated":
            pnl_pct = -90.0  # Perde ~90% da margem
            pnl_usd = -margin * 0.9
        else:
            pnl_usd = margin * (pnl_pct / 100)

        # Funding rate
        funding_periods = hold_hours / 8
        funding_paid = position_size * (platform["funding_8h"] / 100) * funding_periods
        fees = position_size * (platform["fee_pct"] / 100) * 2  # open + close

        pnl_usd -= (funding_paid + fees)

        pos = LeveragePosition(
            token=token_data["token"],
            platform=platform["name"],
            detected_at=now,
            direction=direction,
            leverage=leverage,
            entry_price=entry,
            current_price=exit_price,
            liquidation_price=liquidation,
            margin_usd=margin,
            position_size_usd=position_size,
            funding_rate=platform["funding_8h"],
            status=status,
            pnl_pct=pnl_pct,
            pnl_usd=pnl_usd,
            hold_time_h=hold_hours,
            max_pnl_pct=max_pnl,
            min_pnl_pct=min_pnl,
            funding_paid=funding_paid,
        )

        self.positions.append(pos)
        if len(self.positions) > 100:
            self.positions = self.positions[-100:]

        self.stats["total_trades"] += 1
        self.stats["total_volume_traded"] += position_size
        self.stats["total_funding_paid"] += funding_paid
        self.stats["total_fees_paid"] += fees

        if status == "liquidated":
            self.stats["liquidations"] += 1
            self.stats["losses"] += 1
        elif status == "tp_hit" or pnl_usd > 0:
            self.stats["wins"] += 1
        else:
            self.stats["losses"] += 1

        self._equity_curve.append(self._equity_curve[-1] + pnl_usd)

        self._update_stats()
        return self.get_dashboard_data()

    def _update_stats(self):
        completed = [p for p in self.positions if p.status != "open"]
        if completed:
            pnls = [p.pnl_pct for p in completed]
            pnls_usd = [p.pnl_usd for p in completed]
            leverages = [p.leverage for p in completed]
            hold_times = [p.hold_time_h for p in completed]

            self.stats["avg_pnl_pct"] = sum(pnls) / len(pnls)
            self.stats["total_pnl_usd"] = sum(pnls_usd)
            self.stats["best_trade_pct"] = max(pnls)
            self.stats["worst_trade_pct"] = min(pnls)
            self.stats["avg_leverage"] = sum(leverages) / len(leverages)
            self.stats["avg_hold_time_h"] = sum(hold_times) / len(hold_times)

            total = self.stats["wins"] + self.stats["losses"]
            self.stats["win_rate"] = (self.stats["wins"] / total) * 100 if total else 0
            self.stats["liquidation_rate"] = (
                (self.stats["liquidations"] / total) * 100 if total else 0
            )

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
        recent = self.positions[-10:] if self.positions else []
        return {
            "strategy_name": self.NAME,
            "risk_level": self.RISK_LEVEL,
            "return_level": self.RETURN_LEVEL,
            "time_frame": self.TIME_FRAME,
            "description": self.DESCRIPTION,
            "tools": self.TOOLS,
            "stats": self.stats.copy(),
            "recent_positions": [
                {
                    "token": p.token,
                    "platform": p.platform,
                    "direction": p.direction,
                    "leverage": f"{p.leverage}x",
                    "status": p.status,
                    "pnl_pct": round(p.pnl_pct, 2),
                    "pnl_usd": round(p.pnl_usd, 2),
                    "margin": round(p.margin_usd, 0),
                    "hold_h": round(p.hold_time_h, 1),
                    "liq_price": round(p.liquidation_price, 2),
                    "time": datetime.fromtimestamp(p.detected_at, tz=BR_TZ).strftime("%H:%M:%S"),
                }
                for p in reversed(recent)
            ],
            "equity_curve": self._equity_curve[-50:],
            "config": self.config.copy(),
        }
