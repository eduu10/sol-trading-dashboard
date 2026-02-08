"""
Motor de Aprendizado Continuo
================================
Registra TODAS as analises, aprende com acertos/erros,
faz "shadow trades" para validar estrategias, e ajusta
agressividade automaticamente.

O bot aprende diariamente como um day trader profissional.
"""

import json
import os
import logging
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict
import config

logger = logging.getLogger("LearningEngine")

# Arquivos de dados
ANALYSIS_LOG_FILE = "analysis_log.json"
SHADOW_TRADES_FILE = "shadow_trades.json"
LEARNING_STATE_FILE = "learning_state.json"
DAILY_REPORT_FILE = "daily_reports.json"


@dataclass
class AnalysisRecord:
    """Registro completo de uma analise."""
    timestamp: str
    analysis_number: int
    price: float
    direction: str
    confidence: float
    confluence_score: float
    agreeing_indicators: int
    total_indicators: int
    combined_scores: Dict
    rsi_value: float
    volume_ratio: float
    # Motivo de rejeicao (se nao gerou sinal)
    signal_generated: bool
    rejection_reason: str  # "", "low_confidence", "few_indicators", "low_rr", "rsi_filter", "volume_filter"
    # Precos futuros (preenchidos depois)
    price_after_5m: float = 0.0
    price_after_15m: float = 0.0
    price_after_30m: float = 0.0
    price_after_1h: float = 0.0
    # O que teria acontecido
    would_have_profited: Optional[bool] = None
    potential_pnl_pct: float = 0.0


@dataclass
class ShadowTrade:
    """Trade virtual para testar decisoes sem arriscar capital."""
    id: str
    timestamp: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profits: List[float]
    confidence: float
    confluence_score: float
    indicators: Dict
    # Resultado
    status: str = "open"  # "open", "win_tp1", "win_tp2", "win_tp3", "loss_sl"
    exit_price: float = 0.0
    exit_time: str = ""
    pnl_pct: float = 0.0
    max_favorable: float = 0.0  # Maximo a favor antes de fechar
    max_adverse: float = 0.0    # Maximo contra antes de fechar


class LearningEngine:
    """Motor de aprendizado que registra tudo e melhora continuamente."""

    def __init__(self):
        self.analysis_log: List[Dict] = []
        self.shadow_trades: List[Dict] = []
        self.state: Dict = {}
        self.daily_reports: List[Dict] = []

        self._load_all()
        self._ensure_state()

    # --------------------------------------------------------
    # PERSISTENCIA
    # --------------------------------------------------------
    def _load_all(self):
        for attr, filepath in [
            ("analysis_log", ANALYSIS_LOG_FILE),
            ("shadow_trades", SHADOW_TRADES_FILE),
            ("state", LEARNING_STATE_FILE),
            ("daily_reports", DAILY_REPORT_FILE),
        ]:
            try:
                if os.path.exists(filepath):
                    with open(filepath) as f:
                        setattr(self, attr, json.load(f))
            except (json.JSONDecodeError, Exception) as e:
                logger.warning(f"Erro ao carregar {filepath}: {e}")

    def _save(self, attr: str, filepath: str):
        try:
            data = getattr(self, attr)
            with open(filepath, "w") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Erro ao salvar {filepath}: {e}")

    def _save_analysis_log(self):
        # Manter apenas ultimos 7 dias (~10000 registros max)
        if len(self.analysis_log) > 10000:
            self.analysis_log = self.analysis_log[-10000:]
        self._save("analysis_log", ANALYSIS_LOG_FILE)

    def _save_shadow_trades(self):
        self._save("shadow_trades", SHADOW_TRADES_FILE)

    def _save_state(self):
        self._save("state", LEARNING_STATE_FILE)

    def _save_daily_reports(self):
        self._save("daily_reports", DAILY_REPORT_FILE)

    def _ensure_state(self):
        """Inicializa estado se necessario."""
        defaults = {
            "total_analyses": 0,
            "total_shadow_trades": 0,
            "shadow_wins": 0,
            "shadow_losses": 0,
            "missed_opportunities": 0,  # Vezes que NAO entrou mas teria lucrado
            "dodged_bullets": 0,        # Vezes que NAO entrou e teria perdido
            "false_entries": 0,         # Vezes que ENTROU e perdeu
            "correct_entries": 0,       # Vezes que ENTROU e ganhou
            "last_daily_review": "",
            "current_risk_level": 1.0,  # 1.0 = normal, 0.5 = conservador, 1.5 = agressivo
            "confidence_adjustment": 0.0,  # Ajuste no threshold de confianca
            "indicator_accuracy": {},   # Precisao de cada indicador
            "best_conditions": [],      # Condicoes que mais deram lucro
            "worst_conditions": [],     # Condicoes que mais deram perda
            "streak": 0,               # Sequencia de acertos (positivo) ou erros (negativo)
            "max_streak": 0,
            "days_learning": 0,
            "total_potential_pnl": 0.0, # PnL potencial total (se tivesse entrado em tudo)
        }
        for k, v in defaults.items():
            if k not in self.state:
                self.state[k] = v

    # --------------------------------------------------------
    # REGISTRA ANALISE (chamado a cada ciclo)
    # --------------------------------------------------------
    def record_analysis(self, price: float, conf: Dict, scores_by_tf: Dict,
                        signal_generated: bool, rejection_reason: str = "",
                        analysis_number: int = 0):
        """Registra CADA analise feita, com ou sem sinal."""
        exec_scores = scores_by_tf.get("execution", {})

        record = {
            "timestamp": datetime.utcnow().isoformat(),
            "analysis_number": analysis_number,
            "price": price,
            "direction": conf["direction"],
            "confidence": round(conf["confidence"], 4),
            "confluence_score": round(conf["confluence_score"], 4),
            "agreeing_indicators": conf["agreeing_indicators"],
            "total_indicators": len(conf["combined_scores"]),
            "combined_scores": {k: round(v, 4) for k, v in conf["combined_scores"].items()},
            "rsi_value": round(exec_scores.get("rsi", {}).get("value", 50), 2),
            "volume_ratio": round(exec_scores.get("volume", {}).get("ratio", 1.0), 3),
            "signal_generated": signal_generated,
            "rejection_reason": rejection_reason,
            # Precos futuros (serao preenchidos depois)
            "price_after_5m": 0.0,
            "price_after_15m": 0.0,
            "price_after_30m": 0.0,
            "price_after_1h": 0.0,
            "would_have_profited": None,
            "potential_pnl_pct": 0.0,
        }

        self.analysis_log.append(record)
        self.state["total_analyses"] = self.state.get("total_analyses", 0) + 1
        self._save_analysis_log()

        logger.info(
            f"[LEARN] Analise #{analysis_number} registrada | "
            f"{'SINAL' if signal_generated else 'SEM SINAL'} | "
            f"{conf['direction'].upper()} {conf['confidence']:.0%} | "
            f"Motivo: {rejection_reason or 'n/a'}"
        )

    # --------------------------------------------------------
    # ATUALIZA PRECOS FUTUROS (retroativamente)
    # --------------------------------------------------------
    def update_future_prices(self, current_price: float):
        """
        Atualiza precos futuros das analises passadas.
        Chamado a cada ciclo, preenche os campos price_after_Xm.
        """
        now = datetime.utcnow()
        updated = 0

        for record in self.analysis_log:
            if record.get("would_have_profited") is not None:
                continue  # Ja avaliado

            try:
                rec_time = datetime.fromisoformat(record["timestamp"])
            except (ValueError, KeyError):
                continue

            elapsed = (now - rec_time).total_seconds() / 60  # minutos

            # Preenche precos conforme o tempo passa
            if elapsed >= 5 and record["price_after_5m"] == 0:
                record["price_after_5m"] = current_price
            if elapsed >= 15 and record["price_after_15m"] == 0:
                record["price_after_15m"] = current_price
            if elapsed >= 30 and record["price_after_30m"] == 0:
                record["price_after_30m"] = current_price
            if elapsed >= 60 and record["price_after_1h"] == 0:
                record["price_after_1h"] = current_price
                updated += 1

                # Agora podemos avaliar: teria dado lucro?
                entry = record["price"]
                direction = record["direction"]

                if direction == "long":
                    best_price = max(
                        record["price_after_5m"],
                        record["price_after_15m"],
                        record["price_after_30m"],
                        record["price_after_1h"],
                    )
                    pnl = ((best_price - entry) / entry) * 100
                else:
                    worst_price = min(
                        record["price_after_5m"],
                        record["price_after_15m"],
                        record["price_after_30m"],
                        record["price_after_1h"],
                    )
                    pnl = ((entry - worst_price) / entry) * 100

                record["potential_pnl_pct"] = round(pnl, 3)
                record["would_have_profited"] = pnl > 0.5  # Pelo menos 0.5% de lucro

                # Atualiza contadores
                if not record["signal_generated"]:
                    if record["would_have_profited"]:
                        self.state["missed_opportunities"] = self.state.get("missed_opportunities", 0) + 1
                    else:
                        self.state["dodged_bullets"] = self.state.get("dodged_bullets", 0) + 1

        if updated > 0:
            self._save_analysis_log()
            self._save_state()
            logger.info(f"[LEARN] {updated} analises avaliadas retroativamente")

    # --------------------------------------------------------
    # SHADOW TRADES (trades virtuais de teste)
    # --------------------------------------------------------
    def open_shadow_trade(self, conf: Dict, price: float, scores_by_tf: Dict,
                          stop_loss: float, take_profits: List[float]):
        """
        Abre um trade virtual para testar a decisao.
        Chamado quando a confianca esta PERTO do threshold.
        """
        trade = {
            "id": f"shadow_{int(datetime.utcnow().timestamp())}",
            "timestamp": datetime.utcnow().isoformat(),
            "direction": conf["direction"],
            "entry_price": price,
            "stop_loss": stop_loss,
            "take_profits": take_profits,
            "confidence": round(conf["confidence"], 4),
            "confluence_score": round(conf["confluence_score"], 4),
            "indicators": {k: round(v, 4) for k, v in conf["combined_scores"].items()},
            "status": "open",
            "exit_price": 0.0,
            "exit_time": "",
            "pnl_pct": 0.0,
            "max_favorable": 0.0,
            "max_adverse": 0.0,
        }

        self.shadow_trades.append(trade)
        self.state["total_shadow_trades"] = self.state.get("total_shadow_trades", 0) + 1
        self._save_shadow_trades()
        self._save_state()

        logger.info(
            f"[SHADOW] Trade virtual aberto: {conf['direction'].upper()} "
            f"${price:,.2f} | Conf: {conf['confidence']:.0%} | "
            f"SL: ${stop_loss:,.2f} | TP1: ${take_profits[0]:,.2f}"
        )
        return trade

    def update_shadow_trades(self, current_price: float):
        """Atualiza shadow trades com preco atual. Fecha se bateu SL/TP."""
        for trade in self.shadow_trades:
            if trade["status"] != "open":
                continue

            entry = trade["entry_price"]
            direction = trade["direction"]

            # Atualiza maximos
            if direction == "long":
                favorable = ((current_price - entry) / entry) * 100
                adverse = ((entry - current_price) / entry) * 100
            else:
                favorable = ((entry - current_price) / entry) * 100
                adverse = ((current_price - entry) / entry) * 100

            trade["max_favorable"] = max(trade.get("max_favorable", 0), favorable)
            trade["max_adverse"] = max(trade.get("max_adverse", 0), adverse)

            # Verifica Stop Loss
            if direction == "long" and current_price <= trade["stop_loss"]:
                trade["status"] = "loss_sl"
                trade["exit_price"] = current_price
                trade["exit_time"] = datetime.utcnow().isoformat()
                trade["pnl_pct"] = round(((current_price - entry) / entry) * 100, 3)
                self.state["shadow_losses"] = self.state.get("shadow_losses", 0) + 1
                self._update_streak(False)
                logger.info(f"[SHADOW] LOSS: {trade['id']} | PnL: {trade['pnl_pct']:+.2f}%")

            elif direction == "short" and current_price >= trade["stop_loss"]:
                trade["status"] = "loss_sl"
                trade["exit_price"] = current_price
                trade["exit_time"] = datetime.utcnow().isoformat()
                trade["pnl_pct"] = round(((entry - current_price) / entry) * 100, 3)
                self.state["shadow_losses"] = self.state.get("shadow_losses", 0) + 1
                self._update_streak(False)
                logger.info(f"[SHADOW] LOSS: {trade['id']} | PnL: {trade['pnl_pct']:+.2f}%")

            else:
                # Verifica Take Profits
                for i, tp in enumerate(trade["take_profits"]):
                    if direction == "long" and current_price >= tp:
                        trade["status"] = f"win_tp{i+1}"
                        trade["exit_price"] = current_price
                        trade["exit_time"] = datetime.utcnow().isoformat()
                        trade["pnl_pct"] = round(((current_price - entry) / entry) * 100, 3)
                        self.state["shadow_wins"] = self.state.get("shadow_wins", 0) + 1
                        self._update_streak(True)
                        logger.info(f"[SHADOW] WIN TP{i+1}: {trade['id']} | PnL: {trade['pnl_pct']:+.2f}%")
                        break
                    elif direction == "short" and current_price <= tp:
                        trade["status"] = f"win_tp{i+1}"
                        trade["exit_price"] = current_price
                        trade["exit_time"] = datetime.utcnow().isoformat()
                        trade["pnl_pct"] = round(((entry - current_price) / entry) * 100, 3)
                        self.state["shadow_wins"] = self.state.get("shadow_wins", 0) + 1
                        self._update_streak(True)
                        logger.info(f"[SHADOW] WIN TP{i+1}: {trade['id']} | PnL: {trade['pnl_pct']:+.2f}%")
                        break

            # Timeout: fecha shadow trade apos 4 horas
            try:
                opened = datetime.fromisoformat(trade["timestamp"])
                if (datetime.utcnow() - opened).total_seconds() > 4 * 3600:
                    if trade["status"] == "open":
                        if direction == "long":
                            trade["pnl_pct"] = round(((current_price - entry) / entry) * 100, 3)
                        else:
                            trade["pnl_pct"] = round(((entry - current_price) / entry) * 100, 3)
                        trade["status"] = "timeout"
                        trade["exit_price"] = current_price
                        trade["exit_time"] = datetime.utcnow().isoformat()
                        if trade["pnl_pct"] > 0:
                            self.state["shadow_wins"] = self.state.get("shadow_wins", 0) + 1
                            self._update_streak(True)
                        else:
                            self.state["shadow_losses"] = self.state.get("shadow_losses", 0) + 1
                            self._update_streak(False)
                        logger.info(f"[SHADOW] TIMEOUT: {trade['id']} | PnL: {trade['pnl_pct']:+.2f}%")
            except (ValueError, KeyError):
                pass

        self._save_shadow_trades()
        self._save_state()

    def _update_streak(self, won: bool):
        """Atualiza sequencia de acertos/erros."""
        streak = self.state.get("streak", 0)
        if won:
            self.state["streak"] = max(0, streak) + 1
        else:
            self.state["streak"] = min(0, streak) - 1
        self.state["max_streak"] = max(
            self.state.get("max_streak", 0),
            abs(self.state["streak"])
        )

    # --------------------------------------------------------
    # REVISAO DIARIA (aprendizado)
    # --------------------------------------------------------
    def daily_review(self) -> Optional[Dict]:
        """
        Faz revisao diaria: analisa o que aconteceu, ajusta parametros.
        Retorna relatorio ou None se ja fez hoje.
        """
        today = datetime.utcnow().strftime("%Y-%m-%d")
        if self.state.get("last_daily_review") == today:
            return None

        logger.info("[LEARN] Iniciando revisao diaria...")

        # Coleta analises das ultimas 24h
        now = datetime.utcnow()
        cutoff = now - timedelta(hours=24)
        recent = []
        for r in self.analysis_log:
            try:
                t = datetime.fromisoformat(r["timestamp"])
                if t >= cutoff:
                    recent.append(r)
            except (ValueError, KeyError):
                continue

        if len(recent) < 10:
            logger.info("[LEARN] Poucos dados para revisao diaria")
            return None

        # Analisa resultados
        evaluated = [r for r in recent if r.get("would_have_profited") is not None]
        if not evaluated:
            return None

        total = len(evaluated)
        would_profit = sum(1 for r in evaluated if r["would_have_profited"])
        would_loss = total - would_profit

        # Analises que geraram sinal
        signaled = [r for r in evaluated if r["signal_generated"]]
        signaled_profit = sum(1 for r in signaled if r["would_have_profited"])

        # Analises rejeitadas que teriam dado lucro (oportunidades perdidas)
        rejected = [r for r in evaluated if not r["signal_generated"]]
        rejected_profit = sum(1 for r in rejected if r["would_have_profited"])
        rejected_loss = sum(1 for r in rejected if not r["would_have_profited"])

        # Precisao dos indicadores
        indicator_accuracy = self._calc_indicator_accuracy(evaluated)

        # Melhores condicoes para lucro
        best_conditions = self._find_best_conditions(evaluated)

        # Shadow trades performance
        shadow_closed = [t for t in self.shadow_trades if t["status"] != "open"]
        shadow_wins = sum(1 for t in shadow_closed if t.get("pnl_pct", 0) > 0)
        shadow_total = len(shadow_closed)
        shadow_wr = (shadow_wins / shadow_total * 100) if shadow_total > 0 else 0

        # AJUSTA PARAMETROS baseado no aprendizado
        adjustments = self._calculate_adjustments(
            evaluated, rejected_profit, rejected_loss,
            shadow_wr, shadow_total
        )

        report = {
            "date": today,
            "total_analyses": total,
            "would_profit": would_profit,
            "would_loss": would_loss,
            "accuracy": round(would_profit / total * 100, 1) if total > 0 else 0,
            "signals_generated": len(signaled),
            "signals_correct": signaled_profit,
            "missed_opportunities": rejected_profit,
            "dodged_bullets": rejected_loss,
            "shadow_trades": shadow_total,
            "shadow_win_rate": round(shadow_wr, 1),
            "indicator_accuracy": indicator_accuracy,
            "best_conditions": best_conditions,
            "adjustments": adjustments,
            "risk_level": self.state["current_risk_level"],
            "streak": self.state["streak"],
            "days_learning": self.state.get("days_learning", 0) + 1,
        }

        self.daily_reports.append(report)
        self.state["last_daily_review"] = today
        self.state["days_learning"] = report["days_learning"]
        self.state["indicator_accuracy"] = indicator_accuracy
        self.state["best_conditions"] = best_conditions

        self._save_daily_reports()
        self._save_state()

        logger.info(
            f"[LEARN] Revisao diaria completa | "
            f"Precisao: {report['accuracy']:.0f}% | "
            f"Oportunidades perdidas: {rejected_profit} | "
            f"Balas desviadas: {rejected_loss} | "
            f"Risk Level: {self.state['current_risk_level']:.2f}"
        )

        return report

    def _calc_indicator_accuracy(self, evaluated: List[Dict]) -> Dict:
        """Calcula precisao de cada indicador."""
        accuracy = {}
        for record in evaluated:
            scores = record.get("combined_scores", {})
            profited = record.get("would_have_profited", False)
            direction = record.get("direction", "long")

            for ind, score in scores.items():
                if ind not in accuracy:
                    accuracy[ind] = {"correct": 0, "wrong": 0, "total": 0}

                accuracy[ind]["total"] += 1

                # Indicador concordou com a direcao que teria dado lucro?
                indicator_says_long = score > 0.1
                indicator_says_short = score < -0.1

                if profited:
                    if (direction == "long" and indicator_says_long) or \
                       (direction == "short" and indicator_says_short):
                        accuracy[ind]["correct"] += 1
                    elif indicator_says_long or indicator_says_short:
                        accuracy[ind]["wrong"] += 1
                else:
                    if (direction == "long" and indicator_says_short) or \
                       (direction == "short" and indicator_says_long):
                        accuracy[ind]["correct"] += 1  # Corretamente contrario
                    elif indicator_says_long or indicator_says_short:
                        accuracy[ind]["wrong"] += 1

        # Converte para porcentagem
        result = {}
        for ind, data in accuracy.items():
            total_decisions = data["correct"] + data["wrong"]
            if total_decisions > 0:
                result[ind] = round(data["correct"] / total_decisions * 100, 1)
        return result

    def _find_best_conditions(self, evaluated: List[Dict]) -> List[Dict]:
        """Encontra as condicoes que mais deram lucro."""
        conditions = []

        # Agrupa por faixa de RSI
        rsi_ranges = {"<30": [], "30-50": [], "50-70": [], ">70": []}
        for r in evaluated:
            rsi = r.get("rsi_value", 50)
            if rsi < 30:
                rsi_ranges["<30"].append(r)
            elif rsi < 50:
                rsi_ranges["30-50"].append(r)
            elif rsi < 70:
                rsi_ranges["50-70"].append(r)
            else:
                rsi_ranges[">70"].append(r)

        for rsi_range, records in rsi_ranges.items():
            if len(records) >= 3:
                wins = sum(1 for r in records if r.get("would_have_profited"))
                wr = wins / len(records) * 100
                avg_pnl = np.mean([r.get("potential_pnl_pct", 0) for r in records])
                conditions.append({
                    "type": "rsi_range",
                    "value": rsi_range,
                    "win_rate": round(wr, 1),
                    "avg_pnl": round(float(avg_pnl), 3),
                    "samples": len(records),
                })

        # Agrupa por faixa de confianca
        conf_ranges = {"<25%": [], "25-50%": [], "50-75%": [], ">75%": []}
        for r in evaluated:
            conf = r.get("confidence", 0) * 100
            if conf < 25:
                conf_ranges["<25%"].append(r)
            elif conf < 50:
                conf_ranges["25-50%"].append(r)
            elif conf < 75:
                conf_ranges["50-75%"].append(r)
            else:
                conf_ranges[">75%"].append(r)

        for conf_range, records in conf_ranges.items():
            if len(records) >= 3:
                wins = sum(1 for r in records if r.get("would_have_profited"))
                wr = wins / len(records) * 100
                avg_pnl = np.mean([r.get("potential_pnl_pct", 0) for r in records])
                conditions.append({
                    "type": "confidence_range",
                    "value": conf_range,
                    "win_rate": round(wr, 1),
                    "avg_pnl": round(float(avg_pnl), 3),
                    "samples": len(records),
                })

        return sorted(conditions, key=lambda x: x["avg_pnl"], reverse=True)

    # --------------------------------------------------------
    # AJUSTE AUTOMATICO DE PARAMETROS
    # --------------------------------------------------------
    def _calculate_adjustments(self, evaluated, missed_opps, dodged,
                                shadow_wr, shadow_total) -> Dict:
        """
        Calcula ajustes nos parametros baseado no aprendizado.

        REGRA DE OURO: Quanto mais acerta, mais arrisca.
        Mas NUNCA zera o capital (risco maximo = 3% por trade).
        """
        adjustments = {}

        # 1. AJUSTE DE RISCO baseado no desempenho
        current_risk = self.state.get("current_risk_level", 1.0)

        if shadow_total >= 5:
            if shadow_wr >= 70:
                # Muito bom! Aumenta risco gradualmente
                new_risk = min(current_risk * 1.1, 2.0)  # Max 2x
                adjustments["risk_reason"] = f"Shadow WR {shadow_wr:.0f}% >= 70%, aumentando risco"
            elif shadow_wr >= 55:
                # Bom, mantem ou sobe um pouco
                new_risk = min(current_risk * 1.03, 1.5)
                adjustments["risk_reason"] = f"Shadow WR {shadow_wr:.0f}% ok, risco estavel"
            elif shadow_wr >= 40:
                # Mediano, reduz um pouco
                new_risk = max(current_risk * 0.95, 0.5)
                adjustments["risk_reason"] = f"Shadow WR {shadow_wr:.0f}% mediano, reduzindo"
            else:
                # Ruim, reduz bastante mas nunca abaixo de 0.3
                new_risk = max(current_risk * 0.8, 0.3)
                adjustments["risk_reason"] = f"Shadow WR {shadow_wr:.0f}% ruim, protegendo capital"

            self.state["current_risk_level"] = round(new_risk, 3)
            adjustments["risk_level"] = round(new_risk, 3)

        # 2. AJUSTE DO THRESHOLD DE CONFIANCA
        if missed_opps > dodged * 2:
            # Perdendo muitas oportunidades - baixar threshold
            adj = min(0.05, missed_opps * 0.005)
            self.state["confidence_adjustment"] = round(
                max(self.state.get("confidence_adjustment", 0) - adj, -0.20), 3
            )
            adjustments["confidence_reason"] = (
                f"Muitas oportunidades perdidas ({missed_opps}), "
                f"reduzindo threshold"
            )
        elif dodged > missed_opps * 2:
            # Desviando de muitas perdas - esta bom, talvez subir threshold
            adj = min(0.03, dodged * 0.003)
            self.state["confidence_adjustment"] = round(
                min(self.state.get("confidence_adjustment", 0) + adj, 0.15), 3
            )
            adjustments["confidence_reason"] = (
                f"Filtrando bem perdas ({dodged}), "
                f"mantendo/subindo threshold"
            )

        adjustments["confidence_adjustment"] = self.state.get("confidence_adjustment", 0)
        adjustments["effective_threshold"] = round(
            config.CONFLUENCE_THRESHOLD + self.state.get("confidence_adjustment", 0), 3
        )

        # 3. AJUSTE DE PESOS DOS INDICADORES
        ind_accuracy = self.state.get("indicator_accuracy", {})
        weight_changes = {}
        for ind, acc in ind_accuracy.items():
            if ind in config.INDICATOR_WEIGHTS:
                current_w = config.INDICATOR_WEIGHTS[ind]
                if acc >= 65:
                    # Indicador bom, aumenta peso
                    weight_changes[ind] = min(current_w * 1.05, 0.30)
                elif acc < 45:
                    # Indicador ruim, diminui peso
                    weight_changes[ind] = max(current_w * 0.90, 0.03)

        if weight_changes:
            adjustments["weight_changes"] = {
                k: round(v, 4) for k, v in weight_changes.items()
            }

        return adjustments

    # --------------------------------------------------------
    # PARAMETROS EFETIVOS (usados pelo confluence engine)
    # --------------------------------------------------------
    def get_effective_threshold(self) -> float:
        """Retorna threshold de confianca ajustado pelo aprendizado."""
        base = config.CONFLUENCE_THRESHOLD
        adj = self.state.get("confidence_adjustment", 0)
        # Nunca abaixo de 0.20 (20%) nem acima de 0.80 (80%)
        return max(0.20, min(0.80, base + adj))

    def get_effective_risk_per_trade(self) -> float:
        """Retorna risco por trade ajustado pelo nivel de confianca."""
        base = config.RISK_PER_TRADE
        risk_level = self.state.get("current_risk_level", 1.0)
        adjusted = base * risk_level
        # NUNCA mais de 3% por trade (protecao contra zerar)
        return min(adjusted, 0.03)

    def get_effective_weights(self) -> Dict:
        """Retorna pesos ajustados dos indicadores."""
        weights = config.INDICATOR_WEIGHTS.copy()
        ind_accuracy = self.state.get("indicator_accuracy", {})

        for ind, acc in ind_accuracy.items():
            if ind in weights:
                if acc >= 65:
                    weights[ind] = min(weights[ind] * 1.05, 0.30)
                elif acc < 45:
                    weights[ind] = max(weights[ind] * 0.90, 0.03)

        # Normaliza
        total = sum(weights.values())
        if total > 0:
            weights = {k: round(v / total, 4) for k, v in weights.items()}

        return weights

    def should_open_shadow_trade(self, conf: Dict) -> bool:
        """
        Decide se deve abrir um shadow trade.
        Abre quando a confianca esta entre 25% e o threshold (zona cinza).
        """
        threshold = self.get_effective_threshold()
        confidence = conf["confidence"]

        # Zona cinza: perto do threshold mas nao passou
        if 0.25 <= confidence < threshold:
            # Limita a 3 shadow trades abertos
            open_shadows = sum(1 for t in self.shadow_trades if t["status"] == "open")
            return open_shadows < 3

        return False

    # --------------------------------------------------------
    # RELATORIO PARA TELEGRAM
    # --------------------------------------------------------
    def get_telegram_report(self) -> str:
        """Gera relatorio de aprendizado para Telegram."""
        s = self.state
        days = s.get("days_learning", 0)
        risk = s.get("current_risk_level", 1.0)
        threshold = self.get_effective_threshold()
        streak = s.get("streak", 0)

        shadow_total = s.get("shadow_wins", 0) + s.get("shadow_losses", 0)
        shadow_wr = (
            s.get("shadow_wins", 0) / shadow_total * 100
            if shadow_total > 0 else 0
        )

        missed = s.get("missed_opportunities", 0)
        dodged = s.get("dodged_bullets", 0)

        # Barra de nivel de risco
        risk_bar_filled = int(risk * 5)
        risk_bar = "█" * min(risk_bar_filled, 10) + "░" * max(0, 10 - risk_bar_filled)

        report = (
            f"🧠 *APRENDIZADO DO BOT*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📅 Dias aprendendo: *{days}*\n"
            f"📊 Analises registradas: *{s.get('total_analyses', 0)}*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 *Shadow Trades:*\n"
            f"  Total: {shadow_total}\n"
            f"  Win Rate: {shadow_wr:.0f}%\n"
            f"  Wins: {s.get('shadow_wins', 0)} | Losses: {s.get('shadow_losses', 0)}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📈 *Decisoes:*\n"
            f"  Oportunidades perdidas: {missed}\n"
            f"  Balas desviadas: {dodged}\n"
            f"  Sequencia: {'🟢' if streak > 0 else '🔴'} {abs(streak)}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⚙️ *Parametros Atuais:*\n"
            f"  Risco: [{risk_bar}] {risk:.1f}x\n"
            f"  Threshold: {threshold:.0%}\n"
            f"  Risco/Trade: {self.get_effective_risk_per_trade()*100:.1f}%\n"
        )

        # Top indicadores
        ind_acc = s.get("indicator_accuracy", {})
        if ind_acc:
            sorted_ind = sorted(ind_acc.items(), key=lambda x: x[1], reverse=True)
            report += f"━━━━━━━━━━━━━━━━━━━━\n"
            report += f"🏆 *Precisao Indicadores:*\n"
            for ind, acc in sorted_ind[:5]:
                emoji = "🟢" if acc >= 60 else "🔴" if acc < 45 else "🟡"
                report += f"  {emoji} {ind}: {acc:.0f}%\n"

        return report

    def get_daily_summary(self) -> Optional[str]:
        """Retorna resumo diario se disponivel."""
        if not self.daily_reports:
            return None

        r = self.daily_reports[-1]
        return (
            f"📊 *RESUMO DIARIO ({r['date']})*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Analises: {r['total_analyses']}\n"
            f"Precisao: {r['accuracy']:.0f}%\n"
            f"Sinais gerados: {r['signals_generated']}\n"
            f"Sinais corretos: {r['signals_correct']}\n"
            f"Oportunidades perdidas: {r['missed_opportunities']}\n"
            f"Perdas evitadas: {r['dodged_bullets']}\n"
            f"Shadow WR: {r['shadow_win_rate']:.0f}%\n"
            f"Risco atual: {r['risk_level']:.1f}x\n"
        )
