"""
Motor de Confluência
======================
Combina indicadores multi-timeframe para gerar sinais de alta confiança.
"""

import numpy as np
import json
import os
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
import config
from indicators import get_all_scores, calculate_all


@dataclass
class TradeSignal:
    timestamp: str
    symbol: str
    direction: str          # "long" / "short"
    confidence: float
    entry_price: float
    stop_loss: float
    take_profits: List[float]
    timeframe: str
    indicators_detail: Dict
    confluence_score: float
    risk_reward_ratio: float

    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp, "symbol": self.symbol,
            "direction": self.direction, "confidence": round(self.confidence, 4),
            "entry_price": self.entry_price, "stop_loss": self.stop_loss,
            "take_profits": self.take_profits, "timeframe": self.timeframe,
            "confluence_score": round(self.confluence_score, 4),
            "risk_reward_ratio": round(self.risk_reward_ratio, 2),
            "indicators_detail": self.indicators_detail,
        }

    def telegram_message(self) -> str:
        emoji = "🟢" if self.direction == "long" else "🔴"
        tps = "\n".join([f"   🎯 TP{i+1}: ${tp:,.2f}" for i, tp in enumerate(self.take_profits)])
        return (
            f"{emoji} **SINAL: {self.direction.upper()}**\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📊 Par: {self.symbol}\n"
            f"💰 Entrada: ${self.entry_price:,.2f}\n"
            f"🛑 Stop Loss: ${self.stop_loss:,.2f}\n"
            f"{tps}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📈 Confiança: {self.confidence:.0%}\n"
            f"⚖️ R:R: {self.risk_reward_ratio:.1f}:1\n"
            f"🕐 TF: {self.timeframe}\n"
            f"🔗 DEX: Jupiter (Solana)\n"
        )


class ConfluenceEngine:
    def __init__(self, learning_engine=None):
        self.weights = config.INDICATOR_WEIGHTS.copy()
        self.threshold = config.CONFLUENCE_THRESHOLD
        self.min_agree = config.MIN_INDICATORS_AGREE
        self.trade_history: List[Dict] = []
        self.learning = learning_engine  # Motor de aprendizado
        self._load_history()

    def _load_history(self):
        if os.path.exists("trade_history.json"):
            with open("trade_history.json") as f:
                self.trade_history = json.load(f)

    def _save_history(self):
        with open("trade_history.json", "w") as f:
            json.dump(self.trade_history, f, indent=2)

    # --------------------------------------------------------
    # NORMALIZA SCORES PARA -1..1
    # --------------------------------------------------------
    def _normalize(self, scores: Dict) -> Dict[str, float]:
        n = {}
        n["ema_alignment"] = float(scores["ema_alignment"])

        cx = scores["ema_crossover"]
        n["ema_crossover"] = cx["strength"] * (1 if cx["signal"] == "buy" else -1 if cx["signal"] == "sell" else 0)

        n["ichimoku_trend"] = float(scores["ichimoku_trend"])

        isig = scores["ichimoku_signal"]
        n["ichimoku_signal"] = isig["strength"] * (1 if isig["signal"] == "buy" else -1 if isig["signal"] == "sell" else 0)

        fib = scores["fibonacci"]
        fs = fib["support_score"] - fib["resistance_score"]
        n["fibonacci_support"] = max(0, fs)
        n["fibonacci_resistance"] = max(0, -fs)

        # RSI - MUITO IMPORTANTE para evitar entrar em sobrecompra
        rsi = scores.get("rsi", {})
        if rsi.get("signal") == "buy":
            n["rsi"] = rsi.get("strength", 0)
        elif rsi.get("signal") == "sell":
            n["rsi"] = -rsi.get("strength", 0)
        else:
            n["rsi"] = 0

        # Volume - confirma força do movimento
        vol = scores.get("volume", {})
        if vol.get("signal") == "buy":
            n["volume"] = vol.get("strength", 0)
        elif vol.get("signal") == "sell":
            n["volume"] = -vol.get("strength", 0)
        else:
            n["volume"] = vol.get("strength", 0)  # Pode ser negativo se volume baixo

        return n

    # --------------------------------------------------------
    # CONFLUÊNCIA MULTI-TIMEFRAME
    # --------------------------------------------------------
    def calculate_confluence(self, scores_by_tf: Dict[str, Dict]) -> Dict:
        tf_weights = {"execution": 0.40, "confirmation": 0.35, "trend": 0.25}
        combined = {}
        details = {}

        for tf_name, scores in scores_by_tf.items():
            norm = self._normalize(scores)
            w = tf_weights.get(tf_name, 0.33)
            details[tf_name] = norm
            for ind, score in norm.items():
                combined[ind] = combined.get(ind, 0) + score * w

        # Score final ponderado
        final = sum(combined[k] * self.weights.get(k, 0.1) for k in combined)
        total_w = sum(self.weights.values())
        if total_w > 0:
            final /= total_w

        direction = "long" if final > 0 else "short"
        agreeing = sum(
            1 for s in combined.values()
            if (s > 0.1 and direction == "long") or (s < -0.1 and direction == "short")
        )

        confidence = abs(final)
        if agreeing < self.min_agree:
            confidence *= 0.5

        return {
            "direction": direction,
            "confluence_score": final,
            "confidence": min(confidence, 1.0),
            "agreeing_indicators": agreeing,
            "combined_scores": combined,
            "details": details,
        }

    # --------------------------------------------------------
    # STOP LOSS DINÂMICO
    # --------------------------------------------------------
    def calculate_stop_loss(self, price: float, direction: str,
                            scores: Dict, df) -> float:
        df_calc = calculate_all(df.copy())
        last = df_calc.iloc[-1]
        candidates = []

        if config.STOP_LOSS_TYPE == "fixed":
            pct = config.FIXED_STOP_LOSS_PCT
            return price * (1 - pct) if direction == "long" else price * (1 + pct)

        # Kumo
        if pd.notna(last.get("kumo_bottom")) and pd.notna(last.get("kumo_top")):
            if direction == "long":
                candidates.append(last["kumo_bottom"] * 0.998)
            else:
                candidates.append(last["kumo_top"] * 1.002)

        # Kijun
        if pd.notna(last.get("kijun_sen")):
            if direction == "long":
                candidates.append(last["kijun_sen"] * 0.995)
            else:
                candidates.append(last["kijun_sen"] * 1.005)

        # Fibonacci
        fib_levels = scores.get("fibonacci", {}).get("levels", {})
        if fib_levels:
            sorted_lvls = sorted(fib_levels.values())
            if direction == "long":
                below = [l for l in sorted_lvls if l < price]
                if below:
                    candidates.append(below[-1] * 0.998)
            else:
                above = [l for l in sorted_lvls if l > price]
                if above:
                    candidates.append(above[0] * 1.002)

        # ATR fallback
        if len(df) > 14:
            tr = pd.concat([
                df["high"] - df["low"],
                abs(df["high"] - df["close"].shift(1)),
                abs(df["low"] - df["close"].shift(1)),
            ], axis=1).max(axis=1)
            atr = tr.rolling(14).mean().iloc[-1]
            if direction == "long":
                candidates.append(price - 2.0 * atr)
            else:
                candidates.append(price + 2.0 * atr)

        if not candidates:
            pct = config.FIXED_STOP_LOSS_PCT
            return price * (1 - pct) if direction == "long" else price * (1 + pct)

        return max(candidates) if direction == "long" else min(candidates)

    # --------------------------------------------------------
    # TAKE PROFITS
    # --------------------------------------------------------
    def calculate_take_profits(self, price: float, direction: str,
                                stop_loss: float, scores: Dict) -> List[float]:
        risk = abs(price - stop_loss)
        tps = []
        for ext in config.TAKE_PROFIT_LEVELS:
            if direction == "long":
                tps.append(price + risk * ext * 2)
            else:
                tps.append(price - risk * ext * 2)

        if direction == "long":
            tps = sorted(set(tps))
        else:
            tps = sorted(set(tps), reverse=True)
        return tps[:3]

    # --------------------------------------------------------
    # GERA SINAL
    # --------------------------------------------------------
    def generate_signal(self, symbol: str, scores_by_tf: Dict[str, Dict],
                        exec_df) -> Optional[TradeSignal]:
        conf = self.calculate_confluence(scores_by_tf)

        # Usa threshold do learning engine se disponivel
        threshold = self.threshold
        if self.learning:
            threshold = self.learning.get_effective_threshold()
            # Usa pesos ajustados pelo aprendizado
            learned_weights = self.learning.get_effective_weights()
            if learned_weights:
                self.weights = learned_weights

        self.last_rejection_reason = ""  # Reseta motivo

        if conf["confidence"] < threshold:
            self.last_rejection_reason = "low_confidence"
            return None
        if conf["agreeing_indicators"] < self.min_agree:
            self.last_rejection_reason = "few_indicators"
            return None

        price = exec_df.iloc[-1]["close"]
        direction = conf["direction"]
        exec_scores = scores_by_tf.get("execution", {})

        sl = self.calculate_stop_loss(price, direction, exec_scores, exec_df)
        tps = self.calculate_take_profits(price, direction, sl, exec_scores)

        risk = abs(price - sl)
        reward = abs(tps[0] - price) if tps else risk
        rr = reward / risk if risk > 0 else 0

        if rr < config.MIN_RISK_REWARD:
            self.last_rejection_reason = "low_rr"
            return None

        # FILTRO RSI: não compra em sobrecompra, não vende em sobrevenda
        rsi_data = exec_scores.get("rsi", {})
        rsi_value = rsi_data.get("value", 50)
        if direction == "long" and rsi_value > 70:
            self.last_rejection_reason = "rsi_filter"
            return None  # Não comprar em sobrecompra
        if direction == "short" and rsi_value < 30:
            self.last_rejection_reason = "rsi_filter"
            return None  # Não vender em sobrevenda

        # FILTRO VOLUME: evita entrar sem volume
        vol_data = exec_scores.get("volume", {})
        vol_ratio = vol_data.get("ratio", 1.0)
        if vol_ratio < 0.5:
            self.last_rejection_reason = "volume_filter"
            return None  # Volume muito baixo, pode ser armadilha

        return TradeSignal(
            timestamp=datetime.utcnow().isoformat(),
            symbol=symbol, direction=direction,
            confidence=conf["confidence"], entry_price=price,
            stop_loss=sl, take_profits=tps,
            timeframe=config.TIMEFRAMES[config.TRADE_MODE]["execution"],
            indicators_detail=conf["combined_scores"],
            confluence_score=conf["confluence_score"],
            risk_reward_ratio=rr,
        )

    # --------------------------------------------------------
    # REGISTRO E APRENDIZADO
    # --------------------------------------------------------
    def record_result(self, signal: TradeSignal, result: str, pnl_pct: float):
        self.trade_history.append({**signal.to_dict(), "result": result, "pnl_pct": pnl_pct})
        self._save_history()
        self._adapt_weights()

    def _adapt_weights(self):
        if len(self.trade_history) < 10:
            return
        recent = self.trade_history[-50:]
        perf = {}
        for t in recent:
            for ind, score in t.get("indicators_detail", {}).items():
                if ind not in perf:
                    perf[ind] = {"correct": 0, "total": 0}
                perf[ind]["total"] += 1
                if t.get("result") == "win":
                    if (t["direction"] == "long" and score > 0) or (t["direction"] == "short" and score < 0):
                        perf[ind]["correct"] += 1
        for ind, p in perf.items():
            if p["total"] > 0 and ind in self.weights:
                acc = p["correct"] / p["total"]
                self.weights[ind] = max(0.05, min(0.40, self.weights[ind] * 0.8 + acc * 0.2))
        total = sum(self.weights.values())
        if total > 0:
            self.weights = {k: v / total for k, v in self.weights.items()}

    def get_report(self) -> Dict:
        if not self.trade_history:
            return {"total": 0}
        wins = sum(1 for t in self.trade_history if t.get("result") == "win")
        pnls = [t.get("pnl_pct", 0) for t in self.trade_history]
        return {
            "total": len(self.trade_history), "wins": wins,
            "losses": len(self.trade_history) - wins,
            "win_rate": f"{wins/len(self.trade_history)*100:.1f}%",
            "total_pnl": f"{sum(pnls):.2f}%",
            "avg_pnl": f"{np.mean(pnls):.2f}%",
        }


# Need pandas import for stop loss calculation
import pandas as pd
