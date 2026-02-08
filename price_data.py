"""
Módulo de Dados de Preço
==========================
Busca candles OHLCV de tokens Solana via GeckoTerminal API (grátis, sem API key).
Fallback: DexScreener para preço atual.
"""

import httpx
import pandas as pd
import asyncio
import logging
from typing import Dict, Optional
from datetime import datetime, timedelta
import config

logger = logging.getLogger(__name__)

# ============================================================
# GeckoTerminal API - 100% grátis, sem API key
# ============================================================
GECKO_BASE_URL = "https://api.geckoterminal.com/api/v2"

# Mapeamento de timeframe para parâmetros do GeckoTerminal
# GeckoTerminal aceita: minute, hour, day com aggregate
GECKO_TF_MAP = {
    "1m":  {"timeframe": "minute", "aggregate": 1},
    "5m":  {"timeframe": "minute", "aggregate": 5},
    "15m": {"timeframe": "minute", "aggregate": 15},
    "30m": {"timeframe": "minute", "aggregate": 30},
    "1h":  {"timeframe": "hour",   "aggregate": 1},
    "4h":  {"timeframe": "hour",   "aggregate": 4},
    "1d":  {"timeframe": "day",    "aggregate": 1},
    "1w":  {"timeframe": "day",    "aggregate": 7},
}


class PriceDataFetcher:
    """Busca dados OHLCV para tokens Solana via GeckoTerminal (grátis)."""

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30)
        # Pool address principal para OHLCV (WBTC/USDC com mais liquidez)
        self.pool_address = config.GECKO_POOL_ADDRESS

    async def close(self):
        await self.client.aclose()

    # --------------------------------------------------------
    # GECKOTERMINAL OHLCV (principal - grátis)
    # --------------------------------------------------------
    async def fetch_ohlcv(self, timeframe: str = "5m",
                          limit: int = 300) -> pd.DataFrame:
        """
        Busca candles OHLCV via GeckoTerminal API.
        Grátis, sem API key. Rate limit: ~30 req/min.
        """
        tf_params = GECKO_TF_MAP.get(timeframe)
        if not tf_params:
            logger.warning(f"Timeframe {timeframe} nao suportado")
            return pd.DataFrame()

        # GeckoTerminal limita a 1000 candles por request
        limit = min(limit, 1000)

        url = (
            f"{GECKO_BASE_URL}/networks/solana/pools/"
            f"{self.pool_address}/ohlcv/{tf_params['timeframe']}"
        )
        params = {
            "aggregate": tf_params["aggregate"],
            "limit": limit,
            "currency": "usd",
        }
        headers = {"Accept": "application/json"}

        try:
            resp = await self.client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()

            ohlcv_list = (
                data.get("data", {})
                .get("attributes", {})
                .get("ohlcv_list", [])
            )

            if not ohlcv_list:
                logger.warning(
                    f"GeckoTerminal: sem dados para pool {self.pool_address} {timeframe}"
                )
                return pd.DataFrame()

            # Formato: [timestamp, open, high, low, close, volume]
            df = pd.DataFrame(
                ohlcv_list,
                columns=["timestamp", "open", "high", "low", "close", "volume"],
            )
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
            df = df.set_index("timestamp")
            df = df[["open", "high", "low", "close", "volume"]].astype(float)
            df = df.sort_index()

            logger.info(
                f"GeckoTerminal: {len(df)} candles {timeframe} recebidos"
            )
            return df

        except Exception as e:
            logger.error(f"GeckoTerminal OHLCV error: {e}")
            return pd.DataFrame()

    # --------------------------------------------------------
    # GECKOTERMINAL PREÇO ATUAL
    # --------------------------------------------------------
    async def fetch_gecko_price(self) -> Optional[float]:
        """Busca preço atual do pool via GeckoTerminal."""
        url = f"{GECKO_BASE_URL}/networks/solana/pools/{self.pool_address}"
        headers = {"Accept": "application/json"}

        try:
            resp = await self.client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()

            price_usd = (
                data.get("data", {})
                .get("attributes", {})
                .get("base_token_price_usd")
            )
            if price_usd:
                return float(price_usd)
            return None

        except Exception as e:
            logger.error(f"GeckoTerminal price error: {e}")
            return None

    # --------------------------------------------------------
    # DEXSCREENER PREÇO (fallback - grátis, sem key)
    # --------------------------------------------------------
    async def fetch_dexscreener_price(self) -> Optional[float]:
        """Busca preço atual via DexScreener (fallback)."""
        token_address = config.TOKENS[config.TRADE_TOKEN]
        url = f"https://api.dexscreener.com/tokens/v1/solana/{token_address}"

        try:
            resp = await self.client.get(url)
            resp.raise_for_status()
            data = resp.json()

            if isinstance(data, list) and data:
                price = data[0].get("priceUsd")
                if price:
                    return float(price)
            return None

        except Exception as e:
            logger.error(f"DexScreener price error: {e}")
            return None

    # --------------------------------------------------------
    # MULTI-TIMEFRAME
    # --------------------------------------------------------
    async def fetch_multi_timeframe(self, token_address: str = None) -> Dict[str, pd.DataFrame]:
        """
        Busca dados para todos os timeframes configurados.
        Retorna: {"execution": df, "confirmation": df, "trend": df}
        """
        tfs = config.TIMEFRAMES[config.TRADE_MODE]
        data = {}

        for tf_name, tf_value in tfs.items():
            logger.info(f"Buscando candles {tf_value} para {config.TRADE_TOKEN}...")
            df = await self.fetch_ohlcv(tf_value)
            if not df.empty:
                data[tf_name] = df
            await asyncio.sleep(5.0)  # Rate limit GeckoTerminal (~30 req/min)

        return data

    # --------------------------------------------------------
    # PREÇO ATUAL
    # --------------------------------------------------------
    async def get_current_price(self) -> float:
        """Retorna preço atual do token de trade."""
        # 1. DexScreener (primário - mais generoso no rate limit)
        price = await self.fetch_dexscreener_price()
        if price and price > 0:
            return price

        # 2. Fallback: GeckoTerminal
        price = await self.fetch_gecko_price()
        if price and price > 0:
            return price

        # 3. Fallback: último candle
        df = await self.fetch_ohlcv("1m", limit=5)
        if not df.empty:
            return float(df.iloc[-1]["close"])

        return 0.0
