"""
Strategy Agents - Agentes adaptativos para cada estrategia
============================================================
Cada agente analisa o historico de trades reais da sua estrategia
e ajusta parametros (TP/SL, filtros, tamanho) para melhorar performance.

O agente aprende com:
- Win rate recente vs geral
- PnL medio por trade
- Horarios com melhor performance
- Sequencias de wins/losses
- Drawdown maximo
- Correlacao entre sim_pnl e pnl real
"""

import json
import time
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("StrategyAgents")

BR_TZ = timezone(timedelta(hours=-3))

AGENTS_FILE = os.path.join(os.path.dirname(__file__), "agents_state.json")

# Minimo de trades para comecar a ajustar
MIN_TRADES_TO_ADAPT = 10


class StrategyAgent:
    """Agente adaptativo para uma estrategia individual."""

    def __init__(self, strategy_key: str):
        self.key = strategy_key
        self.confidence = 0.5  # 0-1, comeca neutro
        self.adjustments = {}  # Ajustes feitos pelo agente
        self.analysis = {}     # Ultima analise
        self.last_analyzed = 0
        self.decisions_made = 0
        self.signals_approved = 0
        self.signals_rejected = 0
        self.streak = 0  # Positivo = wins, negativo = losses

    def analyze_history(self, trade_history: List[Dict], allocation: Dict) -> Dict:
        """Analisa historico de trades e retorna metricas."""
        if not trade_history:
            self.analysis = {"status": "sem_dados", "trades": 0}
            return self.analysis

        total = len(trade_history)
        wins = [t for t in trade_history if (t.get("pnl", 0)) > 0]
        losses = [t for t in trade_history if (t.get("pnl", 0)) < 0]
        neutral = [t for t in trade_history if (t.get("pnl", 0)) == 0]

        win_rate = len(wins) / total if total > 0 else 0
        total_pnl = sum(t.get("pnl", 0) for t in trade_history)
        avg_pnl = total_pnl / total if total > 0 else 0
        avg_win = sum(t.get("pnl", 0) for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t.get("pnl", 0) for t in losses) / len(losses) if losses else 0

        # Profit factor
        gross_profit = sum(t.get("pnl", 0) for t in wins)
        gross_loss = abs(sum(t.get("pnl", 0) for t in losses))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf') if gross_profit > 0 else 0

        # Ultimos N trades (performance recente)
        recent_n = min(20, total)
        recent = trade_history[-recent_n:]
        recent_wins = [t for t in recent if (t.get("pnl", 0)) > 0]
        recent_win_rate = len(recent_wins) / len(recent) if recent else 0
        recent_pnl = sum(t.get("pnl", 0) for t in recent)

        # Streak atual (sequencia de wins ou losses)
        streak = 0
        for t in reversed(trade_history):
            pnl = t.get("pnl", 0)
            if pnl > 0:
                if streak >= 0:
                    streak += 1
                else:
                    break
            elif pnl < 0:
                if streak <= 0:
                    streak -= 1
                else:
                    break
            else:
                break
        self.streak = streak

        # Drawdown maximo
        peak = 0
        running = 0
        max_dd = 0
        for t in trade_history:
            running += t.get("pnl", 0)
            if running > peak:
                peak = running
            dd = peak - running
            if dd > max_dd:
                max_dd = dd

        # Analise por horario (UTC-3)
        hour_pnl = {}
        for t in trade_history:
            ts = t.get("time", 0)
            if ts:
                h = datetime.fromtimestamp(ts, BR_TZ).hour
                if h not in hour_pnl:
                    hour_pnl[h] = {"pnl": 0, "count": 0, "wins": 0}
                hour_pnl[h]["pnl"] += t.get("pnl", 0)
                hour_pnl[h]["count"] += 1
                if t.get("pnl", 0) > 0:
                    hour_pnl[h]["wins"] += 1

        best_hours = sorted(hour_pnl.items(), key=lambda x: x[1]["pnl"], reverse=True)[:3]
        worst_hours = sorted(hour_pnl.items(), key=lambda x: x[1]["pnl"])[:3]

        # Correlacao sim vs real (a simulacao preve bem?)
        sim_real_corr = 0
        corr_trades = [t for t in trade_history if t.get("sim_pnl_pct") is not None]
        if len(corr_trades) >= 5:
            sim_correct = sum(1 for t in corr_trades
                              if (t.get("sim_pnl_pct", 0) > 0) == (t.get("pnl", 0) > 0))
            sim_real_corr = sim_correct / len(corr_trades)

        # Analise por token/sinal
        signal_perf = {}
        for t in trade_history:
            sig = t.get("signal", "unknown")
            if sig not in signal_perf:
                signal_perf[sig] = {"pnl": 0, "count": 0, "wins": 0}
            signal_perf[sig]["pnl"] += t.get("pnl", 0)
            signal_perf[sig]["count"] += 1
            if t.get("pnl", 0) > 0:
                signal_perf[sig]["wins"] += 1

        best_signals = sorted(signal_perf.items(), key=lambda x: x[1]["pnl"], reverse=True)[:5]
        worst_signals = sorted(signal_perf.items(), key=lambda x: x[1]["pnl"])[:3]

        # Calcula confianca do agente (0 a 1)
        # Baseada em: win_rate, profit_factor, consistencia, recencia
        conf = 0.3  # base
        if win_rate > 0.5:
            conf += 0.15
        if win_rate > 0.6:
            conf += 0.1
        if profit_factor > 1.5:
            conf += 0.15
        if recent_win_rate > win_rate:
            conf += 0.1  # Melhorando
        elif recent_win_rate < win_rate - 0.1:
            conf -= 0.1  # Piorando
        if streak > 3:
            conf += 0.05
        if streak < -3:
            conf -= 0.15
        if total >= 50:
            conf += 0.05  # Mais dados = mais confiança
        self.confidence = max(0.1, min(0.95, conf))

        self.analysis = {
            "status": "analisado",
            "trades": total,
            "wins": len(wins),
            "losses": len(losses),
            "neutral": len(neutral),
            "win_rate": round(win_rate * 100, 1),
            "total_pnl": round(total_pnl, 4),
            "avg_pnl": round(avg_pnl, 4),
            "avg_win": round(avg_win, 4),
            "avg_loss": round(avg_loss, 4),
            "profit_factor": round(profit_factor, 2),
            "recent_win_rate": round(recent_win_rate * 100, 1),
            "recent_pnl": round(recent_pnl, 4),
            "streak": streak,
            "max_drawdown": round(max_dd, 4),
            "confidence": round(self.confidence, 2),
            "best_hours": [(h, round(d["pnl"], 4), d["count"]) for h, d in best_hours],
            "worst_hours": [(h, round(d["pnl"], 4), d["count"]) for h, d in worst_hours],
            "sim_accuracy": round(sim_real_corr * 100, 1),
            "best_signals": [(s, round(d["pnl"], 4), d["count"]) for s, d in best_signals],
            "worst_signals": [(s, round(d["pnl"], 4), d["count"]) for s, d in worst_signals],
        }
        self.last_analyzed = time.time()
        return self.analysis

    def should_execute(self, signal: Dict, trade_history: List[Dict]) -> Tuple[bool, str]:
        """
        Decide se deve executar um sinal baseado na analise.
        Retorna (executar, motivo).
        """
        self.decisions_made += 1

        total_trades = len(trade_history) if trade_history else 0

        # Se poucos trades, sempre aprova (fase de aprendizado)
        if total_trades < MIN_TRADES_TO_ADAPT:
            self.signals_approved += 1
            return True, f"aprendendo ({total_trades}/{MIN_TRADES_TO_ADAPT} trades)"

        # Re-analisa se faz mais de 5 min
        if time.time() - self.last_analyzed > 300:
            self.analyze_history(trade_history, {})

        analysis = self.analysis
        if not analysis or analysis.get("status") == "sem_dados":
            self.signals_approved += 1
            return True, "sem analise"

        reasons_reject = []
        reasons_approve = []

        # 1. Win rate muito baixo? Rejeita mais sinais
        win_rate = analysis.get("win_rate", 50)
        if win_rate < 30 and total_trades >= 20:
            reasons_reject.append(f"win_rate baixo ({win_rate}%)")

        # 2. Sequencia de losses? Pausa temporaria
        if self.streak <= -5:
            reasons_reject.append(f"sequencia de {abs(self.streak)} losses")

        # 3. Drawdown alto? Reduz exposicao
        max_dd = analysis.get("max_drawdown", 0)
        total_pnl = analysis.get("total_pnl", 0)
        if max_dd > 0 and total_pnl > 0 and max_dd > total_pnl * 2:
            reasons_reject.append(f"drawdown alto (${max_dd:.4f})")

        # 4. Horario ruim? Filtro de horario
        now_hour = datetime.now(BR_TZ).hour
        worst_hours = [h for h, pnl, cnt in analysis.get("worst_hours", [])
                       if pnl < 0 and cnt >= 5]
        if now_hour in worst_hours and total_trades >= 30:
            reasons_reject.append(f"horario {now_hour}h tem historico ruim")

        # 5. Sinal especifico tem historico ruim?
        signal_name = signal.get("trade_info", {}).get("token", "")
        if signal_name:
            worst_sigs = [s for s, pnl, cnt in analysis.get("worst_signals", [])
                          if pnl < -0.01 and cnt >= 3]
            if signal_name in worst_sigs:
                reasons_reject.append(f"sinal '{signal_name}' tem historico negativo")

        # 6. Fatores positivos
        if win_rate > 55:
            reasons_approve.append(f"win_rate bom ({win_rate}%)")
        if self.streak >= 3:
            reasons_approve.append(f"sequencia de {self.streak} wins")
        recent_wr = analysis.get("recent_win_rate", 50)
        if recent_wr > win_rate:
            reasons_approve.append("performance recente melhorando")

        # Decisao final
        # Rejeita se tem motivos fortes e poucos motivos para aprovar
        if reasons_reject and not reasons_approve:
            self.signals_rejected += 1
            reason = f"REJEITADO: {'; '.join(reasons_reject)}"
            logger.info(f"[AGENTE {self.key}] {reason}")
            return False, reason

        # Rejeita com probabilidade baseada na confianca
        if reasons_reject and self.confidence < 0.4:
            self.signals_rejected += 1
            reason = f"REJEITADO (conf={self.confidence:.0%}): {'; '.join(reasons_reject)}"
            logger.info(f"[AGENTE {self.key}] {reason}")
            return False, reason

        self.signals_approved += 1
        reasons = reasons_approve if reasons_approve else ["padrao"]
        reason = f"APROVADO (conf={self.confidence:.0%}): {'; '.join(reasons)}"
        logger.info(f"[AGENTE {self.key}] {reason}")
        return True, reason

    def get_tp_sl_adjustments(self, trade_history: List[Dict]) -> Dict:
        """
        Sugere ajustes de TP/SL baseado no historico.
        Retorna dict com tp_pct e sl_pct ajustados, ou vazio se nao tem dados.
        """
        if len(trade_history) < MIN_TRADES_TO_ADAPT:
            return {}

        if time.time() - self.last_analyzed > 300:
            self.analyze_history(trade_history, {})

        analysis = self.analysis
        if not analysis or analysis.get("trades", 0) < MIN_TRADES_TO_ADAPT:
            return {}

        adjustments = {}
        win_rate = analysis.get("win_rate", 50) / 100
        profit_factor = analysis.get("profit_factor", 1.0)

        # Se win rate alto mas avg_win pequeno: pode aumentar TP
        avg_win = analysis.get("avg_win", 0)
        avg_loss = abs(analysis.get("avg_loss", 0))
        if win_rate > 0.6 and avg_win < avg_loss * 0.5:
            adjustments["tp_suggestion"] = "aumentar_tp"
            adjustments["reason_tp"] = "win rate alto mas lucros pequenos"

        # Se win rate baixo mas avg_win grande: TP esta bom, SL precisa ser mais apertado
        if win_rate < 0.4 and avg_win > avg_loss * 2:
            adjustments["sl_suggestion"] = "apertar_sl"
            adjustments["reason_sl"] = "muitas losses, apertar stop"

        # Se muitos timeouts: posicao segura demais, ajustar
        recent = trade_history[-20:]
        timeouts = sum(1 for t in recent if t.get("status") == "timeout")
        if timeouts > len(recent) * 0.3:
            adjustments["hold_suggestion"] = "aumentar_hold"
            adjustments["reason_hold"] = f"{timeouts}/{len(recent)} timeouts recentes"

        self.adjustments = adjustments
        return adjustments

    def get_dashboard_data(self) -> Dict:
        """Retorna dados do agente para exibir no dashboard."""
        return {
            "strategy": self.key,
            "confidence": round(self.confidence, 2),
            "decisions": self.decisions_made,
            "approved": self.signals_approved,
            "rejected": self.signals_rejected,
            "streak": self.streak,
            "approval_rate": round(
                self.signals_approved / self.decisions_made * 100, 1
            ) if self.decisions_made > 0 else 100,
            "analysis": self.analysis,
            "adjustments": self.adjustments,
            "last_analyzed": self.last_analyzed,
        }


class AgentManager:
    """Gerencia todos os agentes de estrategia."""

    def __init__(self):
        self.agents: Dict[str, StrategyAgent] = {}
        self._load_state()

    def get_agent(self, strategy_key: str) -> StrategyAgent:
        """Retorna ou cria agente para a estrategia."""
        if strategy_key not in self.agents:
            self.agents[strategy_key] = StrategyAgent(strategy_key)
        return self.agents[strategy_key]

    def evaluate_signal(self, signal: Dict, trade_history: List[Dict]) -> Tuple[bool, str]:
        """Avalia se um sinal deve ser executado."""
        key = signal.get("strategy", "")
        agent = self.get_agent(key)
        return agent.should_execute(signal, trade_history)

    def update_after_trade(self, strategy_key: str, trade_history: List[Dict],
                           allocation: Dict):
        """Atualiza analise do agente apos trade."""
        agent = self.get_agent(strategy_key)
        agent.analyze_history(trade_history, allocation)
        agent.get_tp_sl_adjustments(trade_history)
        self._save_state()

    def get_all_dashboard_data(self) -> List[Dict]:
        """Retorna dados de todos os agentes para o dashboard."""
        return [agent.get_dashboard_data() for agent in self.agents.values()]

    def _save_state(self):
        """Persiste estado dos agentes."""
        try:
            state = {}
            for key, agent in self.agents.items():
                state[key] = {
                    "confidence": agent.confidence,
                    "decisions_made": agent.decisions_made,
                    "signals_approved": agent.signals_approved,
                    "signals_rejected": agent.signals_rejected,
                    "streak": agent.streak,
                    "analysis": agent.analysis,
                    "adjustments": agent.adjustments,
                    "last_analyzed": agent.last_analyzed,
                }
            with open(AGENTS_FILE, "w") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save agents state: {e}")

    def _load_state(self):
        """Carrega estado persistido dos agentes."""
        try:
            with open(AGENTS_FILE) as f:
                state = json.load(f)
            for key, data in state.items():
                agent = self.get_agent(key)
                agent.confidence = data.get("confidence", 0.5)
                agent.decisions_made = data.get("decisions_made", 0)
                agent.signals_approved = data.get("signals_approved", 0)
                agent.signals_rejected = data.get("signals_rejected", 0)
                agent.streak = data.get("streak", 0)
                agent.analysis = data.get("analysis", {})
                agent.adjustments = data.get("adjustments", {})
                agent.last_analyzed = data.get("last_analyzed", 0)
            logger.info(f"Loaded {len(state)} agent states")
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        except Exception as e:
            logger.warning(f"Failed to load agents state: {e}")
