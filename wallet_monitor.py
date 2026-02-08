"""
Wallet Monitor - Consulta saldo real da carteira Solana
========================================================
Usa Solana JSON-RPC para buscar saldo SOL e USDC.
Modo read-only (só consulta, não executa transações).
"""

import logging
import time
from typing import Dict, Optional

logger = logging.getLogger("WalletMonitor")

# USDC Mint na Solana mainnet
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
# Token Program ID
TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"


class WalletMonitor:
    """Monitor read-only de saldo da carteira Solana."""

    def __init__(self, wallet_address: str, rpc_url: str = "https://api.mainnet-beta.solana.com"):
        self.wallet_address = wallet_address
        self.rpc_url = rpc_url
        self.last_sol_balance: float = 0.0
        self.last_usdc_balance: float = 0.0
        self.last_update: float = 0
        self.cache_ttl: int = 120  # Cache por 2 min (evita rate limit)
        self.connected: bool = False
        self.error: str = ""

    async def _rpc_call(self, method: str, params: list) -> Optional[Dict]:
        """Faz chamada JSON-RPC para a Solana."""
        import httpx
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params,
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(self.rpc_url, json=payload)
                data = resp.json()
                if "error" in data:
                    logger.debug(f"RPC error ({method}): {data['error']}")
                    return None
                return data.get("result")
        except Exception as e:
            logger.debug(f"RPC call failed ({method}): {e}")
            return None

    async def fetch_sol_balance(self) -> float:
        """Busca saldo SOL (em SOL, não lamports)."""
        result = await self._rpc_call("getBalance", [self.wallet_address])
        if result is not None:
            lamports = result.get("value", 0)
            return lamports / 1_000_000_000  # 1 SOL = 10^9 lamports
        return 0.0

    async def fetch_usdc_balance(self) -> float:
        """Busca saldo USDC da carteira."""
        result = await self._rpc_call("getTokenAccountsByOwner", [
            self.wallet_address,
            {"mint": USDC_MINT},
            {"encoding": "jsonParsed"},
        ])
        if result and "value" in result:
            accounts = result["value"]
            total = 0.0
            for acc in accounts:
                info = acc.get("account", {}).get("data", {}).get("parsed", {}).get("info", {})
                token_amount = info.get("tokenAmount", {})
                total += float(token_amount.get("uiAmount", 0))
            return total
        return 0.0

    async def update_balances(self) -> Dict:
        """Atualiza saldos (com cache para evitar rate limit)."""
        now = time.time()
        if now - self.last_update < self.cache_ttl:
            return self.get_data()

        try:
            self.last_sol_balance = await self.fetch_sol_balance()
            self.last_usdc_balance = await self.fetch_usdc_balance()
            self.last_update = now
            self.connected = True
            self.error = ""
            logger.info(f"Wallet: {self.last_sol_balance:.4f} SOL | {self.last_usdc_balance:.2f} USDC")
        except Exception as e:
            self.error = str(e)
            logger.debug(f"Wallet update error: {e}")

        return self.get_data()

    def get_data(self) -> Dict:
        """Retorna dados da carteira para dashboard/cloud push."""
        return {
            "address": self.wallet_address,
            "address_short": f"{self.wallet_address[:4]}...{self.wallet_address[-4:]}",
            "sol_balance": round(self.last_sol_balance, 6),
            "usdc_balance": round(self.last_usdc_balance, 2),
            "connected": self.connected,
            "last_update": self.last_update,
            "error": self.error,
        }
