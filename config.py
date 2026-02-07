"""
Configuração do Bot - Solana DEX Trading via Telegram
======================================================
OTIMIZADO PARA LUCRO - SOL/USDC
"""

# ============================================================
# TELEGRAM (opcional - funciona sem)
# ============================================================
TELEGRAM_BOT_TOKEN = ""          # Token do BotFather
TELEGRAM_CHAT_ID = ""            # Seu chat ID
AUTHORIZED_USERS = []            # Lista de user IDs autorizados

# ============================================================
# SOLANA
# ============================================================
SOLANA_PRIVATE_KEY = ""           # Private key Base58 (só para trades reais)
SOLANA_RPC_URL = "https://api.mainnet-beta.solana.com"

# ============================================================
# TOKENS - Solana Mint Addresses
# ============================================================
TOKENS = {
    "SOL": "So11111111111111111111111111111111111111112",
    "USDC": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "USDT": "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
    "WBTC": "3NZ9JMVBmGAqocybic2c7LQCJScmgsAZ6vQqTDzcqmJh",
    "JUP": "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
    "BONK": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
}

# ============================================================
# PAR DE TRADING - SOL/USDC (ALTA LIQUIDEZ!)
# ============================================================
BASE_TOKEN = "USDC"               # Token que você deposita
TRADE_TOKEN = "SOL"               # SOL = muito mais liquidez e volatilidade!

# ============================================================
# TRADING - OTIMIZADO PARA LUCRO
# ============================================================
TRADE_MODE = "day_trade"           # "day_trade" ou "swing_trade"

CAPITAL_USDC = 500.0               # Capital disponível em USDC
RISK_PER_TRADE = 0.015             # 1.5% de risco por trade (mais conservador)
MAX_OPEN_POSITIONS = 3             # Até 3 posições simultâneas
SLIPPAGE_BPS = 50                  # 0.5% slippage (SOL tem alta liquidez)

# ============================================================
# TIMEFRAMES - OTIMIZADOS
# ============================================================
TIMEFRAMES = {
    "day_trade": {
        "execution": "5m",         # Entrada precisa
        "confirmation": "15m",     # Confirma tendência
        "trend": "1h",             # Tendência maior
    },
    "swing_trade": {
        "execution": "1h",
        "confirmation": "4h",
        "trend": "1d",
    }
}

# ============================================================
# INDICADORES - EMAs
# ============================================================
EMA_PERIODS = [9, 21, 50, 200]

# ============================================================
# INDICADORES - ICHIMOKU
# ============================================================
ICHIMOKU_TENKAN = 9
ICHIMOKU_KIJUN = 26
ICHIMOKU_SENKOU_B = 52

# ============================================================
# INDICADORES - FIBONACCI
# ============================================================
FIBONACCI_LEVELS = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
FIBONACCI_LOOKBACK = 100

# ============================================================
# SISTEMA DE CONFLUÊNCIA - OTIMIZADO
# ============================================================
CONFLUENCE_THRESHOLD = 0.50        # 50% de confiança (era 65% - muito restritivo)
MIN_INDICATORS_AGREE = 3           # Mínimo de indicadores concordando

# Pesos dos indicadores - RSI e Volume agora incluídos!
INDICATOR_WEIGHTS = {
    "ichimoku_trend": 0.18,
    "ichimoku_signal": 0.12,
    "ema_alignment": 0.15,
    "ema_crossover": 0.10,
    "fibonacci_support": 0.12,
    "fibonacci_resistance": 0.08,
    "rsi": 0.15,                   # RSI muito importante!
    "volume": 0.10,                # Volume confirma movimento
}

# ============================================================
# GESTÃO DE RISCO - OTIMIZADA
# ============================================================
STOP_LOSS_TYPE = "dynamic"         # "fixed" ou "dynamic" (usa ATR)
FIXED_STOP_LOSS_PCT = 0.02         # 2% se fixo
TAKE_PROFIT_LEVELS = [1.0, 1.5, 2.0]  # R:R de 1:1, 1.5:1, 2:1
TRAILING_STOP = True               # Protege lucros
TRAILING_STOP_PCT = 0.015          # 1.5% trailing
MIN_RISK_REWARD = 1.2              # R:R mínimo 1.2:1 (era 1.5 - muito restritivo)

# ============================================================
# JUPITER DEX
# ============================================================
JUPITER_API_URL = "https://quote-api.jup.ag/v6"
JUPITER_SWAP_URL = "https://quote-api.jup.ag/v6/swap"
JUPITER_PRICE_URL = "https://price.jup.ag/v6/price"

# ============================================================
# DADOS DE PREÇO - GeckoTerminal (grátis, sem API key!)
# ============================================================
# Pool SOL/USDC com MAIOR LIQUIDEZ na Solana (Orca Whirlpool)
GECKO_POOL_ADDRESS = "FpCMFDFGYotvufJ7HrFHsWEiiQCGbkLCtwHiDnh7o28Q"

# ============================================================
# OPERAÇÃO
# ============================================================
PAPER_TRADING = True               # SEMPRE comece em True!
LOOP_INTERVAL_SECONDS = 45         # Intervalo entre análises (evita rate limit)
LOG_FILE = "trading_bot.log"
LOG_LEVEL = "INFO"

# ============================================================
# DASHBOARD
# ============================================================
DASHBOARD_UPDATE_INTERVAL = 60
SHOW_CHART_IN_DASHBOARD = True
