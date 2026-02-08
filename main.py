"""
🤖 Solana DEX Trading Bot - Main (Telegram)
==============================================
Bot principal com interface Telegram, loop de análise,
e execução automática via Jupiter DEX.

Uso:
    python main.py
"""

import asyncio
import logging
import sys
import signal
import io
import os
import json
from datetime import datetime
from typing import Dict

# Fix Windows console encoding for emojis
if os.name == "nt":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import config
from indicators import get_all_scores
from confluence import ConfluenceEngine
from price_data import PriceDataFetcher
from jupiter_executor import JupiterExecutor
from dashboard import DashboardServer

# ============================================================
# LOGGING
# ============================================================
_handlers = [
    logging.StreamHandler(sys.stdout),
    logging.FileHandler(config.LOG_FILE, encoding="utf-8"),
]
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=_handlers,
)
logger = logging.getLogger("TradingBot")

# ============================================================
# CLOUD DASHBOARD PUSH CONFIG
# ============================================================
# URL do dashboard no Render (preencha apos deploy)
CLOUD_DASHBOARD_URL = os.environ.get("CLOUD_DASHBOARD_URL", "https://sol-trading-dashboard.onrender.com")
CLOUD_API_KEY = os.environ.get("DASHBOARD_API_KEY", "sol-trading-2026")


async def push_to_cloud(data: dict):
    """Envia dados do bot para o dashboard na nuvem via POST."""
    if not CLOUD_DASHBOARD_URL:
        return
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{CLOUD_DASHBOARD_URL}/api/push",
                json=data,
                headers={"X-API-Key": CLOUD_API_KEY},
            )
            if resp.status_code != 200:
                logger.debug(f"Cloud push failed: {resp.status_code}")
    except Exception as e:
        logger.debug(f"Cloud push error: {e}")


# ============================================================
# TELEGRAM BOT
# ============================================================
class TelegramBot:
    """Interface Telegram para o trading bot."""

    def __init__(self):
        self.base_url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}"
        self.offset = 0
        self.running = False

        # Módulos
        self.price_fetcher = PriceDataFetcher()
        self.confluence = ConfluenceEngine()
        self.executor = JupiterExecutor()

        # Estado
        self.auto_trading = True
        self.last_signal = None
        self.analysis_count = 0
        self.last_indicators = {}

        # Dashboard Web
        self.dashboard = DashboardServer(self)

    # --------------------------------------------------------
    # TELEGRAM API
    # --------------------------------------------------------
    async def send_message(self, text: str, parse_mode: str = "Markdown",
                           reply_markup: Dict = None):
        """Envia mensagem para todos os chat IDs configurados."""
        import httpx
        async with httpx.AsyncClient() as client:
            for chat_id in config.TELEGRAM_CHAT_IDS:
                msg_data = {
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": parse_mode,
                }
                if reply_markup:
                    msg_data["reply_markup"] = json.dumps(reply_markup)

                try:
                    resp = await client.post(f"{self.base_url}/sendMessage", data=msg_data)
                except Exception as e:
                    logger.error(f"Telegram send error (chat {chat_id}): {e}")

    async def get_updates(self):
        """Busca atualizações (mensagens) do Telegram."""
        import httpx
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await client.get(
                    f"{self.base_url}/getUpdates",
                    params={"offset": self.offset, "timeout": 10}
                )
                data = resp.json()
                updates = data.get("result", [])
                if updates:
                    self.offset = updates[-1]["update_id"] + 1
                return updates
            except Exception:
                return []

    # --------------------------------------------------------
    # COMANDOS
    # --------------------------------------------------------
    async def handle_command(self, text: str):
        """Processa comandos do Telegram."""
        cmd = text.strip().lower()

        if cmd == "/start":
            await self.cmd_start()
        elif cmd == "/status":
            await self.cmd_status()
        elif cmd == "/config":
            await self.cmd_config()
        elif cmd.startswith("/mode"):
            await self.cmd_mode(cmd)
        elif cmd.startswith("/paper"):
            await self.cmd_paper(cmd)
        elif cmd == "/force buy" or cmd == "/buy":
            await self.cmd_force_buy()
        elif cmd == "/force sell" or cmd == "/sell":
            await self.cmd_force_sell()
        elif cmd == "/stop":
            await self.cmd_stop()
        elif cmd == "/report":
            await self.cmd_report()
        elif cmd == "/positions":
            await self.cmd_positions()
        elif cmd == "/help":
            await self.cmd_help()
        else:
            await self.send_message(
                "❓ Comando não reconhecido. Use /help para ver os comandos."
            )

    async def cmd_start(self):
        mode = "PAPER 📝" if config.PAPER_TRADING else "LIVE 🔴"
        await self.send_message(
            f"🤖 *Solana DEX Trading Bot*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 Par: {config.TRADE_TOKEN}/{config.BASE_TOKEN}\n"
            f"🔗 DEX: Jupiter (Solana)\n"
            f"📈 Modo: {config.TRADE_MODE.replace('_', ' ').title()}\n"
            f"💰 Capital: ${config.CAPITAL_USDC:,.2f}\n"
            f"⚡ Status: {mode}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🟢 Bot iniciado! Analisando mercado...\n\n"
            f"Use /help para ver comandos."
        )

    async def cmd_status(self):
        """Dashboard completo."""
        price = await self.price_fetcher.get_current_price()
        dash = self.executor.get_dashboard_data(price)

        # Posições abertas
        pos_text = ""
        if dash["positions"]:
            for p in dash["positions"]:
                emoji = "🟢" if p["pnl_pct"] > 0 else "🔴"
                pos_text += (
                    f"\n{emoji} *{p['direction'].upper()}* "
                    f"${p['entry_price']:,.2f}\n"
                    f"   P&L: {p['pnl_pct']:+.2f}% (${p['pnl_usd']:+.2f})\n"
                    f"   SL: ${p['stop_loss']:,.2f} | "
                    f"TP: ${p['take_profits'][0]:,.2f}\n"
                )
        else:
            pos_text = "\n_Nenhuma posição aberta_\n"

        mode = "PAPER 📝" if config.PAPER_TRADING else "LIVE 🔴"
        pnl_emoji = "🟢" if dash["total_pnl_usd"] >= 0 else "🔴"

        await self.send_message(
            f"📊 *DASHBOARD*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💲 Preço {config.TRADE_TOKEN}: ${price:,.2f}\n"
            f"⚡ Modo: {mode}\n"
            f"🔄 Análises: {self.analysis_count}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"\n📌 *Posições Abertas ({dash['open_positions']}):*"
            f"{pos_text}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{pnl_emoji} *P&L Aberto:* ${dash['open_pnl_usd']:+,.2f}\n"
            f"📊 *P&L Fechado:* ${dash['closed_pnl_usd']:+,.2f}\n"
            f"💰 *P&L Total:* ${dash['total_pnl_usd']:+,.2f}\n"
            f"📈 *Win Rate:* {dash['win_rate']}\n"
            f"🔢 *Total Trades:* {dash['total_trades']}\n"
        )

    async def cmd_config(self):
        await self.send_message(
            f"⚙️ *Configuração Atual*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 Par: {config.TRADE_TOKEN}/{config.BASE_TOKEN}\n"
            f"📈 Modo: {config.TRADE_MODE}\n"
            f"💰 Capital: ${config.CAPITAL_USDC:,.2f}\n"
            f"⚠️ Risco/Trade: {config.RISK_PER_TRADE*100:.1f}%\n"
            f"📏 Max Posições: {config.MAX_OPEN_POSITIONS}\n"
            f"🎯 Confiança Mín: {config.CONFLUENCE_THRESHOLD*100:.0f}%\n"
            f"🛑 Stop Loss: {config.STOP_LOSS_TYPE}\n"
            f"📐 Trailing Stop: {'✅' if config.TRAILING_STOP else '❌'}\n"
            f"🔀 Slippage: {config.SLIPPAGE_BPS/100:.1f}%\n"
            f"⏱️ Intervalo: {config.LOOP_INTERVAL_SECONDS}s\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Timeframes:\n"
            f"  Execução: {config.TIMEFRAMES[config.TRADE_MODE]['execution']}\n"
            f"  Confirmação: {config.TIMEFRAMES[config.TRADE_MODE]['confirmation']}\n"
            f"  Tendência: {config.TIMEFRAMES[config.TRADE_MODE]['trend']}\n"
        )

    async def cmd_mode(self, cmd: str):
        parts = cmd.split()
        if len(parts) < 2:
            await self.send_message("Uso: `/mode day` ou `/mode swing`")
            return
        mode = parts[1]
        if mode == "day":
            config.TRADE_MODE = "day_trade"
        elif mode == "swing":
            config.TRADE_MODE = "swing_trade"
        else:
            await self.send_message("❌ Modo inválido. Use `day` ou `swing`.")
            return
        await self.send_message(f"✅ Modo alterado para: *{config.TRADE_MODE}*")

    async def cmd_paper(self, cmd: str):
        parts = cmd.split()
        if len(parts) < 2:
            status = "ATIVADO ✅" if config.PAPER_TRADING else "DESATIVADO ❌"
            await self.send_message(f"Paper Trading: {status}\nUse `/paper on` ou `/paper off`")
            return
        if parts[1] == "on":
            config.PAPER_TRADING = True
            await self.send_message("📝 Paper Trading *ATIVADO*. Trades serão simulados.")
        elif parts[1] == "off":
            config.PAPER_TRADING = False
            await self.send_message(
                "🔴 Paper Trading *DESATIVADO*.\n"
                "⚠️ *CUIDADO: Trades serão executados com dinheiro real!*"
            )

    async def cmd_force_buy(self):
        """Força uma compra manual."""
        price = await self.price_fetcher.get_current_price()
        if price <= 0:
            await self.send_message("❌ Não foi possível obter preço atual.")
            return

        # Cria sinal manual
        from confluence import TradeSignal
        sl = price * (1 - config.FIXED_STOP_LOSS_PCT)
        risk = abs(price - sl)
        tps = [price + risk * ext * 2 for ext in config.TAKE_PROFIT_LEVELS]

        signal = TradeSignal(
            timestamp=datetime.utcnow().isoformat(),
            symbol=f"{config.TRADE_TOKEN}/{config.BASE_TOKEN}",
            direction="long", confidence=1.0,
            entry_price=price, stop_loss=sl, take_profits=tps[:3],
            timeframe="manual", indicators_detail={},
            confluence_score=1.0, risk_reward_ratio=2.0,
        )

        pos = await self.executor.open_position(signal, price)
        if pos:
            await self.send_message(
                f"✅ *Compra executada!*\n"
                f"💰 Entrada: ${price:,.2f}\n"
                f"📦 Quantidade: {pos.quantity:.8f} {config.TRADE_TOKEN}\n"
                f"🛑 SL: ${sl:,.2f}\n"
                f"🔗 TX: `{pos.tx_hash}`"
            )
        else:
            await self.send_message("❌ Erro ao executar compra.")

    async def cmd_force_sell(self):
        """Força venda de todas as posições."""
        if not self.executor.positions:
            await self.send_message("📭 Nenhuma posição aberta para vender.")
            return

        price = await self.price_fetcher.get_current_price()
        closed = 0
        for pos in self.executor.positions[:]:
            tx = await self.executor.close_position(pos, "manual", price)
            if tx:
                closed += 1

        await self.send_message(f"✅ {closed} posição(ões) fechada(s) manualmente.")

    async def cmd_stop(self):
        self.running = False
        await self.send_message("⏹️ Bot parado. Posições abertas continuam ativas.")

    async def cmd_report(self):
        report = self.confluence.get_report()
        if report.get("total", 0) == 0:
            await self.send_message("📊 Sem trades registrados ainda.")
            return

        await self.send_message(
            f"📊 *Relatório de Desempenho*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📈 Total Trades: {report['total']}\n"
            f"✅ Wins: {report['wins']}\n"
            f"❌ Losses: {report['losses']}\n"
            f"🎯 Win Rate: {report['win_rate']}\n"
            f"💰 P&L Total: {report['total_pnl']}\n"
            f"📊 P&L Médio: {report['avg_pnl']}\n"
        )

    async def cmd_positions(self):
        if not self.executor.positions:
            await self.send_message("📭 Nenhuma posição aberta.")
            return
        await self.cmd_status()

    async def cmd_help(self):
        await self.send_message(
            "🤖 *Comandos Disponíveis*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "/start - Iniciar bot\n"
            "/status - Dashboard completo\n"
            "/positions - Posições abertas\n"
            "/config - Ver configurações\n"
            "/mode day|swing - Trocar modo\n"
            "/paper on|off - Paper trading\n"
            "/buy - Forçar compra\n"
            "/sell - Vender tudo\n"
            "/report - Relatório P&L\n"
            "/stop - Parar bot\n"
            "/help - Esta mensagem\n"
        )

    # --------------------------------------------------------
    # LOOP DE ANÁLISE
    # --------------------------------------------------------
    async def analysis_loop(self):
        """Loop principal de análise e execução."""
        logger.info("🔄 Loop de análise iniciado")

        while self.running:
            try:
                await self._run_analysis()
            except Exception as e:
                logger.error(f"Erro no loop de análise: {e}")

            await asyncio.sleep(config.LOOP_INTERVAL_SECONDS)

    async def _run_analysis(self):
        """Executa uma rodada de análise."""
        self.analysis_count += 1
        self.last_price = 0.0
        token_address = config.TOKENS[config.TRADE_TOKEN]

        # 1. Busca dados multi-timeframe
        data = await self.price_fetcher.fetch_multi_timeframe(token_address)

        if not data or "execution" not in data:
            logger.warning("Dados insuficientes para análise")
            return

        # 2. Calcula indicadores para cada timeframe
        scores_by_tf = {}
        for tf_name, df in data.items():
            if len(df) >= 50:  # Mínimo de candles
                scores_by_tf[tf_name] = get_all_scores(df)

        # Salva indicadores para o dashboard
        if "execution" in scores_by_tf:
            exec_scores = scores_by_tf["execution"]
            self.last_indicators = {
                "RSI": exec_scores.get("rsi", {}).get("value", 50),
                "EMA": exec_scores.get("ema_alignment", 0),
                "Ichimoku": exec_scores.get("ichimoku_trend", 0),
                "Volume": exec_scores.get("volume", {}).get("ratio", 1.0),
            }
            self.dashboard.add_log(f"RSI: {self.last_indicators['RSI']:.1f} | EMA: {self.last_indicators['EMA']:.2f}")

        if len(scores_by_tf) < 2:
            logger.warning("Timeframes insuficientes para confluência")
            return

        # 3. Gera sinal de confluência
        signal = self.confluence.generate_signal(
            f"{config.TRADE_TOKEN}/{config.BASE_TOKEN}",
            scores_by_tf,
            data["execution"]
        )

        # 4. Preço atual (usa último candle se possível, senão busca)
        current_price = float(data["execution"].iloc[-1]["close"]) if not data["execution"].empty else 0.0
        if current_price <= 0:
            current_price = await self.price_fetcher.get_current_price()
        self.last_price = current_price

        # 5. Verifica posições existentes (SL/TP)
        events = await self.executor.check_positions(current_price)
        for event in events:
            pos = event["position"]
            emoji = "🛑" if event["type"] == "stop_loss" else "🎯"
            await self.send_message(
                f"{emoji} *{event['type'].upper().replace('_', ' ')}*\n"
                f"P&L: {pos['pnl_pct']:+.2f}% (${pos['pnl_usd']:+.2f})\n"
                f"TX: `{event.get('tx', 'N/A')}`"
            )

        # 6. Executa novo trade se houver sinal
        if signal and self.auto_trading:
            self.last_signal = signal
            logger.info(
                f"🚨 Sinal detectado: {signal.direction.upper()} "
                f"confiança={signal.confidence:.0%}"
            )

            # Alerta no Telegram
            await self.send_message(signal.telegram_message())

            # Executa
            position = await self.executor.open_position(signal, current_price)
            if position:
                await self.send_message(
                    f"✅ *Trade Executado!*\n"
                    f"📦 {position.quantity:.8f} {config.TRADE_TOKEN}\n"
                    f"💵 Investido: ${position.quantity_base:,.2f}\n"
                    f"🔗 TX: `{position.tx_hash}`"
                )

        # Log periódico
        if self.analysis_count % 10 == 0:
            n_pos = len(self.executor.positions)
            logger.info(
                f"📊 Análise #{self.analysis_count} | "
                f"Preço: ${current_price:,.2f} | "
                f"Posições: {n_pos}"
            )

        # Push para dashboard na nuvem
        try:
            dashboard = self.executor.get_dashboard_data(current_price)
            last_signal = None
            if self.last_signal:
                last_signal = {
                    "direction": self.last_signal.direction,
                    "confidence": self.last_signal.confidence,
                    "entry_price": self.last_signal.entry_price,
                }
            cloud_data = {
                "price": current_price,
                "mode": config.TRADE_MODE.replace("_", " ").title(),
                "paper_trading": config.PAPER_TRADING,
                "analysis_count": self.analysis_count,
                "last_update": datetime.now().strftime("%H:%M:%S"),
                "open_positions": dashboard["open_positions"],
                "open_pnl": dashboard["open_pnl_usd"],
                "total_pnl": dashboard["total_pnl_usd"],
                "win_rate": dashboard["win_rate"],
                "total_trades": dashboard["total_trades"],
                "positions": dashboard.get("positions", []),
                "indicators": self.last_indicators,
                "last_signal": last_signal,
                "logs": self.dashboard.logs[-30:],
            }
            await push_to_cloud(cloud_data)
        except Exception as e:
            logger.debug(f"Cloud push prep error: {e}")

    # --------------------------------------------------------
    # LOOP DE TELEGRAM (recebe comandos)
    # --------------------------------------------------------
    async def telegram_loop(self):
        """Loop que escuta comandos do Telegram."""
        logger.info("📱 Telegram listener iniciado")

        while self.running:
            try:
                updates = await self.get_updates()
                for update in updates:
                    msg = update.get("message", {})
                    text = msg.get("text", "")
                    chat_id = str(msg.get("chat", {}).get("id", ""))

                    # Verifica se é um chat autorizado
                    if config.TELEGRAM_CHAT_IDS and chat_id not in [str(c) for c in config.TELEGRAM_CHAT_IDS]:
                        continue

                    if text.startswith("/"):
                        await self.handle_command(text)

            except Exception as e:
                logger.error(f"Telegram loop error: {e}")

            await asyncio.sleep(1)

    # --------------------------------------------------------
    # INICIAR / PARAR
    # --------------------------------------------------------
    async def start(self):
        """Inicia o bot."""
        self.running = True

        if not config.TELEGRAM_BOT_TOKEN:
            logger.error("❌ TELEGRAM_BOT_TOKEN não configurado no config.py!")
            logger.info("💡 Rodando em modo console (sem Telegram)...")
            await self._console_mode()
            return

        await self.send_message("🤖 Bot iniciando...")
        await self.cmd_start()

        # Roda loops em paralelo
        await asyncio.gather(
            self.analysis_loop(),
            self.telegram_loop(),
        )

    async def _console_mode(self):
        """Modo console para debug (sem Telegram)."""
        logger.info("=" * 50)
        logger.info("🤖 MODO CONSOLE (sem Telegram)")
        logger.info(f"📊 Par: {config.TRADE_TOKEN}/{config.BASE_TOKEN}")
        logger.info(f"📈 Modo: {config.TRADE_MODE}")
        logger.info(f"💰 Paper: {config.PAPER_TRADING}")
        logger.info("=" * 50)

        # Inicia dashboard web
        await self.dashboard.start(port=8080)
        logger.info("🌐 Dashboard: http://localhost:8080")
        logger.info("📤 Para compartilhar: npx localtunnel --port 8080")

        while self.running:
            try:
                await self._run_analysis()
                price = self.last_price if hasattr(self, 'last_price') and self.last_price > 0 else 0.0
                logger.info(f"💲 {config.TRADE_TOKEN}: ${price:,.2f}")
                self.dashboard.add_log(f"Preco: ${price:,.2f}")
            except Exception as e:
                logger.error(f"Erro: {e}")
                self.dashboard.add_log(f"ERRO: {e}")
            await asyncio.sleep(config.LOOP_INTERVAL_SECONDS)

    async def shutdown(self):
        """Desliga o bot graciosamente."""
        self.running = False
        await self.price_fetcher.close()
        await self.executor.close()
        logger.info("👋 Bot desligado")


# ============================================================
# MAIN
# ============================================================
async def main():
    bot = TelegramBot()

    # Handle SIGINT (Ctrl+C) - compatible with Windows
    if sys.platform != "win32":
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(bot.shutdown()))

    try:
        await bot.start()
    except KeyboardInterrupt:
        await bot.shutdown()


if __name__ == "__main__":
    print("""
+================================================+
|  Solana DEX Trading Bot (Telegram)             |
|  Jupiter Aggregator | Ichimoku + Fib + EMA     |
|  ----------------------------------------------  |
|  Configure config.py antes de rodar!           |
|  Comece SEMPRE em PAPER_TRADING = True         |
+================================================+
    """)
    asyncio.run(main())
