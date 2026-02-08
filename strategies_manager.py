"""
Gerenciador de Estrategias - 5 Variacoes de Day Trade DEX Solana
==================================================================
Coordena todas as 5 estrategias de teste, roda simulacoes periodicas
e fornece dados consolidados para o dashboard.
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Optional

from strategy_sniper import SnipingStrategy
from strategy_memecoin import MemeCoinStrategy
from strategy_arbitrage import ArbitrageStrategy
from strategy_scalping import ScalpingStrategy
from strategy_leverage import LeverageStrategy

logger = logging.getLogger("StrategiesManager")


class StrategiesManager:
    """Gerencia as 5 estrategias de day trade em modo teste."""

    STRATEGY_KEYS = ["sniper", "memecoin", "arbitrage", "scalping", "leverage"]

    def __init__(self):
        self.sniper = SnipingStrategy()
        self.memecoin = MemeCoinStrategy()
        self.arbitrage = ArbitrageStrategy()
        self.scalping = ScalpingStrategy()
        self.leverage = LeverageStrategy()

        self.strategies = [
            self.sniper,
            self.memecoin,
            self.arbitrage,
            self.scalping,
            self.leverage,
        ]

        # Estado pausado por estrategia
        self.paused = {k: False for k in self.STRATEGY_KEYS}

        # Alocacoes de capital real por estrategia
        # {key: {"amount": float, "active": bool, "allocated_at": float}}
        self.allocations: Dict[str, Dict] = {}
        self._load_allocations()

    def toggle_strategy(self, key: str) -> bool:
        """Alterna pausa de uma estrategia. Retorna novo estado (True=pausado)."""
        if key in self.paused:
            self.paused[key] = not self.paused[key]
            logger.info(f"Strategy '{key}' {'PAUSADA' if self.paused[key] else 'RETOMADA'}")
            return self.paused[key]
        return False

    async def run_simulation_cycle(self) -> Dict:
        """Roda um ciclo de simulacao para todas as estrategias (pula pausadas)."""
        results = {}

        if not self.paused.get("sniper"):
            try:
                data1 = await self.sniper.simulate_monitoring()
                results["sniper"] = data1
            except Exception as e:
                logger.debug(f"Sniper sim error: {e}")

        if not self.paused.get("memecoin"):
            try:
                data2 = await self.memecoin.simulate_analysis()
                results["memecoin"] = data2
            except Exception as e:
                logger.debug(f"Memecoin sim error: {e}")

        if not self.paused.get("arbitrage"):
            try:
                data3 = await self.arbitrage.simulate_scan()
                results["arbitrage"] = data3
            except Exception as e:
                logger.debug(f"Arbitrage sim error: {e}")

        if not self.paused.get("scalping"):
            try:
                data4 = await self.scalping.simulate_scalp()
                results["scalping"] = data4
            except Exception as e:
                logger.debug(f"Scalping sim error: {e}")

        if not self.paused.get("leverage"):
            try:
                data5 = await self.leverage.simulate_leverage_trade()
                results["leverage"] = data5
            except Exception as e:
                logger.debug(f"Leverage sim error: {e}")

        return results

    # ---- Alocacao de capital real ----

    def _load_allocations(self):
        """Carrega alocacoes salvas em disco."""
        try:
            with open("allocations.json") as f:
                self.allocations = json.load(f)
                logger.info(f"Loaded {len(self.allocations)} allocations")
        except (FileNotFoundError, json.JSONDecodeError):
            self.allocations = {}

    def _save_allocations(self):
        """Persiste alocacoes em disco."""
        with open("allocations.json", "w") as f:
            json.dump(self.allocations, f, indent=2)

    def allocate_strategy(self, key: str, amount: float, coin: str = "SOL") -> bool:
        """Aloca capital real para uma estrategia."""
        if key not in self.STRATEGY_KEYS:
            return False
        if amount <= 0:
            return False
        self.allocations[key] = {
            "amount": amount,
            "coin": coin,
            "active": True,
            "allocated_at": time.time(),
            "pnl": 0.0,
            "trades": 0,
        }
        self._save_allocations()
        logger.info(f"ALOCACAO REAL: ${amount:.2f} -> estrategia '{key}'")
        return True

    def deallocate_strategy(self, key: str) -> bool:
        """Remove alocacao de capital real."""
        if key in self.allocations:
            old = self.allocations.pop(key)
            self._save_allocations()
            logger.info(f"DESALOCACAO: estrategia '{key}' (era ${old.get('amount', 0):.2f})")
            return True
        return False

    def get_allocation(self, key: str) -> Optional[Dict]:
        """Retorna alocacao de uma estrategia ou None."""
        alloc = self.allocations.get(key)
        if alloc and alloc.get("active"):
            return alloc
        return None

    def get_all_allocations(self) -> Dict:
        """Retorna todas as alocacoes para o dashboard."""
        return dict(self.allocations)

    def sync_real_from_simulations(self) -> List[Dict]:
        """
        Sincroniza o MODO REAL com as simulacoes.
        Detecta novos trades completados nas simulacoes e replica o PNL
        proporcionalmente no capital alocado.
        Retorna lista de trades replicados (para log/notificacao).
        """
        replicated = []
        for key in self.STRATEGY_KEYS:
            alloc = self.get_allocation(key)
            if not alloc:
                continue
            if self.paused.get(key):
                continue

            strat = getattr(self, key, None)
            if not strat:
                continue

            data = strat.get_dashboard_data()
            capital = data.get("capital", {})

            # Conta total de trades da simulacao
            stats = data.get("stats", {})
            sim_trades = 0
            if key == "sniper":
                sim_trades = stats.get("total_snipes", 0)
            elif key == "arbitrage":
                sim_trades = stats.get("executed", 0)
            else:
                sim_trades = stats.get("total_trades", 0)

            # Quantos trades ja replicamos?
            last_synced = alloc.get("last_synced_trades", 0)
            new_trades = sim_trades - last_synced

            if new_trades <= 0:
                continue

            # Pega o PNL da simulacao (% sobre capital teste $100)
            sim_pnl_usd = capital.get("pnl_usd", 0)
            sim_capital = capital.get("initial", 100.0)
            if sim_capital <= 0:
                sim_capital = 100.0
            sim_pnl_pct = (sim_pnl_usd / sim_capital) * 100 if sim_capital else 0

            # Calcula PNL real proporcional ao capital alocado
            real_amount = alloc["amount"]
            real_pnl = real_amount * (sim_pnl_pct / 100)

            # Pega ultimo trade recente para detalhes
            last_trade_info = self._get_last_trade_info(key, data)

            # Atualiza alocacao
            alloc["pnl"] = round(real_pnl, 4)
            alloc["trades"] = sim_trades
            alloc["last_synced_trades"] = sim_trades
            alloc["sim_pnl_pct"] = round(sim_pnl_pct, 2)
            alloc["last_sync"] = time.time()
            if last_trade_info:
                alloc["last_trade_info"] = last_trade_info

            self._save_allocations()

            for _ in range(new_trades):
                replicated.append({
                    "strategy": key,
                    "coin": alloc.get("coin", "SOL"),
                    "amount": real_amount,
                    "sim_pnl_pct": sim_pnl_pct,
                    "real_pnl": real_pnl,
                    "trades": sim_trades,
                    "last_info": last_trade_info,
                })

            if new_trades > 0:
                logger.info(
                    f"[MODO REAL] {key}: {new_trades} novos trades | "
                    f"Sim PNL: {sim_pnl_pct:+.2f}% | "
                    f"Real PNL: ${real_pnl:+.2f} (de ${real_amount:.2f})"
                )

        return replicated

    def _get_last_trade_info(self, key: str, data: Dict) -> Optional[Dict]:
        """Extrai info do ultimo trade da simulacao para mostrar no dashboard."""
        try:
            if key == "scalping":
                recent = data.get("recent_trades", [])
                if recent:
                    t = recent[-1]
                    return {"token": t.get("token", "?"), "direction": t.get("direction", "?"),
                            "pnl_pct": t.get("pnl_pct", 0), "status": t.get("status", "?")}
            elif key == "memecoin":
                recent = data.get("recent_signals", [])
                if recent:
                    t = recent[-1]
                    return {"name": t.get("name", "?"), "pnl_pct": t.get("pnl_pct", 0),
                            "status": t.get("status", "?")}
            elif key == "arbitrage":
                recent = data.get("recent_opportunities", [])
                if recent:
                    t = recent[-1]
                    return {"token": t.get("token", "?"), "profit": t.get("profit", 0),
                            "status": t.get("status", "?")}
            elif key == "sniper":
                recent = data.get("recent_targets", [])
                if recent:
                    t = recent[-1]
                    return {"name": t.get("name", "?"), "pnl_pct": t.get("pnl_pct", 0),
                            "status": t.get("status", "?")}
            elif key == "leverage":
                recent = data.get("recent_positions", [])
                if recent:
                    t = recent[-1]
                    return {"token": t.get("token", "?"), "direction": t.get("direction", "?"),
                            "pnl_pct": t.get("pnl_pct", 0), "leverage": t.get("leverage", "?"),
                            "status": t.get("status", "?")}
        except Exception:
            pass
        return None

    def mark_trade_executed(self, key: str, trade_id: str, tx_hash: str):
        """Marca que um trade real foi executado para evitar duplicata."""
        if key in self.allocations:
            self.allocations[key]["last_trade_id"] = trade_id
            self.allocations[key]["last_tx"] = tx_hash
            self.allocations[key]["trades"] = self.allocations[key].get("trades", 0) + 1
            self._save_allocations()

    def get_all_dashboard_data(self) -> Dict:
        """Retorna dados de todas as estrategias para o dashboard."""
        data = {
            "sniper": self.sniper.get_dashboard_data(),
            "memecoin": self.memecoin.get_dashboard_data(),
            "arbitrage": self.arbitrage.get_dashboard_data(),
            "scalping": self.scalping.get_dashboard_data(),
            "leverage": self.leverage.get_dashboard_data(),
        }
        # Adiciona estado pausado a cada estrategia
        for key in self.STRATEGY_KEYS:
            if key in data:
                data[key]["paused"] = self.paused.get(key, False)
        return data

    def get_summary(self) -> Dict:
        """Retorna resumo comparativo das estrategias."""
        all_data = self.get_all_dashboard_data()
        summary = []
        for key, data in all_data.items():
            stats = data.get("stats", {})
            summary.append({
                "key": key,
                "name": data.get("strategy_name", key),
                "risk": data.get("risk_level", "?"),
                "return": data.get("return_level", "?"),
                "timeframe": data.get("time_frame", "?"),
                "total_trades": stats.get("total_trades", stats.get("total_snipes", stats.get("executed", 0))),
                "win_rate": stats.get("win_rate", 0),
                "total_pnl": stats.get("total_pnl_usd", stats.get("total_pnl", stats.get("net_profit", 0))),
            })
        return {"strategies": summary}
