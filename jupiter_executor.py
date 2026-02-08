"""
Executor de Swaps via Jupiter DEX (Solana)
============================================
Usa Jupiter Aggregator API v6 para encontrar melhor rota
e executar swaps on-chain.
"""

import httpx
import base64
import json
import logging
import time
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, field

import config

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Posição aberta."""
    id: str
    symbol: str
    direction: str
    entry_price: float
    current_price: float
    quantity: float            # Quantidade do token comprado
    quantity_base: float       # Quantidade em USDC investida
    stop_loss: float
    take_profits: List[float]
    opened_at: str
    tx_hash: str
    pnl_pct: float = 0.0
    pnl_usd: float = 0.0
    status: str = "open"      # "open", "closed_tp", "closed_sl", "closed_manual"

    def to_dict(self) -> Dict:
        return {
            "id": self.id, "symbol": self.symbol, "direction": self.direction,
            "entry_price": self.entry_price, "current_price": self.current_price,
            "quantity": self.quantity, "quantity_base": self.quantity_base,
            "stop_loss": self.stop_loss, "take_profits": self.take_profits,
            "opened_at": self.opened_at, "tx_hash": self.tx_hash,
            "pnl_pct": round(self.pnl_pct, 2), "pnl_usd": round(self.pnl_usd, 2),
            "status": self.status,
        }


class JupiterExecutor:
    """Executa swaps via Jupiter Aggregator na Solana."""

    def __init__(self, learning_engine=None):
        self.client = httpx.AsyncClient(timeout=30)
        self.positions: List[Position] = []
        self.closed_positions: List[Position] = []
        self.learning = learning_engine
        self._load_positions()

    async def close(self):
        await self.client.aclose()

    def _load_positions(self):
        try:
            with open("positions.json") as f:
                data = json.load(f)
                # Reconstruct from saved data
                self.positions = []
                for p in data.get("open", []):
                    self.positions.append(Position(**p))
                for p in data.get("closed", []):
                    self.closed_positions.append(Position(**p))
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def _save_positions(self):
        with open("positions.json", "w") as f:
            json.dump({
                "open": [p.to_dict() for p in self.positions],
                "closed": [p.to_dict() for p in self.closed_positions],
            }, f, indent=2)

    # --------------------------------------------------------
    # JUPITER QUOTE (melhor rota)
    # --------------------------------------------------------
    async def get_quote(self, input_mint: str, output_mint: str,
                        amount: int, slippage_bps: int = None) -> Optional[Dict]:
        """
        Busca melhor rota de swap no Jupiter.
        amount: em lamports/smallest unit do token de entrada
        """
        if slippage_bps is None:
            slippage_bps = config.SLIPPAGE_BPS

        params = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": str(amount),
            "slippageBps": slippage_bps,
            "onlyDirectRoutes": False,
            "asLegacyTransaction": False,
        }

        try:
            resp = await self.client.get(
                f"{config.JUPITER_API_URL}/quote", params=params
            )
            resp.raise_for_status()
            quote = resp.json()

            logger.info(
                f"Jupiter Quote: {amount} → "
                f"{quote.get('outAmount', '?')} "
                f"(impact: {quote.get('priceImpactPct', '?')}%)"
            )
            return quote

        except Exception as e:
            logger.error(f"Jupiter quote error: {e}")
            return None

    # --------------------------------------------------------
    # JUPITER SWAP (execução)
    # --------------------------------------------------------
    async def execute_swap(self, quote: Dict) -> Optional[str]:
        """
        Executa o swap on-chain usando a quote do Jupiter.
        Retorna: tx_hash ou None
        
        ⚠️ Em PAPER_TRADING, simula a execução.
        """
        if config.PAPER_TRADING:
            return self._simulate_swap(quote)

        if not config.SOLANA_PRIVATE_KEY:
            logger.error("SOLANA_PRIVATE_KEY não configurada!")
            return None

        try:
            # 1. Pega a transação serializada do Jupiter
            swap_data = {
                "quoteResponse": quote,
                "userPublicKey": self._get_public_key(),
                "wrapAndUnwrapSol": True,
                "dynamicComputeUnitLimit": True,
                "prioritizationFeeLamports": "auto",
            }

            resp = await self.client.post(
                config.JUPITER_SWAP_URL, json=swap_data
            )
            resp.raise_for_status()
            swap_response = resp.json()

            swap_transaction = swap_response.get("swapTransaction")
            if not swap_transaction:
                logger.error("Jupiter não retornou transação")
                return None

            # 2. Assina e envia a transação
            tx_hash = await self._sign_and_send(swap_transaction)
            logger.info(f"✅ Swap executado! TX: {tx_hash}")
            return tx_hash

        except Exception as e:
            logger.error(f"Swap execution error: {e}")
            return None

    def _simulate_swap(self, quote: Dict) -> str:
        """Simula swap em paper trading."""
        fake_tx = f"PAPER_{int(time.time())}_{quote.get('outputMint', 'unknown')[:8]}"
        in_amount = int(quote.get("inAmount", 0))
        out_amount = int(quote.get("outAmount", 0))
        logger.info(
            f"[PAPER] Swap simulado: {in_amount} → {out_amount} | TX: {fake_tx}"
        )
        return fake_tx

    def _get_public_key(self) -> str:
        """Deriva public key da private key."""
        try:
            from solders.keypair import Keypair
            kp = Keypair.from_base58_string(config.SOLANA_PRIVATE_KEY)
            return str(kp.pubkey())
        except ImportError:
            logger.warning("solders não instalado - usando placeholder")
            return "YOUR_PUBLIC_KEY"

    async def _sign_and_send(self, swap_transaction: str) -> str:
        """Assina e envia transação para a Solana."""
        try:
            from solders.keypair import Keypair
            from solders.transaction import VersionedTransaction
            from solana.rpc.async_api import AsyncClient as SolanaClient

            # Decode
            raw_tx = base64.b64decode(swap_transaction)
            tx = VersionedTransaction.from_bytes(raw_tx)

            # Sign
            keypair = Keypair.from_base58_string(config.SOLANA_PRIVATE_KEY)
            tx.sign([keypair], tx.message.recent_blockhash)

            # Send
            client = SolanaClient(config.SOLANA_RPC_URL)
            result = await client.send_transaction(tx)
            await client.close()

            return str(result.value)

        except ImportError:
            logger.error("Instale: pip install solana solders")
            return "ERROR_NO_SOLANA_SDK"
        except Exception as e:
            logger.error(f"Sign/Send error: {e}")
            return f"ERROR_{e}"

    # --------------------------------------------------------
    # TRADE COMPLETO
    # --------------------------------------------------------
    async def open_position(self, signal, current_price: float) -> Optional[Position]:
        """
        Abre posição completa: calcula tamanho, faz swap, registra.
        """
        if len(self.positions) >= config.MAX_OPEN_POSITIONS:
            logger.warning("Máximo de posições atingido!")
            return None

        # Calcula capital por trade (usa risco ajustado pelo aprendizado)
        effective_risk = self.learning.get_effective_risk_per_trade() if self.learning else config.RISK_PER_TRADE
        risk_amount = config.CAPITAL_USDC * effective_risk
        risk_per_unit = abs(signal.entry_price - signal.stop_loss)
        if risk_per_unit <= 0:
            return None

        # Quanto investir em USDC
        invest_usdc = min(
            risk_amount / (risk_per_unit / signal.entry_price),
            config.CAPITAL_USDC * 0.3,  # Máximo 30% do capital por trade
        )

        if signal.direction == "long":
            # Compra: USDC → WBTC
            input_mint = config.TOKENS[config.BASE_TOKEN]
            output_mint = config.TOKENS[config.TRADE_TOKEN]
            # USDC tem 6 decimais
            amount_lamports = int(invest_usdc * 1_000_000)
        else:
            # Venda/Short: não suportado diretamente em DEX spot
            logger.warning("Short não suportado em DEX spot. Ignorando sinal de sell.")
            return None

        # Busca quote
        quote = await self.get_quote(input_mint, output_mint, amount_lamports)
        if not quote:
            return None

        # Executa swap
        tx_hash = await self.execute_swap(quote)
        if not tx_hash or tx_hash.startswith("ERROR"):
            return None

        # Calcula quantidade recebida
        out_amount = int(quote.get("outAmount", 0))
        # WBTC tem 8 decimais
        token_quantity = out_amount / 1e8

        position = Position(
            id=f"pos_{int(time.time())}",
            symbol=f"{config.TRADE_TOKEN}/{config.BASE_TOKEN}",
            direction=signal.direction,
            entry_price=current_price,
            current_price=current_price,
            quantity=token_quantity,
            quantity_base=invest_usdc,
            stop_loss=signal.stop_loss,
            take_profits=signal.take_profits,
            opened_at=datetime.utcnow().isoformat(),
            tx_hash=tx_hash,
        )

        self.positions.append(position)
        self._save_positions()

        logger.info(
            f"✅ Posição aberta: {signal.direction.upper()} "
            f"${invest_usdc:.2f} USDC → {token_quantity:.8f} {config.TRADE_TOKEN}"
        )
        return position

    async def close_position(self, position: Position, reason: str,
                              current_price: float) -> Optional[str]:
        """Fecha posição: vende token de volta para USDC."""
        if position.direction == "long":
            input_mint = config.TOKENS[config.TRADE_TOKEN]
            output_mint = config.TOKENS[config.BASE_TOKEN]
            amount_lamports = int(position.quantity * 1e8)
        else:
            return None

        quote = await self.get_quote(input_mint, output_mint, amount_lamports)
        if not quote:
            return None

        tx_hash = await self.execute_swap(quote)
        if not tx_hash:
            return None

        # Calcula P&L
        position.current_price = current_price
        position.pnl_pct = ((current_price - position.entry_price) / position.entry_price) * 100
        position.pnl_usd = position.quantity_base * (position.pnl_pct / 100)
        position.status = f"closed_{reason}"

        self.positions.remove(position)
        self.closed_positions.append(position)
        self._save_positions()

        logger.info(
            f"{'✅' if position.pnl_pct > 0 else '❌'} Posição fechada ({reason}): "
            f"P&L: {position.pnl_pct:+.2f}% (${position.pnl_usd:+.2f})"
        )
        return tx_hash

    # --------------------------------------------------------
    # MONITORAMENTO DE POSIÇÕES
    # --------------------------------------------------------
    async def check_positions(self, current_price: float) -> List[Dict]:
        """
        Verifica stop loss e take profits de todas as posições.
        Retorna lista de eventos (fechamentos).
        """
        events = []

        for pos in self.positions[:]:
            pos.current_price = current_price
            pos.pnl_pct = ((current_price - pos.entry_price) / pos.entry_price) * 100
            pos.pnl_usd = pos.quantity_base * (pos.pnl_pct / 100)

            # Stop Loss
            if pos.direction == "long" and current_price <= pos.stop_loss:
                tx = await self.close_position(pos, "sl", current_price)
                events.append({"type": "stop_loss", "position": pos.to_dict(), "tx": tx})
                continue

            # Take Profits
            for i, tp in enumerate(pos.take_profits):
                if pos.direction == "long" and current_price >= tp:
                    tx = await self.close_position(pos, f"tp{i+1}", current_price)
                    events.append({"type": f"take_profit_{i+1}", "position": pos.to_dict(), "tx": tx})
                    break

            # Trailing Stop
            if config.TRAILING_STOP and pos.direction == "long":
                new_sl = current_price * (1 - config.TRAILING_STOP_PCT)
                if new_sl > pos.stop_loss and current_price > pos.entry_price:
                    old_sl = pos.stop_loss
                    pos.stop_loss = new_sl
                    logger.info(f"Trailing stop: ${old_sl:.2f} → ${new_sl:.2f}")

        self._save_positions()
        return events

    # --------------------------------------------------------
    # DASHBOARD DATA
    # --------------------------------------------------------
    def get_dashboard_data(self, current_price: float) -> Dict:
        """Retorna dados para o dashboard do Telegram."""
        open_pnl = 0
        for p in self.positions:
            p.current_price = current_price
            p.pnl_pct = ((current_price - p.entry_price) / p.entry_price) * 100
            p.pnl_usd = p.quantity_base * (p.pnl_pct / 100)
            open_pnl += p.pnl_usd

        closed_pnl = sum(p.pnl_usd for p in self.closed_positions)
        wins = sum(1 for p in self.closed_positions if p.pnl_usd > 0)
        total_closed = len(self.closed_positions)

        return {
            "open_positions": len(self.positions),
            "positions": [p.to_dict() for p in self.positions],
            "open_pnl_usd": round(open_pnl, 2),
            "closed_pnl_usd": round(closed_pnl, 2),
            "total_pnl_usd": round(open_pnl + closed_pnl, 2),
            "total_trades": total_closed,
            "win_rate": f"{wins/total_closed*100:.0f}%" if total_closed > 0 else "N/A",
            "current_price": current_price,
        }
