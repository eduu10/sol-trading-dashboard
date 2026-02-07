# 🤖 Solana DEX Trading Bot (Telegram)

Bot de trading automatizado para **Solana** via **Jupiter DEX**, controlado pelo **Telegram**.
Opera BTC wrapped (WBTC/tBTC) com sistema de confluência de indicadores técnicos.

## 📋 Funcionalidades

- ✅ **Execução automática** de swaps via Jupiter Aggregator
- ✅ **Confluência de indicadores**: Ichimoku, Fibonacci, EMAs
- ✅ **Multi-timeframe**: analisa 5m, 15m, 1h (day trade) ou 1h, 4h, 1D (swing)
- ✅ **Dashboard** de posições abertas e P&L no Telegram
- ✅ **Stop Loss / Take Profit** monitorados on-chain
- ✅ **Paper Trading** para testar sem risco
- ✅ **Trailing Stop** dinâmico
- ✅ **Relatório de desempenho** com win rate e P&L

## 🏗️ Arquitetura

```
Telegram Bot (interface)
    ↓
Confluence Engine (IA + indicadores)
    ↓
Jupiter Aggregator API (melhor rota de swap)
    ↓
Solana Blockchain (execução on-chain)
```

## ⚙️ Setup

### 1. Requisitos
```bash
pip install python-telegram-bot solana solders httpx pandas numpy aiohttp
```

### 2. Configuração

Edite o arquivo `config.py`:

```python
# Telegram
TELEGRAM_BOT_TOKEN = "seu_token_do_botfather"
TELEGRAM_CHAT_ID = "seu_chat_id"

# Solana Wallet
SOLANA_PRIVATE_KEY = "sua_private_key_base58"
SOLANA_RPC_URL = "https://api.mainnet-beta.solana.com"

# Modo
PAPER_TRADING = True  # Comece em simulação!
```

### 3. Criar Bot no Telegram
1. Fale com [@BotFather](https://t.me/BotFather) no Telegram
2. Envie `/newbot` e siga as instruções
3. Copie o token e cole em `config.py`
4. Envie uma mensagem para o bot e pegue seu chat_id

### 4. Rodar
```bash
python main.py
```

## 📱 Comandos do Telegram

| Comando | Descrição |
|---------|-----------|
| `/start` | Iniciar bot e ver menu |
| `/status` | Dashboard: posições, saldo, P&L |
| `/config` | Ver/alterar configurações |
| `/mode day` | Mudar para Day Trade |
| `/mode swing` | Mudar para Swing Trade |
| `/paper on/off` | Ativar/desativar paper trading |
| `/force buy` | Forçar compra manual |
| `/force sell` | Forçar venda manual |
| `/stop` | Parar o bot |
| `/report` | Relatório de desempenho |

## ⚠️ Avisos Importantes

- **COMECE SEMPRE EM PAPER TRADING** (`PAPER_TRADING = True`)
- Este bot é experimental e educacional
- Nunca invista mais do que pode perder
- Teste extensivamente antes de usar dinheiro real
- A private key fica local — nunca compartilhe
- Use uma wallet dedicada só para o bot

## 🪙 Tokens Operados

| Token | Mint Address |
|-------|-------------|
| SOL | nativo |
| WBTC (Portal) | `3NZ9JMVBmGAqocybic2c7LQCJScmgsAZ6vQqTDzcqmJh` |
| tBTC (Threshold) | `6DNSN2BJsaPFdBAy4hg6vmNBtChqxaFX6jMgaveLgWkm` |
| USDC | `EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v` |
