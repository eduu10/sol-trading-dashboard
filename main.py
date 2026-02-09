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
from datetime import datetime, timezone, timedelta
from typing import Dict

BR_TZ = timezone(timedelta(hours=-3))

def now_br():
    return datetime.now(BR_TZ)

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
from learning_engine import LearningEngine
from strategies_manager import StrategiesManager
from wallet_monitor import WalletMonitor

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


async def push_to_cloud(data: dict) -> list:
    """Envia dados do bot para o dashboard na nuvem via POST. Retorna comandos pendentes."""
    if not CLOUD_DASHBOARD_URL:
        return []
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{CLOUD_DASHBOARD_URL}/api/push",
                json=data,
                headers={"X-API-Key": CLOUD_API_KEY},
            )
            if resp.status_code == 200:
                result = resp.json()
                return result.get("commands", [])
            else:
                logger.debug(f"Cloud push failed: {resp.status_code}")
    except Exception as e:
        logger.debug(f"Cloud push error: {e}")
    return []


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
        self.learning = LearningEngine()
        self.confluence = ConfluenceEngine(learning_engine=self.learning)
        self.executor = JupiterExecutor(learning_engine=self.learning)

        # Estado
        self.auto_trading = True
        self.last_signal = None
        self.analysis_count = 0
        self.last_indicators = {}
        self.last_hourly_price_hour = -1  # Track last hour we sent price update
        self.last_daily_review_hour = -1  # Track daily review
        self.analysis_history = []  # Last N analyses for dashboard

        # Dashboard Web
        self.dashboard = DashboardServer(self)

        # Estrategias de teste (5 variacoes de day trade)
        self.strategies = StrategiesManager()

        # Monitor de carteira Phantom (read-only)
        self.wallet = WalletMonitor(
            wallet_address=config.SOLANA_WALLET_ADDRESS,
            rpc_url=config.SOLANA_RPC_URL,
        ) if config.SOLANA_WALLET_ADDRESS else None

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
        elif cmd == "/learn":
            await self.cmd_learn()
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

    async def cmd_learn(self):
        """Mostra status do aprendizado."""
        report = self.learning.get_telegram_report()
        await self.send_message(report)

        # Tenta fazer revisao diaria se ainda nao fez
        daily = self.learning.daily_review()
        if daily:
            summary = self.learning.get_daily_summary()
            if summary:
                await self.send_message(summary)

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
            "/learn - Status do aprendizado AI\n"
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

        # 3. Calcula confluência (sempre, para mostrar análise)
        conf = self.confluence.calculate_confluence(scores_by_tf)

        # 4. Preço atual (usa último candle se possível, senão busca)
        current_price = float(data["execution"].iloc[-1]["close"]) if not data["execution"].empty else 0.0
        if current_price <= 0:
            current_price = await self.price_fetcher.get_current_price()
        self.last_price = current_price

        # 4.1 Envia preço do SOL a cada hora no Telegram
        current_hour = now_br().hour
        if current_hour != self.last_hourly_price_hour and current_price > 0:
            self.last_hourly_price_hour = current_hour
            n_pos = len(self.executor.positions)
            dash = self.executor.get_dashboard_data(current_price)
            await self.send_message(
                f"🕐 *ATUALIZAÇÃO HORÁRIA*\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"💲 SOL: *${current_price:,.2f}*\n"
                f"💰 Capital: *${config.CAPITAL_USDC:,.2f}*\n"
                f"📊 P&L Total: *${dash['total_pnl_usd']:+,.2f}*\n"
                f"📈 Posições: {n_pos} | Trades: {dash['total_trades']}\n"
                f"🔄 Análises: {self.analysis_count}\n"
                f"⏰ {now_br().strftime('%H:%M - %d/%m/%Y')}\n"
            )

            # Envia saldo da carteira Phantom
            wallet_data = self.wallet.get_data() if self.wallet else {}
            if self.wallet and wallet_data.get("connected"):
                sol_bal = wallet_data.get("sol_balance", 0)
                usdc_bal = wallet_data.get("usdc_balance", 0)
                sol_usd = sol_bal * current_price if current_price > 0 else 0
                total_usd = sol_usd + usdc_bal
                addr_short = wallet_data.get("address_short", "")
                await self.send_message(
                    f"👛 *CARTEIRA PHANTOM*\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"🔑 `{addr_short}`\n"
                    f"◎ SOL: *{sol_bal:.4f}* (~${sol_usd:,.2f})\n"
                    f"💵 USDC: *${usdc_bal:,.2f}*\n"
                    f"💎 Total: *${total_usd:,.2f}*\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"📖 Modo: Somente leitura"
                )

            # Envia resumo das estrategias de teste
            try:
                strats = self.strategies.get_all_dashboard_data()
                strat_lines = []
                for key, label, emoji in [
                    ("sniper", "Sniper", "🎯"),
                    ("memecoin", "MemeCoin", "🐸"),
                    ("arbitrage", "Arbitragem", "🔄"),
                    ("scalping", "Scalping", "⚡"),
                    ("leverage", "Leverage", "📊"),
                ]:
                    s = strats.get(key, {})
                    cap = s.get("capital", {})
                    cur = cap.get("current", 100)
                    pnl = cap.get("pnl_usd", 0)
                    today = cap.get("today_pnl", 0)
                    invested = cap.get("total_invested", 0)
                    gains = cap.get("total_gains", 0)
                    losses = cap.get("total_losses", 0)
                    pnl_emoji = "🟢" if pnl >= 0 else "🔴"
                    strat_lines.append(
                        f"{emoji} *{label}*\n"
                        f"   💰 ${cur:.2f} | P&L: {pnl_emoji} ${pnl:+.2f}\n"
                        f"   📥 Inv: ${invested:.2f} | ✅ ${gains:.2f} | ❌ ${losses:.2f}\n"
                        f"   📅 Hoje: ${today:+.2f}"
                    )
                strat_msg = "\n".join(strat_lines)
                await self.send_message(
                    f"📋 *ESTRATÉGIAS DE TESTE*\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"{strat_msg}\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"💵 Capital inicial: $100 cada"
                )
            except Exception as e:
                logger.debug(f"Strategies telegram error: {e}")

        # 5. Monta relatório de análise (sempre mostra)
        direction_emoji = "🟢" if conf["direction"] == "long" else "🔴"
        confidence_pct = conf["confidence"] * 100
        agreeing = conf["agreeing_indicators"]
        total_ind = len(conf["combined_scores"])

        # Barra de confiança visual
        bar_filled = int(confidence_pct / 10)
        bar_empty = 10 - bar_filled
        bar = "█" * bar_filled + "░" * bar_empty

        # Indicadores individuais
        ind_lines = []
        for ind_name, score in sorted(conf["combined_scores"].items(), key=lambda x: abs(x[1]), reverse=True):
            if score > 0.1:
                ind_lines.append(f"  🟢 {ind_name}: +{score:.2f}")
            elif score < -0.1:
                ind_lines.append(f"  🔴 {ind_name}: {score:.2f}")
            else:
                ind_lines.append(f"  ⚪ {ind_name}: {score:.2f}")
        ind_text = "\n".join(ind_lines)

        # RSI e Volume detalhados
        exec_scores = scores_by_tf.get("execution", {})
        rsi_val = exec_scores.get("rsi", {}).get("value", 50)
        vol_ratio = exec_scores.get("volume", {}).get("ratio", 1.0)
        rsi_emoji = "🟢" if 30 < rsi_val < 70 else "🔴"
        vol_emoji = "🟢" if vol_ratio > 0.8 else "🔴"

        # Info do aprendizado
        learn_threshold = self.learning.get_effective_threshold() * 100
        risk_lvl = self.learning.state.get("current_risk_level", 1.0)
        shadow_w = self.learning.state.get("shadow_wins", 0)
        shadow_l = self.learning.state.get("shadow_losses", 0)
        open_shadows = sum(1 for t in self.learning.shadow_trades if t["status"] == "open")

        analysis_msg = (
            f"📊 *ANÁLISE #{self.analysis_count}*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💲 {config.TRADE_TOKEN}: *${current_price:,.2f}*\n"
            f"{direction_emoji} Direção: *{conf['direction'].upper()}*\n"
            f"📈 Confiança: *{confidence_pct:.1f}%* [{bar}]\n"
            f"🎯 Indicadores: {agreeing}/{total_ind} concordam\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{rsi_emoji} RSI: {rsi_val:.1f}\n"
            f"{vol_emoji} Volume: {vol_ratio:.2f}x\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{ind_text}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🧠 *AI Learning:*\n"
            f"  Threshold: {learn_threshold:.0f}% | Risco: {risk_lvl:.1f}x\n"
            f"  Shadow: {shadow_w}W/{shadow_l}L ({open_shadows} abertos)\n"
        )

        # Envia análise a cada 5 ciclos (para não spammar)
        if self.analysis_count % 5 == 0:
            await self.send_message(analysis_msg)

        logger.info(
            f"📊 Análise #{self.analysis_count} | "
            f"${current_price:,.2f} | "
            f"{conf['direction'].upper()} {confidence_pct:.0f}% | "
            f"{agreeing}/{total_ind} ind"
        )

        # 5.1 Salva análise no histórico para o dashboard
        rejection_reason_preview = getattr(self.confluence, 'last_rejection_reason', '')
        analysis_entry = {
            "num": self.analysis_count,
            "time": now_br().strftime("%H:%M:%S"),
            "price": round(current_price, 2),
            "direction": conf["direction"],
            "confidence": round(confidence_pct, 1),
            "agreeing": agreeing,
            "total": total_ind,
            "rsi": round(rsi_val, 1),
            "volume": round(vol_ratio, 2),
            "scores": {k: round(v, 3) for k, v in conf["combined_scores"].items()},
            "signal": False,  # updated below if signal generated
            "reason": "",
            "threshold": round(self.learning.get_effective_threshold() * 100, 1),
            "risk_level": self.learning.state.get("current_risk_level", 1.0),
        }
        self.analysis_history.append(analysis_entry)
        if len(self.analysis_history) > 50:
            self.analysis_history = self.analysis_history[-50:]

        # 6. Verifica posições existentes (SL/TP)
        events = await self.executor.check_positions(current_price)
        for event in events:
            pos = event["position"]
            emoji = "🛑" if event["type"] == "stop_loss" else "🎯"
            await self.send_message(
                f"{emoji} *{event['type'].upper().replace('_', ' ')}*\n"
                f"P&L: {pos['pnl_pct']:+.2f}% (${pos['pnl_usd']:+.2f})\n"
                f"TX: `{event.get('tx', 'N/A')}`"
            )

        # 7. Gera sinal completo e executa trade
        signal = self.confluence.generate_signal(
            f"{config.TRADE_TOKEN}/{config.BASE_TOKEN}",
            scores_by_tf,
            data["execution"]
        )

        # 7.1 APRENDIZADO: Registra TODA analise (com ou sem sinal)
        rejection_reason = getattr(self.confluence, 'last_rejection_reason', '') if not signal else ''
        self.learning.record_analysis(
            price=current_price,
            conf=conf,
            scores_by_tf=scores_by_tf,
            signal_generated=signal is not None,
            rejection_reason=rejection_reason,
            analysis_number=self.analysis_count,
        )

        # Atualiza análise no histórico com resultado do sinal
        if self.analysis_history:
            self.analysis_history[-1]["signal"] = signal is not None
            self.analysis_history[-1]["reason"] = rejection_reason

        # 7.2 APRENDIZADO: Atualiza precos futuros de analises anteriores
        self.learning.update_future_prices(current_price)

        # 7.3 APRENDIZADO: Atualiza shadow trades
        self.learning.update_shadow_trades(current_price)

        # 7.4 APRENDIZADO: Se nao gerou sinal mas esta perto, abre shadow trade
        if not signal and self.learning.should_open_shadow_trade(conf):
            # Calcula SL/TP para o shadow trade
            try:
                exec_scores_shadow = scores_by_tf.get("execution", {})
                shadow_sl = self.confluence.calculate_stop_loss(
                    current_price, conf["direction"], exec_scores_shadow, data["execution"]
                )
                shadow_tps = self.confluence.calculate_take_profits(
                    current_price, conf["direction"], shadow_sl, exec_scores_shadow
                )
                self.learning.open_shadow_trade(
                    conf, current_price, scores_by_tf, shadow_sl, shadow_tps
                )
            except Exception as e:
                logger.debug(f"Shadow trade error: {e}")

        # 7.5 APRENDIZADO: Revisao diaria (1x por dia, as 00:00 UTC)
        current_review_hour = now_br().hour
        if current_review_hour == 0 and self.last_daily_review_hour != 0:
            report = self.learning.daily_review()
            if report:
                summary = self.learning.get_daily_summary()
                if summary:
                    await self.send_message(summary)
                    learning_report = self.learning.get_telegram_report()
                    await self.send_message(learning_report)
        self.last_daily_review_hour = current_review_hour

        if signal and self.auto_trading:
            self.last_signal = signal

            # ENTRADA DETECTADA - mensagem com ênfase!
            risk_level = self.learning.state.get("current_risk_level", 1.0)
            risk_emoji = "🟢" if risk_level >= 1.0 else "🟡" if risk_level >= 0.5 else "🔴"
            entry_msg = (
                f"🚨🚨🚨 *ENTRADA DETECTADA!* 🚨🚨🚨\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"{'🟢 COMPRA (LONG)' if signal.direction == 'long' else '🔴 VENDA (SHORT)'}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"💰 *Entrada:* ${signal.entry_price:,.2f}\n"
                f"🛑 *Stop Loss:* ${signal.stop_loss:,.2f}\n"
            )
            for i, tp in enumerate(signal.take_profits):
                entry_msg += f"🎯 *TP{i+1}:* ${tp:,.2f}\n"
            entry_msg += (
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"📈 Confiança: *{signal.confidence:.0%}*\n"
                f"⚖️ Risco/Retorno: *{signal.risk_reward_ratio:.1f}:1*\n"
                f"{risk_emoji} Risco AI: *{risk_level:.1f}x*\n"
                f"🧠 Dias aprendendo: *{self.learning.state.get('days_learning', 0)}*\n"
                f"🔗 DEX: Jupiter (Solana)\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
            )

            await self.send_message(entry_msg)

            # Executa o trade (usa risco ajustado pelo aprendizado)
            position = await self.executor.open_position(signal, current_price)
            if position:
                await self.send_message(
                    f"✅✅✅ *TRADE EXECUTADO!* ✅✅✅\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"📦 Quantidade: {position.quantity:.8f} {config.TRADE_TOKEN}\n"
                    f"💵 Investido: ${position.quantity_base:,.2f}\n"
                    f"💰 Entrada: ${current_price:,.2f}\n"
                    f"🔗 TX: `{position.tx_hash}`\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                )
            else:
                await self.send_message("❌ Erro ao executar trade. Verifique os logs.")

        # Snapshot trade counts ANTES da simulacao
        before_counts = self.strategies.snapshot_trade_counts()

        # Roda simulacao das 5 estrategias de teste
        try:
            await self.strategies.run_simulation_cycle()
        except Exception as e:
            logger.debug(f"Strategies simulation error: {e}")

        # Atualiza saldo da carteira ANTES dos trades reais (necessário para auto-funding)
        wallet_data = {}
        if self.wallet:
            try:
                wallet_data = await self.wallet.update_balances()
            except Exception as e:
                logger.debug(f"Wallet update error: {e}")

        # MODO REAL: detecta novos trades e executa swaps reais via Jupiter
        try:
            signals = self.strategies.get_new_trade_signals(before_counts)

            # Auto-funding: se tem sinais e pouco USDC, converte SOL->USDC
            if signals and not config.PAPER_TRADING:
                usdc_bal = self.wallet.last_usdc_balance if self.wallet else 0
                sol_bal = self.wallet.last_sol_balance if self.wallet else 0
                total_needed = sum(s["amount_usd"] for s in signals)
                if usdc_bal < total_needed and sol_bal > 0.01:
                    fund_usd = total_needed - usdc_bal + 0.01  # pequena margem
                    sol_price = current_price if current_price > 0 else 100
                    sol_needed = fund_usd / sol_price
                    # Garante que não usa mais que 90% do SOL (reserva para fees)
                    sol_to_sell = min(sol_needed, sol_bal * 0.9)
                    sol_lamports = int(sol_to_sell * (10 ** 9))
                    if sol_lamports > 0:
                        logger.info(
                            f"[MODO REAL] Auto-funding: vendendo {sol_to_sell:.6f} SOL "
                            f"(~${fund_usd:.2f}) para USDC"
                        )
                        sol_mint = config.TOKENS["SOL"]
                        usdc_mint_f = config.TOKENS["USDC"]
                        fund_quote = await self.executor.get_quote(
                            sol_mint, usdc_mint_f, sol_lamports
                        )
                        if fund_quote:
                            fund_tx = await self.executor.execute_swap(fund_quote)
                            if fund_tx:
                                funded = int(fund_quote.get("outAmount", 0)) / (10 ** 6)
                                logger.info(
                                    f"[MODO REAL] Auto-funding OK: +${funded:.4f} USDC | TX: {fund_tx}"
                                )
                                # Atualiza saldo USDC em memoria
                                if self.wallet:
                                    self.wallet.last_usdc_balance += funded
                                    self.wallet.last_sol_balance -= sol_to_sell
                            else:
                                logger.warning("[MODO REAL] Auto-funding: falha no swap SOL->USDC")
                        else:
                            logger.warning("[MODO REAL] Auto-funding: sem quote SOL->USDC")

            for sig in signals:
                strat_key = sig["strategy"]
                coin = sig["coin"]
                amount_usd = sig["amount_usd"]
                direction = sig["direction"]
                sim_pnl_pct = sig["sim_pnl_pct"]
                trade_id = sig["trade_id"]

                logger.info(
                    f"[MODO REAL] Executando trade real: {strat_key} "
                    f"${amount_usd:.2f} {coin} | dir={direction}"
                )

                # Resolve mint addresses
                coin_mint = config.TOKENS.get(coin, config.TOKENS["SOL"])
                usdc_mint = config.TOKENS["USDC"]

                # Decimals: USDC=6, SOL=9, outros=variavel
                decimals = {"SOL": 9, "USDC": 6, "USDT": 6, "WBTC": 8, "JUP": 6, "BONK": 5}
                coin_decimals = decimals.get(coin, 9)

                real_pnl = 0.0
                tx_buy = None
                tx_sell = None

                try:
                    # === PASSO 1: Compra (USDC -> Coin) ===
                    buy_amount_lamports = int(amount_usd * (10 ** 6))  # USDC has 6 decimals
                    buy_quote = await self.executor.get_quote(
                        usdc_mint, coin_mint, buy_amount_lamports
                    )
                    if not buy_quote:
                        logger.warning(f"[MODO REAL] {strat_key}: sem quote para compra")
                        continue

                    tx_buy = await self.executor.execute_swap(buy_quote)
                    if not tx_buy:
                        logger.warning(f"[MODO REAL] {strat_key}: falha na compra")
                        continue

                    coins_received = int(buy_quote.get("outAmount", 0))
                    logger.info(
                        f"[MODO REAL] {strat_key}: COMPROU {coins_received} {coin} "
                        f"(${amount_usd:.2f} USDC) | TX: {tx_buy}"
                    )

                    # === PASSO 2: Vende imediatamente (Coin -> USDC) ===
                    sell_quote = await self.executor.get_quote(
                        coin_mint, usdc_mint, coins_received
                    )
                    if not sell_quote:
                        logger.warning(
                            f"[MODO REAL] {strat_key}: sem quote para venda! "
                            f"Posicao aberta: {coins_received} {coin}"
                        )
                        # Registra trade parcial (so compra)
                        self.strategies.update_allocation_after_trade(
                            strat_key, tx_buy, 0.0,
                            tx_buy=tx_buy, tx_sell="", amount_usd=amount_usd,
                            coin=coin, direction=direction, sim_pnl_pct=sim_pnl_pct
                        )
                        self.strategies.mark_trade_executed(strat_key, trade_id, tx_buy)
                        continue

                    tx_sell = await self.executor.execute_swap(sell_quote)
                    if not tx_sell:
                        logger.warning(
                            f"[MODO REAL] {strat_key}: falha na venda! "
                            f"Posicao aberta: {coins_received} {coin}"
                        )
                        self.strategies.update_allocation_after_trade(
                            strat_key, tx_buy, 0.0,
                            tx_buy=tx_buy, tx_sell="", amount_usd=amount_usd,
                            coin=coin, direction=direction, sim_pnl_pct=sim_pnl_pct
                        )
                        self.strategies.mark_trade_executed(strat_key, trade_id, tx_buy)
                        continue

                    usdc_received = int(sell_quote.get("outAmount", 0)) / (10 ** 6)
                    real_pnl = round(usdc_received - amount_usd, 4)

                    logger.info(
                        f"[MODO REAL] {strat_key}: VENDEU → ${usdc_received:.4f} USDC | "
                        f"PNL: ${real_pnl:+.4f} | TX: {tx_sell}"
                    )

                except Exception as ex:
                    logger.error(f"[MODO REAL] {strat_key}: erro no swap: {ex}")
                    if tx_buy:
                        self.strategies.update_allocation_after_trade(
                            strat_key, tx_buy, 0.0,
                            tx_buy=tx_buy or "", tx_sell="", amount_usd=amount_usd,
                            coin=coin, direction=direction, sim_pnl_pct=sim_pnl_pct
                        )
                    continue

                # Atualiza alocacao com resultado real
                final_tx = tx_sell or tx_buy or "ERROR"
                self.strategies.update_allocation_after_trade(
                    strat_key, final_tx, real_pnl,
                    tx_buy=tx_buy or "", tx_sell=tx_sell or "",
                    amount_usd=amount_usd, coin=coin,
                    direction=direction, sim_pnl_pct=sim_pnl_pct
                )
                self.strategies.mark_trade_executed(strat_key, trade_id, final_tx)

                # Notificacao Telegram
                trade_num = self.strategies.allocations.get(strat_key, {}).get("trades", 0)
                pnl_emoji = "🟢" if real_pnl >= 0 else "🔴"
                await self.send_message(
                    f"💰 *MODO REAL* - {strat_key}\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"Trade #{trade_num} executado!\n"
                    f"📦 Capital: ${amount_usd:.2f} {coin}\n"
                    f"{pnl_emoji} PNL Real: ${real_pnl:+.4f}\n"
                    f"📊 PNL Sim: {sim_pnl_pct:+.1f}%\n"
                    f"🔗 Buy TX: `{tx_buy}`\n"
                    f"🔗 Sell TX: `{tx_sell}`\n"
                    f"━━━━━━━━━━━━━━━━━━━━"
                )

        except Exception as e:
            logger.error(f"Real trade execution error: {e}", exc_info=True)

        # Auto-retirada de lucro: quando PNL total >= R$260, transfere R$150 em SOL para carteira spot
        try:
            await self._check_profit_withdraw(current_price)
        except Exception as e:
            logger.debug(f"Profit withdraw check error: {e}")

        # Atualiza wallet DEPOIS dos trades para refletir saldos reais
        if self.wallet:
            try:
                self.wallet.last_update = 0  # Invalida cache
                wallet_data = await self.wallet.update_balances()
            except Exception as e:
                logger.debug(f"Wallet post-trade update error: {e}")

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
                "capital": config.CAPITAL_USDC,
                "mode": config.TRADE_MODE.replace("_", " ").title(),
                "paper_trading": config.PAPER_TRADING,
                "analysis_count": self.analysis_count,
                "last_update": now_br().strftime("%H:%M:%S"),
                "open_positions": dashboard["open_positions"],
                "open_pnl": dashboard["open_pnl_usd"],
                "total_pnl": dashboard["total_pnl_usd"],
                "win_rate": dashboard["win_rate"],
                "total_trades": dashboard["total_trades"],
                "positions": dashboard.get("positions", []),
                "indicators": self.last_indicators,
                "last_signal": last_signal,
                "confluence": {
                    "direction": conf["direction"],
                    "confidence": round(conf["confidence"] * 100, 1),
                    "agreeing": conf["agreeing_indicators"],
                    "scores": {k: round(v, 3) for k, v in conf["combined_scores"].items()},
                },
                "logs": self.dashboard.logs[-30:],
                "learning": {
                    "days": self.learning.state.get("days_learning", 0),
                    "risk_level": self.learning.state.get("current_risk_level", 1.0),
                    "threshold": round(self.learning.get_effective_threshold() * 100, 1),
                    "shadow_wins": self.learning.state.get("shadow_wins", 0),
                    "shadow_losses": self.learning.state.get("shadow_losses", 0),
                    "missed_opps": self.learning.state.get("missed_opportunities", 0),
                    "dodged": self.learning.state.get("dodged_bullets", 0),
                    "streak": self.learning.state.get("streak", 0),
                    "total_analyses": self.learning.state.get("total_analyses", 0),
                },
                "analysis_history": self.analysis_history[-20:],
                "strategies": self.strategies.get_all_dashboard_data(),
                "wallet": wallet_data,
                "allocations": self.strategies.get_all_allocations(),
                "pk_mask": (config.SOLANA_PRIVATE_KEY[:4] + "..." + config.SOLANA_PRIVATE_KEY[-4:]) if len(config.SOLANA_PRIVATE_KEY) > 8 else "",
                "settings_applied": getattr(self, '_settings_applied', False),
            }
            commands = await push_to_cloud(cloud_data)
            self._settings_applied = False
            # Processa comandos do dashboard na nuvem
            for cmd in commands:
                action = cmd.get("action", "")
                if action == "toggle_strategy":
                    key = cmd.get("strategy", "")
                    self.strategies.toggle_strategy(key)
                elif action == "allocate_strategy":
                    key = cmd.get("strategy", "")
                    amount = float(cmd.get("amount", 0))
                    coin = cmd.get("coin", "SOL")
                    if self.strategies.allocate_strategy(key, amount, coin):
                        logger.info(f"Alocacao real: ${amount:.2f} {coin} -> {key}")
                elif action == "deallocate_strategy":
                    key = cmd.get("strategy", "")
                    alloc = self.strategies.get_allocation(key)
                    if alloc:
                        pnl = alloc.get("pnl", 0)
                        trades = alloc.get("trades", 0)
                        # Cash-out: converte USDC restante de volta para SOL
                        await self._cashout_usdc_to_sol(key, alloc)
                        self.strategies.deallocate_strategy(key)
                        logger.info(
                            f"Desalocacao: {key} | {trades} trades | PNL: ${pnl:+.4f}"
                        )
                        await self.send_message(
                            f"🛑 *MODO REAL ENCERRADO* - {key}\n"
                            f"━━━━━━━━━━━━━━━━━━━━\n"
                            f"📊 Trades: {trades}\n"
                            f"{'🟢' if pnl >= 0 else '🔴'} P&L Final: ${pnl:+.4f}\n"
                            f"💰 USDC convertido de volta para SOL\n"
                            f"━━━━━━━━━━━━━━━━━━━━"
                        )
                elif action == "save_settings":
                    self._apply_settings(cmd)
                    self._settings_applied = True
        except Exception as e:
            logger.debug(f"Cloud push prep error: {e}")

    # --------------------------------------------------------
    # CASH-OUT: converte USDC de volta para SOL ao parar modo real
    # --------------------------------------------------------
    async def _cashout_usdc_to_sol(self, key: str, alloc: dict):
        """Converte USDC restante de volta para SOL na carteira."""
        if config.PAPER_TRADING:
            return
        try:
            # Atualiza saldo USDC
            if self.wallet:
                await self.wallet.update_balances()
                usdc_bal = self.wallet.last_usdc_balance
            else:
                usdc_bal = 0

            if usdc_bal < 0.001:
                logger.info(f"[CASH-OUT] {key}: sem USDC para converter (${usdc_bal:.4f})")
                return

            usdc_mint = config.TOKENS["USDC"]
            sol_mint = config.TOKENS["SOL"]
            usdc_lamports = int(usdc_bal * (10 ** 6))

            logger.info(f"[CASH-OUT] {key}: convertendo ${usdc_bal:.4f} USDC -> SOL")
            quote = await self.executor.get_quote(usdc_mint, sol_mint, usdc_lamports)
            if not quote:
                logger.warning(f"[CASH-OUT] {key}: sem quote USDC->SOL")
                return

            tx = await self.executor.execute_swap(quote)
            if tx:
                sol_received = int(quote.get("outAmount", 0)) / (10 ** 9)
                logger.info(
                    f"[CASH-OUT] {key}: ${usdc_bal:.4f} USDC -> {sol_received:.6f} SOL | TX: {tx}"
                )
            else:
                logger.warning(f"[CASH-OUT] {key}: falha no swap USDC->SOL")
        except Exception as e:
            logger.error(f"[CASH-OUT] {key}: erro: {e}")

    # --------------------------------------------------------
    # CONFIGURACOES VIA DASHBOARD
    # --------------------------------------------------------
    def _apply_settings(self, cmd: dict):
        """Aplica configuracoes recebidas do dashboard (private key, paper mode)."""
        import re
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.py")
        changed = []

        pk = cmd.get("private_key")
        if pk and isinstance(pk, str) and len(pk) > 10:
            config.SOLANA_PRIVATE_KEY = pk
            changed.append("SOLANA_PRIVATE_KEY")

        paper = cmd.get("paper_trading")
        if paper is not None:
            config.PAPER_TRADING = bool(paper)
            changed.append("PAPER_TRADING")

        if not changed:
            return

        # Persiste no config.py em disco
        try:
            with open(config_path, "r") as f:
                content = f.read()

            if "SOLANA_PRIVATE_KEY" in changed:
                content = re.sub(
                    r'SOLANA_PRIVATE_KEY\s*=\s*"[^"]*"',
                    f'SOLANA_PRIVATE_KEY = "{config.SOLANA_PRIVATE_KEY}"',
                    content
                )
            if "PAPER_TRADING" in changed:
                content = re.sub(
                    r'PAPER_TRADING\s*=\s*(True|False)',
                    f'PAPER_TRADING = {config.PAPER_TRADING}',
                    content
                )

            with open(config_path, "w") as f:
                f.write(content)

            mask = config.SOLANA_PRIVATE_KEY[:4] + "..." + config.SOLANA_PRIVATE_KEY[-4:] if len(config.SOLANA_PRIVATE_KEY) > 8 else "(vazia)"
            logger.info(
                f"[SETTINGS] Configuracoes atualizadas: {', '.join(changed)} | "
                f"PK={mask} | PAPER={config.PAPER_TRADING}"
            )
        except Exception as e:
            logger.error(f"[SETTINGS] Erro ao salvar config.py: {e}")

    # --------------------------------------------------------
    # AUTO-RETIRADA DE LUCRO
    # --------------------------------------------------------
    async def _check_profit_withdraw(self, current_price: float):
        """
        Verifica se o lucro total atingiu R$260.
        Se sim, transfere R$150 em SOL para carteira spot.
        """
        if not config.SOLANA_PRIVATE_KEY or config.PAPER_TRADING:
            return  # Precisa de private key e modo real

        spot_wallet = getattr(config, "SOLANA_SPOT_WALLET", "")
        if not spot_wallet:
            return

        threshold_brl = getattr(config, "PROFIT_WITHDRAW_THRESHOLD_BRL", 260.0)
        withdraw_brl = getattr(config, "PROFIT_WITHDRAW_AMOUNT_BRL", 150.0)
        usd_brl = getattr(config, "USD_TO_BRL", 5.80)

        # Calcula PNL total de todas as alocacoes
        total_pnl_usd = 0
        for key, alloc in self.strategies.allocations.items():
            total_pnl_usd += alloc.get("pnl", 0)

        total_pnl_brl = total_pnl_usd * usd_brl

        if total_pnl_brl < threshold_brl:
            return

        # Verifica se ja fez retirada recente (cooldown 1h)
        last_withdraw = getattr(self, "_last_profit_withdraw", 0)
        import time as _time
        if _time.time() - last_withdraw < 3600:
            return

        # Calcula quanto SOL transferir
        withdraw_usd = withdraw_brl / usd_brl
        if current_price <= 0:
            return
        sol_amount = withdraw_usd / current_price
        lamports = int(sol_amount * 1_000_000_000)

        logger.info(
            f"[AUTO-WITHDRAW] Lucro R${total_pnl_brl:.2f} >= R${threshold_brl:.2f}. "
            f"Transferindo R${withdraw_brl:.2f} (~{sol_amount:.4f} SOL) para {spot_wallet[:8]}..."
        )

        try:
            from solders.keypair import Keypair
            from solders.pubkey import Pubkey
            from solders.system_program import transfer, TransferParams
            from solders.transaction import Transaction
            from solders.message import Message
            from solana.rpc.async_api import AsyncClient as SolanaClient

            keypair = Keypair.from_base58_string(config.SOLANA_PRIVATE_KEY)
            destination = Pubkey.from_string(spot_wallet)

            client = SolanaClient(config.SOLANA_RPC_URL)
            blockhash_resp = await client.get_latest_blockhash()
            blockhash = blockhash_resp.value.blockhash

            ix = transfer(TransferParams(
                from_pubkey=keypair.pubkey(),
                to_pubkey=destination,
                lamports=lamports,
            ))
            msg = Message.new_with_blockhash([ix], keypair.pubkey(), blockhash)
            tx = Transaction.new_unsigned(msg)
            tx.sign([keypair], blockhash)

            result = await client.send_transaction(tx)
            await client.close()

            tx_hash = str(result.value)
            self._last_profit_withdraw = _time.time()

            logger.info(f"[AUTO-WITHDRAW] TX: {tx_hash}")
            await self.send_message(
                f"💸 *AUTO-RETIRADA DE LUCRO*\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"📈 Lucro total: R${total_pnl_brl:.2f}\n"
                f"💰 Transferido: R${withdraw_brl:.2f} (~{sol_amount:.4f} SOL)\n"
                f"📬 Para: `{spot_wallet[:8]}...{spot_wallet[-4:]}`\n"
                f"🔗 TX: `{tx_hash}`\n"
                f"━━━━━━━━━━━━━━━━━━━━"
            )

        except ImportError:
            logger.error("[AUTO-WITHDRAW] solders/solana nao instalado")
        except Exception as e:
            logger.error(f"[AUTO-WITHDRAW] Erro na transferencia: {e}")

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
