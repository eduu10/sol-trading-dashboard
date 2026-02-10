"""
Estrategia 6: WHALE TRACKING (Seguir Baleias)
=================================================
Monitora transacoes de baleias (grandes movimentacoes de crypto) e
replica a direcao do trade: compra quando baleias compram,
vende quando atinge X% de lucro (take profit rapido).

Fontes de sinal:
- Whale Alert API (whale-alert.io) - transfers, mints, burns
- Monitoramento de wallets conhecidas de baleias na Solana
- Deteccao de grandes compras/vendas em DEXes

Logica:
1. Detecta movimentacao de baleia (transferencia grande para exchange = venda iminente,
   saida de exchange = compra/hold)
2. Filtra por tamanho minimo ($100k+), moeda relevante (SOL)
3. Segue a direcao: baleia comprando -> compra, baleia vendendo -> skip ou short
4. Take profit rapido (3-8% default) — nao tenta segurar muito
5. Stop loss apertado (2-4%) — se o mercado nao segue a baleia, sai rapido

Risco: MEDIO | Retorno: MEDIO-ALTO
Tempo de operacao: Minutos a horas
Ferramentas: Whale Alert API, Solana RPC, Jupiter DEX
"""

import asyncio
import logging
import time
import random
import math
import hashlib
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Optional

logger = logging.getLogger("StrategyWhale")

BR_TZ = timezone(timedelta(hours=-3))


# Tipos de movimentacao de baleia
WHALE_MOVE_TYPES = [
    "exchange_deposit",     # Baleia depositou em exchange -> provavel venda
    "exchange_withdrawal",  # Baleia sacou de exchange -> provavel hold/compra
    "wallet_to_wallet",     # Transferencia entre wallets -> redistribuicao
    "dex_buy",              # Compra grande em DEX
    "dex_sell",             # Venda grande em DEX
    "staking",              # Baleia fazendo stake -> bullish
    "unstaking",            # Baleia desfazendo stake -> pode vender
]

# Exchanges conhecidas (simulacao)
KNOWN_EXCHANGES = ["Binance", "Coinbase", "Kraken", "OKX", "Bybit", "KuCoin", "Gate.io"]

# Wallets conhecidas de baleias (simuladas com nomes descritivos)
WHALE_WALLETS = [
    {"label": "Whale Alpha", "size": "mega", "history_accuracy": 0.72},
    {"label": "Jump Trading", "size": "mega", "history_accuracy": 0.68},
    {"label": "Alameda Remnant", "size": "large", "history_accuracy": 0.55},
    {"label": "Galaxy Digital", "size": "mega", "history_accuracy": 0.71},
    {"label": "Whale Bravo", "size": "large", "history_accuracy": 0.63},
    {"label": "DeFi Whale 1", "size": "large", "history_accuracy": 0.60},
    {"label": "SOL Accumulator", "size": "medium", "history_accuracy": 0.65},
    {"label": "Institutional Fund", "size": "mega", "history_accuracy": 0.74},
    {"label": "Smart Money 42", "size": "medium", "history_accuracy": 0.58},
    {"label": "Whale Charlie", "size": "large", "history_accuracy": 0.66},
]


@dataclass
class WhaleSignal:
    """Sinal detectado de movimentacao de baleia."""
    detected_at: float
    whale_label: str
    move_type: str               # tipo de movimentacao
    direction: str = "long"      # long (compra) ou short (venda)
    amount_usd: float = 0.0     # valor movimentado em USD
    token: str = "SOL"
    source: str = ""             # de onde veio (exchange, wallet)
    destination: str = ""        # para onde foi
    confidence_score: float = 0.5  # 0-1, quao confiavel é o sinal
    status: str = "detected"     # detected, bought, sold, tp_hit, sl_hit, timeout, skipped
    entry_price: float = 0.0
    exit_price: float = 0.0
    pnl_pct: float = 0.0
    pnl_usd: float = 0.0
    hold_time_s: int = 0
    tx_hash: str = ""


class WhaleTrackingStrategy:
    """
    Estrategia de seguir baleias de crypto.

    Modo TESTE (simulacao):
    - Simula deteccao de movimentacoes de baleias
    - Calcula confianca baseada no tipo de movimento e historico da baleia
    - Segue movimentos bullish (saida de exchange, compra em DEX, staking)
    - Take profit rapido + stop loss apertado
    """

    NAME = "Whale Tracking"
    RISK_LEVEL = "MEDIO"
    RETURN_LEVEL = "MEDIO-ALTO"
    TIME_FRAME = "Min-Horas"
    DESCRIPTION = (
        "Segue movimentacoes de baleias (grandes holders) de crypto. "
        "Quando baleias compram/acumulam, replica o trade com TP rapido."
    )
    TOOLS = ["Whale Alert API", "Solana RPC", "Jupiter DEX", "Wallet Tracker"]

    INITIAL_CAPITAL = 100.0

    def __init__(self):
        self.trades: List[WhaleSignal] = []
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
            "skipped": 0,
            "avg_pnl_pct": 0.0,
            "total_pnl_pct": 0.0,
            "total_pnl_usd": 0.0,
            "win_rate": 0.0,
            "best_trade_pct": 0.0,
            "worst_trade_pct": 0.0,
            "avg_hold_time_s": 0,
            "signals_detected": 0,
            "signals_followed": 0,
            "avg_whale_amount_usd": 0.0,
            "top_whale": "",
            "top_whale_pnl": 0.0,
            "bullish_signals": 0,
            "bearish_signals": 0,
        }
        self.config = {
            "trade_size_pct": 20.0,       # % do capital por trade
            "take_profit_pct": 5.0,       # TP 5% (rapido)
            "stop_loss_pct": 3.0,         # SL 3%
            "max_hold_time_s": 1800,      # Max 30 min
            "min_whale_amount_usd": 100_000,  # Minimo $100k para considerar
            "min_confidence": 0.55,       # Confianca minima para seguir
            "cooldown_s": 60,             # Cooldown entre trades
            "max_trades_per_hour": 8,     # Maximo de trades por hora
            "follow_buys_only": False,    # Se True, so segue compras (mais conservador)
            "trailing_pct": 1.5,          # Trailing stop %
        }
        self._start_time = time.time()
        self._equity_curve = [0.0]
        self._last_trade_time = 0
        self._whale_performance: Dict[str, Dict] = {}  # Performance por baleia

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

    def _generate_whale_signal(self) -> Optional[WhaleSignal]:
        """
        Simula deteccao de uma movimentacao de baleia.
        Em producao: usaria Whale Alert API + Solana RPC para detectar
        transacoes grandes em tempo real.
        """
        # Nem sempre tem sinal (60% chance de detectar algo)
        if random.random() > 0.60:
            return None

        whale = random.choice(WHALE_WALLETS)
        move_type = random.choice(WHALE_MOVE_TYPES)

        # Tamanho da movimentacao baseado no tipo de baleia
        size_ranges = {
            "mega": (500_000, 10_000_000),
            "large": (100_000, 2_000_000),
            "medium": (50_000, 500_000),
        }
        min_amt, max_amt = size_ranges.get(whale["size"], (50_000, 500_000))
        amount_usd = random.uniform(min_amt, max_amt)

        # Determina direcao baseada no tipo de movimento
        bullish_moves = ["exchange_withdrawal", "dex_buy", "staking"]
        bearish_moves = ["exchange_deposit", "dex_sell", "unstaking"]

        if move_type in bullish_moves:
            direction = "long"
            self.stats["bullish_signals"] += 1
        elif move_type in bearish_moves:
            direction = "short"
            self.stats["bearish_signals"] += 1
        else:
            # wallet_to_wallet - ambiguo, tende a ser neutro/levemente bullish
            direction = random.choice(["long", "long", "short"])

        # Calcula confianca do sinal
        confidence = self._calculate_signal_confidence(whale, move_type, amount_usd)

        # Source/Destination
        if move_type in ("exchange_deposit", "dex_sell"):
            source = whale["label"]
            destination = random.choice(KNOWN_EXCHANGES)
        elif move_type in ("exchange_withdrawal", "dex_buy"):
            source = random.choice(KNOWN_EXCHANGES)
            destination = whale["label"]
        else:
            source = whale["label"]
            destination = f"Wallet_{hashlib.md5(str(time.time()).encode()).hexdigest()[:8]}"

        self.stats["signals_detected"] += 1

        return WhaleSignal(
            detected_at=time.time(),
            whale_label=whale["label"],
            move_type=move_type,
            direction=direction,
            amount_usd=amount_usd,
            token="SOL",
            source=source,
            destination=destination,
            confidence_score=confidence,
        )

    def _calculate_signal_confidence(self, whale: dict, move_type: str,
                                      amount_usd: float) -> float:
        """Calcula confianca de um sinal de baleia."""
        conf = 0.3

        # Historico da baleia (accuracy passado)
        conf += whale["history_accuracy"] * 0.3

        # Tipo de movimento (alguns sao mais confiaveis)
        move_confidence = {
            "dex_buy": 0.15,          # Compra direta em DEX = muito bullish
            "exchange_withdrawal": 0.12,  # Saiu da exchange = hold
            "staking": 0.10,          # Staking = muito bullish
            "dex_sell": 0.13,         # Venda em DEX = bearish claro
            "exchange_deposit": 0.10, # Entrou na exchange = pode vender
            "unstaking": 0.08,        # Unstaking = pode vender
            "wallet_to_wallet": 0.03, # Ambiguo
        }
        conf += move_confidence.get(move_type, 0.05)

        # Volume (quanto maior, mais impacto no mercado)
        if amount_usd >= 5_000_000:
            conf += 0.15
        elif amount_usd >= 1_000_000:
            conf += 0.10
        elif amount_usd >= 500_000:
            conf += 0.05

        # Performance passada dessa baleia no nosso tracking
        perf = self._whale_performance.get(whale["label"], {})
        if perf.get("trades", 0) >= 3:
            whale_wr = perf.get("wins", 0) / perf["trades"]
            if whale_wr > 0.6:
                conf += 0.10
            elif whale_wr < 0.3:
                conf -= 0.10

        return max(0.1, min(0.95, conf))

    async def simulate_whale_tracking(self) -> Dict:
        """
        Simula um ciclo de monitoramento de baleias.
        Em producao: buscaria dados da Whale Alert API e Solana RPC.
        """
        self._check_new_day()
        now = time.time()

        # Gera sinal de baleia
        signal = self._generate_whale_signal()

        if not signal:
            return self.get_dashboard_data()

        # Filtro: tamanho minimo
        if signal.amount_usd < self.config["min_whale_amount_usd"]:
            signal.status = "skipped"
            self.stats["skipped"] += 1
            return self.get_dashboard_data()

        # Filtro: confianca minima
        if signal.confidence_score < self.config["min_confidence"]:
            signal.status = "skipped"
            self.stats["skipped"] += 1
            return self.get_dashboard_data()

        # Filtro: so segue compras se configurado
        if self.config["follow_buys_only"] and signal.direction != "long":
            signal.status = "skipped"
            self.stats["skipped"] += 1
            return self.get_dashboard_data()

        # Filtro: cooldown
        if now - self._last_trade_time < self.config["cooldown_s"]:
            signal.status = "skipped"
            self.stats["skipped"] += 1
            return self.get_dashboard_data()

        # === SIMULA EXECUCAO DO TRADE ===
        self.stats["signals_followed"] += 1
        self._last_trade_time = now

        # Preco de entrada (simulado baseado no SOL ~180)
        base_price = 180.0 + random.uniform(-10, 10)
        signal.entry_price = base_price

        # Simula movimento de preco apos o sinal
        # Baleias geralmente movem o mercado na direcao certa 55-70% do tempo
        whale_accuracy = random.random()
        whale_is_right = whale_accuracy < signal.confidence_score

        trade_size = self.capital * (self.config["trade_size_pct"] / 100)
        if trade_size < 0.01:
            trade_size = 0.01

        hold_time = random.randint(60, self.config["max_hold_time_s"])

        # Simula path de preco
        volatility = 0.001  # SOL volatilidade por minuto
        ticks = hold_time // 30
        price_path = [base_price]

        # Drift baseado em se a baleia acertou
        if whale_is_right:
            if signal.direction == "long":
                drift = random.uniform(0.0002, 0.001)  # Sobe
            else:
                drift = random.uniform(-0.001, -0.0002)  # Cai
        else:
            if signal.direction == "long":
                drift = random.uniform(-0.0008, 0.0002)  # Lateral/cai
            else:
                drift = random.uniform(-0.0002, 0.0008)  # Lateral/sobe

        for _ in range(max(1, ticks)):
            change = drift + random.gauss(0, volatility * math.sqrt(30/60))
            price_path.append(price_path[-1] * (1 + change))

        # Aplica TP/SL no path
        tp_pct = self.config["take_profit_pct"]
        sl_pct = self.config["stop_loss_pct"]

        if signal.direction == "long":
            tp_price = base_price * (1 + tp_pct / 100)
            sl_price = base_price * (1 - sl_pct / 100)
        else:
            tp_price = base_price * (1 - tp_pct / 100)
            sl_price = base_price * (1 + sl_pct / 100)

        exit_price = base_price
        status = "timeout"
        actual_hold = hold_time

        for i, p in enumerate(price_path):
            if signal.direction == "long":
                if p >= tp_price:
                    exit_price = tp_price
                    status = "tp_hit"
                    actual_hold = (i + 1) * 30
                    break
                elif p <= sl_price:
                    exit_price = sl_price
                    status = "sl_hit"
                    actual_hold = (i + 1) * 30
                    break
            else:
                if p <= tp_price:
                    exit_price = tp_price
                    status = "tp_hit"
                    actual_hold = (i + 1) * 30
                    break
                elif p >= sl_price:
                    exit_price = sl_price
                    status = "sl_hit"
                    actual_hold = (i + 1) * 30
                    break
        else:
            exit_price = price_path[-1]
            status = "timeout"

        # Calcula PnL
        if signal.direction == "long":
            pnl_pct = ((exit_price - base_price) / base_price) * 100
        else:
            pnl_pct = ((base_price - exit_price) / base_price) * 100

        pnl_usd = trade_size * (pnl_pct / 100)

        # Atualiza capital
        self.total_invested += trade_size
        if pnl_usd > 0:
            self.total_gains += pnl_usd
        else:
            self.total_losses += abs(pnl_usd)
        self.capital += pnl_usd

        # Atualiza sinal
        signal.status = status
        signal.exit_price = exit_price
        signal.pnl_pct = pnl_pct
        signal.pnl_usd = pnl_usd
        signal.hold_time_s = actual_hold

        self.trades.append(signal)
        if len(self.trades) > 200:
            self.trades = self.trades[-200:]

        # Atualiza stats
        self.stats["total_trades"] += 1
        if pnl_pct > 0:
            self.stats["wins"] += 1
        else:
            self.stats["losses"] += 1

        # Atualiza performance da baleia
        wl = signal.whale_label
        if wl not in self._whale_performance:
            self._whale_performance[wl] = {"trades": 0, "wins": 0, "pnl": 0.0}
        self._whale_performance[wl]["trades"] += 1
        if pnl_pct > 0:
            self._whale_performance[wl]["wins"] += 1
        self._whale_performance[wl]["pnl"] += pnl_usd

        self._equity_curve.append(self._equity_curve[-1] + pnl_usd)
        self._update_stats()

        return self.get_dashboard_data()

    def _update_stats(self):
        completed = [t for t in self.trades if t.status not in ("detected", "skipped")]
        if not completed:
            return

        pnls = [t.pnl_pct for t in completed]
        pnls_usd = [t.pnl_usd for t in completed]
        hold_times = [t.hold_time_s for t in completed]
        amounts = [t.amount_usd for t in completed]

        self.stats["avg_pnl_pct"] = sum(pnls) / len(pnls)
        self.stats["total_pnl_pct"] = sum(pnls)
        self.stats["total_pnl_usd"] = sum(pnls_usd)
        self.stats["best_trade_pct"] = max(pnls)
        self.stats["worst_trade_pct"] = min(pnls)
        self.stats["avg_hold_time_s"] = sum(hold_times) / len(hold_times)
        self.stats["avg_whale_amount_usd"] = sum(amounts) / len(amounts)

        total = self.stats["wins"] + self.stats["losses"]
        self.stats["win_rate"] = (self.stats["wins"] / total) * 100 if total else 0

        # Top whale
        if self._whale_performance:
            best = max(self._whale_performance.items(), key=lambda x: x[1]["pnl"])
            self.stats["top_whale"] = best[0]
            self.stats["top_whale_pnl"] = round(best[1]["pnl"], 4)

    def get_dashboard_data(self) -> Dict:
        recent = self.trades[-10:] if self.trades else []
        today_pnl = self.capital - self._today_start_capital

        # Top baleias para dashboard
        whale_rankings = []
        for wl, perf in sorted(self._whale_performance.items(),
                                key=lambda x: x[1]["pnl"], reverse=True)[:5]:
            wr = (perf["wins"] / perf["trades"] * 100) if perf["trades"] > 0 else 0
            whale_rankings.append({
                "label": wl,
                "trades": perf["trades"],
                "win_rate": round(wr, 1),
                "pnl": round(perf["pnl"], 4),
            })

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
                    "whale": t.whale_label,
                    "move_type": t.move_type,
                    "direction": t.direction,
                    "whale_amount": f"${t.amount_usd:,.0f}",
                    "confidence": round(t.confidence_score, 2),
                    "status": t.status,
                    "pnl_pct": round(t.pnl_pct, 3),
                    "pnl_usd": round(t.pnl_usd, 2),
                    "hold_time": t.hold_time_s,
                    "source": t.source,
                    "destination": t.destination,
                    "time": datetime.fromtimestamp(t.detected_at, tz=BR_TZ).strftime("%H:%M:%S"),
                }
                for t in reversed(recent)
                if t.status not in ("detected", "skipped")
            ],
            "whale_rankings": whale_rankings,
            "equity_curve": self._equity_curve[-50:],
            "config": self.config.copy(),
        }
