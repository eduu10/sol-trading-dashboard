"""
Gerenciador de Estrategias - 5 Variacoes de Day Trade DEX Solana
==================================================================
Coordena todas as 5 estrategias de teste, roda simulacoes periodicas
e fornece dados consolidados para o dashboard.
"""

import asyncio
import logging
from typing import Dict, List

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
