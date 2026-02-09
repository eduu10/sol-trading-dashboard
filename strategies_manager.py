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

    # TP/SL/Hold config para MODO REAL por estrategia
    STRATEGY_HOLD_CONFIG = {
        "sniper": {
            "tp_pct": 100.0,
            "sl_pct": 50.0,
            "max_hold_s": 300,
            "trailing_pct": 0,
            "leverage": 1,
            "instant": False,
        },
        "memecoin": {
            "tp_pct": 30.0,
            "sl_pct": 15.0,
            "max_hold_s": 3600,
            "trailing_pct": 8.0,
            "leverage": 1,
            "instant": False,
        },
        "arbitrage": {
            "tp_pct": 0,
            "sl_pct": 0,
            "max_hold_s": 0,
            "trailing_pct": 0,
            "leverage": 1,
            "instant": True,
        },
        "scalping": {
            "tp_pct": 0.5,
            "sl_pct": 0.3,
            "max_hold_s": 300,
            "trailing_pct": 0.15,
            "leverage": 1,
            "instant": False,
        },
        "leverage": {
            "tp_pct": 10.0,
            "sl_pct": 5.0,
            "max_hold_s": 172800,
            "trailing_pct": 0,
            "leverage": 5,
            "instant": False,
        },
    }

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

        # Posicoes reais abertas (MODO REAL com hold)
        self.real_positions: List[Dict] = []
        self._load_real_positions()

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

    # ---- Posicoes reais abertas (MODO REAL hold) ----

    def _load_real_positions(self):
        """Carrega posicoes reais abertas do disco."""
        try:
            with open("real_positions.json") as f:
                self.real_positions = json.load(f)
                open_count = sum(1 for p in self.real_positions if p.get("status") == "open")
                if open_count:
                    logger.info(f"Loaded {open_count} open real positions")
        except (FileNotFoundError, json.JSONDecodeError):
            self.real_positions = []

    def _save_real_positions(self):
        """Persiste posicoes reais em disco."""
        # Mantem apenas abertas + ultimas 50 fechadas
        open_pos = [p for p in self.real_positions if p.get("status") == "open"]
        closed = [p for p in self.real_positions if p.get("status") != "open"]
        self.real_positions = open_pos + closed[-50:]
        with open("real_positions.json", "w") as f:
            json.dump(self.real_positions, f, indent=2)

    def open_real_position(self, strategy: str, coin: str, coin_mint: str,
                           amount_usd: float, coins_received: int,
                           coin_decimals: int, entry_price_per_coin: float,
                           tx_buy: str, direction: str, trade_id: str,
                           sim_pnl_pct: float) -> dict:
        """Registra posicao aberta apos BUY."""
        hold_cfg = self.STRATEGY_HOLD_CONFIG.get(strategy, {})
        pos = {
            "strategy": strategy,
            "coin": coin,
            "coin_mint": coin_mint,
            "amount_usd": amount_usd,
            "coins_received": coins_received,
            "coin_decimals": coin_decimals,
            "entry_price_usd": entry_price_per_coin,
            "tx_buy": tx_buy,
            "tx_sell": "",
            "direction": direction,
            "trade_id": trade_id,
            "sim_pnl_pct": sim_pnl_pct,
            "opened_at": time.time(),
            "tp_pct": hold_cfg.get("tp_pct", 10.0),
            "sl_pct": hold_cfg.get("sl_pct", 5.0),
            "max_hold_s": hold_cfg.get("max_hold_s", 300),
            "trailing_pct": hold_cfg.get("trailing_pct", 0),
            "leverage": hold_cfg.get("leverage", 1),
            "highest_value_usd": amount_usd,
            "status": "open",
            "unrealized_pnl_usd": 0.0,
            "unrealized_pnl_pct": 0.0,
            "current_value_usd": amount_usd,
            "last_checked": time.time(),
        }
        self.real_positions.append(pos)
        self._save_real_positions()
        logger.info(
            f"[MODO REAL] Posicao aberta: {strategy} | ${amount_usd:.2f} {coin} | "
            f"TP: +{pos['tp_pct']}% SL: -{pos['sl_pct']}% "
            f"Hold: {pos['max_hold_s']}s"
        )
        return pos

    def has_open_position(self, strategy: str) -> bool:
        """Checa se estrategia ja tem posicao aberta (sem empilhar)."""
        return any(
            p["strategy"] == strategy and p["status"] == "open"
            for p in self.real_positions
        )

    def get_open_real_positions(self) -> List[Dict]:
        """Retorna posicoes abertas."""
        return [p for p in self.real_positions if p["status"] == "open"]

    def close_real_position(self, pos: dict, tx_sell: str,
                            close_value_usd: float, reason: str) -> float:
        """Fecha posicao real com resultado da venda."""
        pos["tx_sell"] = tx_sell
        pos["status"] = f"closed_{reason}"
        pos["closed_at"] = time.time()
        pos["close_value_usd"] = close_value_usd
        real_pnl = round(close_value_usd - pos["amount_usd"], 4)
        pos["realized_pnl_usd"] = real_pnl

        # Atualiza allocation stats
        self.update_allocation_after_trade(
            pos["strategy"], tx_sell, real_pnl,
            tx_buy=pos["tx_buy"], tx_sell=tx_sell,
            amount_usd=pos["amount_usd"], coin=pos["coin"],
            direction=pos["direction"], sim_pnl_pct=pos["sim_pnl_pct"]
        )
        self._save_real_positions()
        return real_pnl

    def check_real_positions_tp_sl(self, current_values: dict) -> list:
        """
        Verifica TP/SL/timeout/trailing/liquidacao em posicoes abertas.
        current_values: {trade_id: current_value_usd}
        Retorna lista de (pos, reason) para fechar.
        """
        to_close = []
        now = time.time()

        for pos in self.real_positions:
            if pos["status"] != "open":
                continue

            current_val = current_values.get(pos["trade_id"])
            if current_val is None:
                continue

            entry_usd = pos["amount_usd"]
            lev = pos.get("leverage", 1)

            # PnL calculation (leverage multiplica)
            raw_pnl_pct = ((current_val - entry_usd) / entry_usd) * 100 if entry_usd > 0 else 0
            effective_pnl_pct = raw_pnl_pct * lev

            pos["unrealized_pnl_pct"] = round(effective_pnl_pct, 2)
            pos["unrealized_pnl_usd"] = round((current_val - entry_usd) * lev, 4)
            pos["current_value_usd"] = round(current_val, 4)
            pos["last_checked"] = now

            # Trailing: track highest
            if current_val > pos.get("highest_value_usd", entry_usd):
                pos["highest_value_usd"] = current_val

            # 1. TIMEOUT
            hold_time = now - pos["opened_at"]
            max_hold = pos.get("max_hold_s", 0)
            if max_hold > 0 and hold_time >= max_hold:
                to_close.append((pos, "timeout"))
                continue

            # 2. TAKE PROFIT
            tp = pos.get("tp_pct", 0)
            if tp > 0 and effective_pnl_pct >= tp:
                to_close.append((pos, "tp"))
                continue

            # 3. STOP LOSS
            sl = pos.get("sl_pct", 0)
            if sl > 0 and effective_pnl_pct <= -sl:
                to_close.append((pos, "sl"))
                continue

            # 4. LIQUIDACAO (leverage: perde > 90% da margem)
            if lev > 1 and effective_pnl_pct <= -90.0:
                to_close.append((pos, "liquidated"))
                continue

            # 5. TRAILING STOP
            trailing = pos.get("trailing_pct", 0)
            if trailing > 0 and current_val > entry_usd:
                highest = pos.get("highest_value_usd", entry_usd)
                drop_pct = ((highest - current_val) / highest) * 100
                if drop_pct >= trailing:
                    to_close.append((pos, "trailing"))
                    continue

        self._save_real_positions()
        return to_close

    def get_real_positions_dashboard(self) -> list:
        """Retorna posicoes abertas para o cloud dashboard."""
        return [
            {
                "strategy": p["strategy"],
                "coin": p["coin"],
                "amount_usd": p["amount_usd"],
                "current_value_usd": p.get("current_value_usd", p["amount_usd"]),
                "unrealized_pnl_usd": p.get("unrealized_pnl_usd", 0),
                "unrealized_pnl_pct": p.get("unrealized_pnl_pct", 0),
                "tp_pct": p.get("tp_pct", 0),
                "sl_pct": p.get("sl_pct", 0),
                "trailing_pct": p.get("trailing_pct", 0),
                "max_hold_s": p.get("max_hold_s", 0),
                "hold_time_s": round(time.time() - p["opened_at"]),
                "tx_buy": p["tx_buy"],
                "direction": p["direction"],
                "status": p["status"],
                "opened_at": p["opened_at"],
            }
            for p in self.real_positions
            if p["status"] == "open"
        ]

    # ---- Alocacao de capital real ----

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
        logger.info(f"ALOCACAO REAL: {amount:.4f} {coin} -> estrategia '{key}'")
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

    def _get_trade_count(self, key: str) -> int:
        """Retorna total de trades de uma estrategia."""
        strat = getattr(self, key, None)
        if not strat:
            return 0
        data = strat.get_dashboard_data()
        stats = data.get("stats", {})
        if key == "sniper":
            return stats.get("total_snipes", 0)
        elif key == "arbitrage":
            return stats.get("executed", 0)
        return stats.get("total_trades", 0)

    def snapshot_trade_counts(self) -> Dict[str, int]:
        """Tira foto do total de trades ANTES da simulacao."""
        return {k: self._get_trade_count(k) for k in self.STRATEGY_KEYS}

    def get_new_trade_signals(self, before_counts: Dict[str, int]) -> List[Dict]:
        """
        Compara trade counts apos simulacao para detectar trades novos.
        Para estrategias com capital real alocado, retorna sinais de
        swap para executar via Jupiter.
        """
        signals = []
        for key in self.STRATEGY_KEYS:
            alloc = self.get_allocation(key)
            if not alloc:
                continue

            before = before_counts.get(key, 0)
            after = self._get_trade_count(key)
            if after <= before:
                continue

            # Novo trade detectado! Pega detalhes
            strat = getattr(self, key, None)
            if not strat:
                continue
            data = strat.get_dashboard_data()
            trade_info = self._get_last_trade_info(key, data)
            if not trade_info:
                continue

            # Determina token e direcao do swap
            coin = alloc.get("coin", "SOL")
            direction = trade_info.get("direction", "long")
            # Sniper, memecoin, arbitrage sao sempre long
            if key in ("sniper", "memecoin", "arbitrage"):
                direction = "long"
            pnl_pct = trade_info.get("pnl_pct", 0)
            won = pnl_pct > 0

            trade_id = f"{key}_{int(time.time())}_{after}"

            signals.append({
                "strategy": key,
                "direction": direction,
                "amount_raw": alloc["amount"],
                "amount_coin": coin,
                "trade_id": trade_id,
                "trade_info": trade_info,
                "sim_pnl_pct": pnl_pct,
                "sim_won": won,
            })

            logger.info(
                f"[MODO REAL] Sinal detectado: {key} {direction} "
                f"{alloc['amount']:.4f} {coin} | Sim: {pnl_pct:+.1f}%"
            )

        return signals

    def update_allocation_after_trade(self, key: str, tx_hash: str, pnl_usd: float,
                                      tx_buy: str = "", tx_sell: str = "",
                                      amount_usd: float = 0, coin: str = "SOL",
                                      direction: str = "long", sim_pnl_pct: float = 0):
        """Atualiza dados da alocacao apos executar trade real."""
        if key not in self.allocations:
            return
        alloc = self.allocations[key]
        alloc["trades"] = alloc.get("trades", 0) + 1
        alloc["pnl"] = round(alloc.get("pnl", 0) + pnl_usd, 4)
        alloc["last_tx"] = tx_hash
        alloc["last_trade_time"] = time.time()

        # Pega info do ultimo trade
        trade_info = self._get_last_trade_info(key, getattr(self, key).get_dashboard_data())
        if trade_info:
            alloc["last_trade_info"] = trade_info
            alloc["sim_pnl_pct"] = trade_info.get("pnl_pct", 0)

        # Registra no historico de trades
        if "trade_history" not in alloc:
            alloc["trade_history"] = []
        trade_record = {
            "time": time.time(),
            "pnl": pnl_usd,
            "tx_buy": tx_buy,
            "tx_sell": tx_sell,
            "amount": amount_usd or alloc.get("amount", 0),
            "coin": coin,
            "direction": direction,
            "sim_pnl_pct": sim_pnl_pct,
            "signal": trade_info.get("name", trade_info.get("token", "?")) if trade_info else "?",
            "status": "ok" if tx_sell else ("partial" if tx_buy else "failed"),
        }
        alloc["trade_history"].append(trade_record)
        # Limita a 100 trades no historico
        if len(alloc["trade_history"]) > 100:
            alloc["trade_history"] = alloc["trade_history"][-100:]

        self._save_allocations()

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
