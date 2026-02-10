"""
Strategy Agents - Agentes adaptativos para cada estrategia
============================================================
Cada agente analisa o historico de trades reais da sua estrategia,
ajusta parametros (TP/SL, hold), gera pensamentos sobre o mercado,
e registra historico de decisoes e ajustes.

O agente aprende com:
- Win rate recente vs geral
- PnL medio por trade
- Horarios com melhor performance
- Sequencias de wins/losses
- Drawdown maximo
- Correlacao entre sim_pnl e pnl real
- Performance por token/sinal
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
# Minimo de trades para ajustar config
MIN_TRADES_TO_TUNE = 20
# Limites de ajuste (nao deixa TP/SL ir muito longe do original)
MAX_TP_MULTIPLIER = 2.0
MIN_TP_MULTIPLIER = 0.5
MAX_SL_MULTIPLIER = 2.0
MIN_SL_MULTIPLIER = 0.5
MAX_HOLD_MULTIPLIER = 3.0
MIN_HOLD_MULTIPLIER = 0.3

# Config original de referencia (para limitar ajustes)
ORIGINAL_HOLD_CONFIG = {
    "sniper": {"tp_pct": 100.0, "sl_pct": 50.0, "max_hold_s": 300, "trailing_pct": 0},
    "memecoin": {"tp_pct": 30.0, "sl_pct": 15.0, "max_hold_s": 3600, "trailing_pct": 8.0},
    "arbitrage": {"tp_pct": 0, "sl_pct": 0, "max_hold_s": 0, "trailing_pct": 0},
    "scalping": {"tp_pct": 0.5, "sl_pct": 0.3, "max_hold_s": 300, "trailing_pct": 0.15},
    "leverage": {"tp_pct": 10.0, "sl_pct": 5.0, "max_hold_s": 172800, "trailing_pct": 0},
    "whale": {"tp_pct": 5.0, "sl_pct": 3.0, "max_hold_s": 1800, "trailing_pct": 1.5},
}


class StrategyAgent:
    """Agente adaptativo para uma estrategia individual."""

    def __init__(self, strategy_key: str):
        self.key = strategy_key
        self.confidence = 0.5
        self.adjustments = {}
        self.analysis = {}
        self.last_analyzed = 0
        self.decisions_made = 0
        self.signals_approved = 0
        self.signals_rejected = 0
        self.streak = 0

        # Novo: pensamentos e historico
        self.thoughts: List[str] = []  # Ultimos pensamentos (max 10)
        self.adjustment_history: List[Dict] = []  # Historico de ajustes (max 20)
        self.current_config_mods = {}  # Modificacoes atuais vs original
        self.phase = "aprendendo"  # aprendendo, analisando, otimizando, confiante

    def _add_thought(self, thought: str):
        """Adiciona pensamento com timestamp."""
        now = datetime.now(BR_TZ).strftime("%H:%M")
        self.thoughts.append(f"[{now}] {thought}")
        if len(self.thoughts) > 10:
            self.thoughts = self.thoughts[-10:]

    def _add_adjustment(self, param: str, old_val, new_val, reason: str):
        """Registra ajuste no historico."""
        self.adjustment_history.append({
            "time": time.time(),
            "param": param,
            "old": old_val,
            "new": new_val,
            "reason": reason,
        })
        if len(self.adjustment_history) > 20:
            self.adjustment_history = self.adjustment_history[-20:]

    def analyze_history(self, trade_history: List[Dict], allocation: Dict) -> Dict:
        """Analisa historico de trades e retorna metricas."""
        if not trade_history:
            self.analysis = {"status": "sem_dados", "trades": 0}
            self.phase = "aprendendo"
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
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else (float('inf') if gross_profit > 0 else 0)

        # Ultimos N trades (performance recente)
        recent_n = min(20, total)
        recent = trade_history[-recent_n:]
        recent_wins = [t for t in recent if (t.get("pnl", 0)) > 0]
        recent_win_rate = len(recent_wins) / len(recent) if recent else 0
        recent_pnl = sum(t.get("pnl", 0) for t in recent)

        # Streak atual
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

        # Correlacao sim vs real
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

        # Analise de fechamento (como as posicoes fecharam)
        close_reasons = {}
        for t in trade_history:
            status = t.get("status", "ok")
            if status not in close_reasons:
                close_reasons[status] = {"count": 0, "pnl": 0}
            close_reasons[status]["count"] += 1
            close_reasons[status]["pnl"] += t.get("pnl", 0)

        # Calcula confianca
        conf = 0.3
        if win_rate > 0.5:
            conf += 0.15
        if win_rate > 0.6:
            conf += 0.1
        if profit_factor > 1.5:
            conf += 0.15
        if recent_win_rate > win_rate:
            conf += 0.1
        elif recent_win_rate < win_rate - 0.1:
            conf -= 0.1
        if streak > 3:
            conf += 0.05
        if streak < -3:
            conf -= 0.15
        if total >= 50:
            conf += 0.05
        self.confidence = max(0.1, min(0.95, conf))

        # Determina fase do agente
        if total < MIN_TRADES_TO_ADAPT:
            self.phase = "aprendendo"
        elif total < MIN_TRADES_TO_TUNE:
            self.phase = "analisando"
        elif self.confidence >= 0.6:
            self.phase = "confiante"
        else:
            self.phase = "otimizando"

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
            "profit_factor": round(profit_factor, 2) if profit_factor != float('inf') else 99.0,
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
            "close_reasons": close_reasons,
        }
        self.last_analyzed = time.time()

        # Gera pensamentos baseados na analise
        self._generate_thoughts(trade_history)

        return self.analysis

    def _generate_thoughts(self, trade_history: List[Dict]):
        """Gera pensamentos inteligentes sobre a estrategia."""
        an = self.analysis
        if not an or an.get("status") == "sem_dados":
            return

        total = an.get("trades", 0)
        wr = an.get("win_rate", 0)
        pf = an.get("profit_factor", 0)
        recent_wr = an.get("recent_win_rate", 0)
        streak = an.get("streak", 0)
        avg_win = an.get("avg_win", 0)
        avg_loss = an.get("avg_loss", 0)

        self.thoughts = []  # Reset

        # Fase
        if total < MIN_TRADES_TO_ADAPT:
            self._add_thought(f"Coletando dados... {total}/{MIN_TRADES_TO_ADAPT} trades. Aprovando tudo para aprender.")
            return

        if total < MIN_TRADES_TO_TUNE:
            self._add_thought(f"Tenho {total} trades. Preciso de {MIN_TRADES_TO_TUNE} para comecar a ajustar parametros.")

        # Win rate
        if wr >= 65:
            self._add_thought(f"Win rate excelente ({wr}%). A estrategia esta funcionando muito bem.")
        elif wr >= 50:
            self._add_thought(f"Win rate ok ({wr}%). Lucrativo mas ha espaco para melhorar.")
        elif wr >= 35:
            self._add_thought(f"Win rate baixo ({wr}%). Preciso filtrar sinais mais agressivamente.")
        else:
            self._add_thought(f"Win rate critico ({wr}%). Rejeitando sinais de risco e apertando SL.")

        # Tendencia recente
        if recent_wr > wr + 5:
            self._add_thought(f"Tendencia recente positiva: win rate subiu de {wr}% para {recent_wr}%. Meus ajustes estao ajudando.")
        elif recent_wr < wr - 10:
            self._add_thought(f"Performance caindo! Win rate recente {recent_wr}% vs geral {wr}%. Investigando...")

        # Profit factor
        if pf > 2.0:
            self._add_thought(f"Profit factor {pf:.1f}x - lucros cobrem perdas com folga.")
        elif pf < 1.0 and pf > 0:
            self._add_thought(f"Profit factor {pf:.1f}x < 1.0 - estou perdendo dinheiro. Preciso ajustar.")

        # Streak
        if streak >= 5:
            self._add_thought(f"Sequencia de {streak} wins! Mantendo a estrategia atual.")
        elif streak <= -3:
            self._add_thought(f"Sequencia de {abs(streak)} losses. Sendo mais seletivo com sinais.")

        # TP/SL ratio
        if avg_win > 0 and avg_loss < 0:
            ratio = avg_win / abs(avg_loss)
            if ratio < 0.5:
                self._add_thought(f"Lucros medios (${avg_win:.4f}) sao muito menores que perdas (${avg_loss:.4f}). Sugerindo aumentar TP.")
            elif ratio > 3:
                self._add_thought(f"Bom risco/retorno: ganho medio {ratio:.1f}x maior que perda media.")

        # Melhores horarios
        best_h = an.get("best_hours", [])
        if best_h and len(best_h) > 0 and best_h[0][2] >= 3:
            self._add_thought(f"Melhor horario: {best_h[0][0]}h (${best_h[0][1]:.4f} em {best_h[0][2]} trades).")

        # Melhores sinais
        best_s = an.get("best_signals", [])
        if best_s and len(best_s) > 0 and best_s[0][2] >= 3:
            self._add_thought(f"Melhor ativo: {best_s[0][0]} (${best_s[0][1]:.4f} em {best_s[0][2]} trades).")

        # Ajustes feitos
        if self.current_config_mods:
            mods = []
            for k, v in self.current_config_mods.items():
                mods.append(f"{k}: {v}")
            self._add_thought(f"Ajustes ativos: {', '.join(mods)}")

    def compute_config_adjustments(self, trade_history: List[Dict],
                                    current_hold_config: Dict) -> Dict:
        """
        Calcula e APLICA ajustes ao STRATEGY_HOLD_CONFIG.
        Retorna o config atualizado para a estrategia.
        """
        if len(trade_history) < MIN_TRADES_TO_TUNE:
            return current_hold_config

        if self.key == "arbitrage":
            return current_hold_config  # Arbitrage é instant, não ajusta

        if time.time() - self.last_analyzed > 300:
            self.analyze_history(trade_history, {})

        an = self.analysis
        if not an or an.get("trades", 0) < MIN_TRADES_TO_TUNE:
            return current_hold_config

        orig = ORIGINAL_HOLD_CONFIG.get(self.key, {})
        if not orig:
            return current_hold_config

        new_config = dict(current_hold_config)
        win_rate = an.get("win_rate", 50) / 100
        avg_win = an.get("avg_win", 0)
        avg_loss = abs(an.get("avg_loss", 0))
        pf = an.get("profit_factor", 1.0)
        recent_wr = an.get("recent_win_rate", 50) / 100
        close_reasons = an.get("close_reasons", {})

        changes_made = []

        # --- TP Adjustment ---
        orig_tp = orig.get("tp_pct", 0)
        if orig_tp > 0:
            tp_mult = 1.0

            # Se win rate alto mas ganhos pequenos vs perdas: aumentar TP
            if win_rate > 0.6 and avg_win > 0 and avg_loss > 0 and avg_win < avg_loss * 0.5:
                tp_mult = 1.2
                reason = "win rate alto mas lucros pequenos - aumentando TP 20%"
            # Se muitos trades fecham por TP e performance boa: pode subir mais
            elif close_reasons.get("ok", {}).get("count", 0) > len(trade_history) * 0.4 and pf > 1.5:
                tp_mult = 1.15
                reason = "muitos TPs atingidos e PF bom - testando TP 15% maior"
            # Se performance ruim: reduzir TP para garantir mais lucros
            elif win_rate < 0.35 and pf < 0.8:
                tp_mult = 0.8
                reason = "performance ruim - reduzindo TP para garantir lucros"
            else:
                reason = None

            if reason:
                new_tp = round(orig_tp * max(MIN_TP_MULTIPLIER, min(MAX_TP_MULTIPLIER, tp_mult)), 2)
                if new_tp != current_hold_config.get("tp_pct"):
                    old_tp = current_hold_config.get("tp_pct", orig_tp)
                    new_config["tp_pct"] = new_tp
                    changes_made.append(("tp_pct", old_tp, new_tp, reason))

        # --- SL Adjustment ---
        orig_sl = orig.get("sl_pct", 0)
        if orig_sl > 0:
            sl_mult = 1.0

            # Se muitas losses e avg_loss grande: apertar SL
            if win_rate < 0.4 and avg_loss > avg_win * 2:
                sl_mult = 0.8
                reason = "muitas losses grandes - apertando SL 20%"
            # Se win rate bom mas drawdown alto: apertar SL levemente
            elif win_rate > 0.5 and an.get("max_drawdown", 0) > an.get("total_pnl", 0) * 1.5:
                sl_mult = 0.9
                reason = "drawdown alto vs PnL - apertando SL 10%"
            # Se performance excelente e SL raramente é atingido: pode relaxar
            elif win_rate > 0.65 and pf > 2.0:
                sl_mult = 1.15
                reason = "performance excelente - relaxando SL 15% para dar mais espaco"
            else:
                reason = None

            if reason:
                new_sl = round(orig_sl * max(MIN_SL_MULTIPLIER, min(MAX_SL_MULTIPLIER, sl_mult)), 2)
                if new_sl != current_hold_config.get("sl_pct"):
                    old_sl = current_hold_config.get("sl_pct", orig_sl)
                    new_config["sl_pct"] = new_sl
                    changes_made.append(("sl_pct", old_sl, new_sl, reason))

        # --- Hold Time Adjustment ---
        orig_hold = orig.get("max_hold_s", 0)
        if orig_hold > 0:
            timeout_trades = close_reasons.get("timeout", {}).get("count", 0)
            timeout_pct = timeout_trades / len(trade_history) if trade_history else 0

            # Se muitos timeouts com PnL positivo: aumentar hold
            timeout_pnl = close_reasons.get("timeout", {}).get("pnl", 0)
            if timeout_pct > 0.3 and timeout_pnl > 0:
                hold_mult = 1.3
                reason = f"{timeout_pct:.0%} timeouts com PnL positivo - aumentando hold 30%"
            # Se muitos timeouts com PnL negativo: diminuir hold
            elif timeout_pct > 0.3 and timeout_pnl < 0:
                hold_mult = 0.7
                reason = f"{timeout_pct:.0%} timeouts com PnL negativo - reduzindo hold 30%"
            else:
                hold_mult = 1.0
                reason = None

            if reason:
                new_hold = int(orig_hold * max(MIN_HOLD_MULTIPLIER, min(MAX_HOLD_MULTIPLIER, hold_mult)))
                if new_hold != current_hold_config.get("max_hold_s"):
                    old_hold = current_hold_config.get("max_hold_s", orig_hold)
                    new_config["max_hold_s"] = new_hold
                    changes_made.append(("max_hold_s", old_hold, new_hold, reason))

        # Registra ajustes
        for param, old_val, new_val, reason in changes_made:
            self._add_adjustment(param, old_val, new_val, reason)
            self.current_config_mods[param] = new_val
            self._add_thought(f"Ajustei {param}: {old_val} -> {new_val} ({reason})")
            logger.info(f"[AGENTE {self.key}] Ajuste: {param} {old_val} -> {new_val} | {reason}")

        return new_config

    def should_execute(self, signal: Dict, trade_history: List[Dict]) -> Tuple[bool, str]:
        """Decide se deve executar um sinal baseado na analise."""
        self.decisions_made += 1
        total_trades = len(trade_history) if trade_history else 0

        if total_trades < MIN_TRADES_TO_ADAPT:
            self.signals_approved += 1
            return True, f"aprendendo ({total_trades}/{MIN_TRADES_TO_ADAPT} trades)"

        if time.time() - self.last_analyzed > 300:
            self.analyze_history(trade_history, {})

        analysis = self.analysis
        if not analysis or analysis.get("status") == "sem_dados":
            self.signals_approved += 1
            return True, "sem analise"

        reasons_reject = []
        reasons_approve = []

        win_rate = analysis.get("win_rate", 50)
        if win_rate < 30 and total_trades >= 20:
            reasons_reject.append(f"win_rate baixo ({win_rate}%)")

        if self.streak <= -5:
            reasons_reject.append(f"sequencia de {abs(self.streak)} losses")

        max_dd = analysis.get("max_drawdown", 0)
        total_pnl = analysis.get("total_pnl", 0)
        if max_dd > 0 and total_pnl > 0 and max_dd > total_pnl * 2:
            reasons_reject.append(f"drawdown alto (${max_dd:.4f})")

        now_hour = datetime.now(BR_TZ).hour
        worst_hours = [h for h, pnl, cnt in analysis.get("worst_hours", [])
                       if pnl < 0 and cnt >= 5]
        if now_hour in worst_hours and total_trades >= 30:
            reasons_reject.append(f"horario {now_hour}h tem historico ruim")

        signal_name = signal.get("trade_info", {}).get("token", "")
        if signal_name:
            worst_sigs = [s for s, pnl, cnt in analysis.get("worst_signals", [])
                          if pnl < -0.01 and cnt >= 3]
            if signal_name in worst_sigs:
                reasons_reject.append(f"sinal '{signal_name}' tem historico negativo")

        if win_rate > 55:
            reasons_approve.append(f"win_rate bom ({win_rate}%)")
        if self.streak >= 3:
            reasons_approve.append(f"sequencia de {self.streak} wins")
        recent_wr = analysis.get("recent_win_rate", 50)
        if recent_wr > win_rate:
            reasons_approve.append("performance recente melhorando")

        if reasons_reject and not reasons_approve:
            self.signals_rejected += 1
            reason = f"REJEITADO: {'; '.join(reasons_reject)}"
            logger.info(f"[AGENTE {self.key}] {reason}")
            return False, reason

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

    def get_dashboard_data(self) -> Dict:
        """Retorna dados completos do agente para o dashboard."""
        return {
            "strategy": self.key,
            "confidence": round(self.confidence, 2),
            "phase": self.phase,
            "decisions": self.decisions_made,
            "approved": self.signals_approved,
            "rejected": self.signals_rejected,
            "streak": self.streak,
            "approval_rate": round(
                self.signals_approved / self.decisions_made * 100, 1
            ) if self.decisions_made > 0 else 100,
            "analysis": self.analysis,
            "adjustments": self.adjustments,
            "thoughts": self.thoughts,
            "adjustment_history": self.adjustment_history[-10:],
            "config_mods": self.current_config_mods,
            "last_analyzed": self.last_analyzed,
        }


class AgentManager:
    """Gerencia todos os agentes de estrategia."""

    def __init__(self):
        self.agents: Dict[str, StrategyAgent] = {}
        self._load_state()

    def get_agent(self, strategy_key: str) -> StrategyAgent:
        if strategy_key not in self.agents:
            self.agents[strategy_key] = StrategyAgent(strategy_key)
        return self.agents[strategy_key]

    def evaluate_signal(self, signal: Dict, trade_history: List[Dict]) -> Tuple[bool, str]:
        key = signal.get("strategy", "")
        agent = self.get_agent(key)
        return agent.should_execute(signal, trade_history)

    def update_after_trade(self, strategy_key: str, trade_history: List[Dict],
                           allocation: Dict):
        """Atualiza analise do agente e aplica ajustes apos trade."""
        agent = self.get_agent(strategy_key)
        agent.analyze_history(trade_history, allocation)
        self._save_state()

    def apply_config_tuning(self, hold_config: Dict,
                            allocations: Dict) -> Dict:
        """
        Aplica ajustes de todos os agentes ao STRATEGY_HOLD_CONFIG.
        Chamado a cada ciclo do bot.
        Retorna o config modificado.
        """
        updated = {}
        for key, cfg in hold_config.items():
            agent = self.get_agent(key)
            alloc = allocations.get(key)
            if alloc and alloc.get("active"):
                history = alloc.get("trade_history", [])
                new_cfg = agent.compute_config_adjustments(history, cfg)
                updated[key] = new_cfg
            else:
                updated[key] = cfg
        return updated

    def get_all_dashboard_data(self) -> List[Dict]:
        return [agent.get_dashboard_data() for agent in self.agents.values()]

    def _save_state(self):
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
                    "thoughts": agent.thoughts,
                    "adjustment_history": agent.adjustment_history,
                    "current_config_mods": agent.current_config_mods,
                    "phase": agent.phase,
                }
            with open(AGENTS_FILE, "w") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save agents state: {e}")

    def _load_state(self):
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
                agent.thoughts = data.get("thoughts", [])
                agent.adjustment_history = data.get("adjustment_history", [])
                agent.current_config_mods = data.get("current_config_mods", {})
                agent.phase = data.get("phase", "aprendendo")
            logger.info(f"Loaded {len(state)} agent states")
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        except Exception as e:
            logger.warning(f"Failed to load agents state: {e}")
