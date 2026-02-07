"""
Dashboard Web - Trading Bot (Pro Edition)
==========================================
Dashboard profissional com WebSocket, graficos em tempo real,
glassmorphism, glow effects e animacoes modernas.
"""

import asyncio
import json
import logging
import weakref
from datetime import datetime
from aiohttp import web
import aiohttp
import config

logger = logging.getLogger("Dashboard")

# ============================================================
# HTML PROFISSIONAL DO DASHBOARD
# ============================================================
DASHBOARD_HTML = r"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SOL/USDC Trading Bot</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-primary: #0a0a0f;
            --bg-secondary: #111118;
            --bg-card: #161622;
            --bg-card-hover: #1a1a28;
            --border-color: rgba(255,255,255,0.06);
            --border-glow: rgba(0,255,136,0.15);
            --green: #00ff88;
            --green-dim: #00cc6a;
            --green-dark: rgba(0,255,136,0.1);
            --green-glow: rgba(0,255,136,0.4);
            --red: #ff4466;
            --red-dim: #cc3355;
            --red-dark: rgba(255,68,102,0.1);
            --red-glow: rgba(255,68,102,0.4);
            --blue: #4488ff;
            --blue-dim: #3366cc;
            --blue-dark: rgba(68,136,255,0.1);
            --yellow: #ffaa00;
            --yellow-dark: rgba(255,170,0,0.1);
            --purple: #aa66ff;
            --purple-dark: rgba(170,102,255,0.1);
            --text-primary: #ffffff;
            --text-secondary: #8888aa;
            --text-muted: #555566;
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: 'Inter', -apple-system, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            overflow-x: hidden;
        }

        /* Animated background */
        body::before {
            content: '';
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background:
                radial-gradient(ellipse at 20% 50%, rgba(0,255,136,0.03) 0%, transparent 50%),
                radial-gradient(ellipse at 80% 20%, rgba(68,136,255,0.03) 0%, transparent 50%),
                radial-gradient(ellipse at 50% 80%, rgba(170,102,255,0.02) 0%, transparent 50%);
            pointer-events: none;
            z-index: 0;
        }

        .app { position: relative; z-index: 1; }

        /* ===== HEADER ===== */
        .header {
            padding: 20px 30px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid var(--border-color);
            backdrop-filter: blur(20px);
            background: rgba(10,10,15,0.8);
            position: sticky;
            top: 0;
            z-index: 100;
        }
        .header-left { display: flex; align-items: center; gap: 16px; }
        .logo {
            width: 40px; height: 40px;
            background: linear-gradient(135deg, var(--green), var(--blue));
            border-radius: 12px;
            display: flex; align-items: center; justify-content: center;
            font-weight: 900; font-size: 18px;
            box-shadow: 0 0 20px var(--green-glow);
        }
        .header-title {
            font-size: 1.3em;
            font-weight: 700;
            letter-spacing: -0.5px;
        }
        .header-title span { color: var(--text-muted); font-weight: 400; }
        .header-right { display: flex; align-items: center; gap: 20px; }
        .connection-status {
            display: flex; align-items: center; gap: 8px;
            font-size: 0.8em; color: var(--text-secondary);
        }
        .status-dot {
            width: 8px; height: 8px; border-radius: 50%;
            background: var(--green);
            box-shadow: 0 0 8px var(--green-glow);
            animation: pulse-dot 2s infinite;
        }
        .status-dot.offline { background: var(--red); box-shadow: 0 0 8px var(--red-glow); animation: none; }
        @keyframes pulse-dot {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.5; transform: scale(0.8); }
        }
        .mode-badge {
            padding: 6px 14px;
            border-radius: 8px;
            font-size: 0.75em;
            font-weight: 600;
            letter-spacing: 1px;
            text-transform: uppercase;
        }
        .mode-paper { background: var(--yellow-dark); color: var(--yellow); border: 1px solid rgba(255,170,0,0.2); }
        .mode-live { background: var(--red-dark); color: var(--red); border: 1px solid rgba(255,68,102,0.2); }

        /* ===== MAIN GRID ===== */
        .main {
            max-width: 1440px;
            margin: 0 auto;
            padding: 24px;
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            grid-template-rows: auto auto auto;
            gap: 16px;
        }

        /* ===== CARDS ===== */
        .card {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 24px;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }
        .card::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 1px;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent);
        }
        .card:hover {
            background: var(--bg-card-hover);
            border-color: var(--border-glow);
            transform: translateY(-2px);
            box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        }
        .card-label {
            font-size: 0.7em;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            color: var(--text-muted);
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .card-label svg { width: 14px; height: 14px; opacity: 0.5; }

        /* ===== PRICE CARD ===== */
        .price-card { grid-column: 1 / 2; }
        .price-main {
            font-size: 3em;
            font-weight: 800;
            letter-spacing: -2px;
            line-height: 1;
            margin-bottom: 8px;
            font-family: 'JetBrains Mono', monospace;
        }
        .price-main.glow-green {
            color: var(--green);
            text-shadow: 0 0 30px var(--green-glow);
        }
        .price-main.glow-red {
            color: var(--red);
            text-shadow: 0 0 30px var(--red-glow);
        }
        .price-change {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 0.85em;
            font-weight: 600;
            font-family: 'JetBrains Mono', monospace;
        }
        .price-change.up { background: var(--green-dark); color: var(--green); }
        .price-change.down { background: var(--red-dark); color: var(--red); }
        .price-pair {
            margin-top: 12px;
            font-size: 0.85em;
            color: var(--text-secondary);
        }

        /* ===== PNL CARD ===== */
        .pnl-card { grid-column: 2 / 3; }
        .pnl-value {
            font-size: 2.4em;
            font-weight: 800;
            font-family: 'JetBrains Mono', monospace;
            letter-spacing: -1px;
        }
        .pnl-value.profit { color: var(--green); text-shadow: 0 0 20px var(--green-glow); }
        .pnl-value.loss { color: var(--red); text-shadow: 0 0 20px var(--red-glow); }
        .pnl-sub {
            display: flex; gap: 20px; margin-top: 16px;
        }
        .pnl-sub-item {
            display: flex; flex-direction: column; gap: 4px;
        }
        .pnl-sub-label { font-size: 0.7em; color: var(--text-muted); text-transform: uppercase; letter-spacing: 1px; }
        .pnl-sub-value { font-size: 1.1em; font-weight: 600; font-family: 'JetBrains Mono', monospace; }

        /* ===== STATUS CARD ===== */
        .status-card { grid-column: 3 / 4; }
        .status-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 16px;
        }
        .status-item {
            background: rgba(255,255,255,0.02);
            border-radius: 10px;
            padding: 14px;
            text-align: center;
        }
        .status-item-value {
            font-size: 1.6em;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
            margin-bottom: 4px;
        }
        .status-item-label {
            font-size: 0.7em;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        /* ===== CHART CARD ===== */
        .chart-card {
            grid-column: 1 / 3;
            min-height: 320px;
        }
        .chart-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
        }
        .chart-tabs {
            display: flex; gap: 4px;
        }
        .chart-tab {
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 0.75em;
            font-weight: 500;
            cursor: pointer;
            background: transparent;
            color: var(--text-muted);
            border: none;
            transition: all 0.2s;
        }
        .chart-tab:hover { color: var(--text-secondary); background: rgba(255,255,255,0.05); }
        .chart-tab.active { background: rgba(0,255,136,0.1); color: var(--green); }
        .chart-container {
            width: 100%;
            height: 260px;
            position: relative;
        }
        canvas#priceChart { width: 100% !important; height: 100% !important; }

        /* ===== INDICATORS CARD ===== */
        .indicators-card { grid-column: 3 / 4; }
        .indicator-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 0;
            border-bottom: 1px solid var(--border-color);
        }
        .indicator-row:last-child { border-bottom: none; }
        .indicator-name {
            font-size: 0.85em;
            font-weight: 500;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .indicator-dot {
            width: 6px; height: 6px;
            border-radius: 50%;
        }
        .indicator-dot.bullish { background: var(--green); box-shadow: 0 0 6px var(--green-glow); }
        .indicator-dot.bearish { background: var(--red); box-shadow: 0 0 6px var(--red-glow); }
        .indicator-dot.neutral { background: var(--text-muted); }
        .indicator-value {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.85em;
            font-weight: 600;
        }
        .indicator-bar {
            width: 100%;
            height: 4px;
            background: rgba(255,255,255,0.05);
            border-radius: 2px;
            margin-top: 6px;
            overflow: hidden;
        }
        .indicator-bar-fill {
            height: 100%;
            border-radius: 2px;
            transition: width 0.8s ease, background 0.5s ease;
        }
        .indicator-bar-fill.bullish { background: linear-gradient(90deg, var(--green-dim), var(--green)); }
        .indicator-bar-fill.bearish { background: linear-gradient(90deg, var(--red), var(--red-dim)); }
        .indicator-bar-fill.neutral { background: var(--text-muted); }

        /* ===== SIGNALS CARD ===== */
        .signals-card {
            grid-column: 1 / 2;
        }
        .signal-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 10px 18px;
            border-radius: 10px;
            font-size: 0.9em;
            font-weight: 700;
            letter-spacing: 0.5px;
            width: 100%;
            justify-content: center;
            margin-bottom: 12px;
        }
        .signal-long {
            background: linear-gradient(135deg, rgba(0,255,136,0.15), rgba(0,255,136,0.05));
            color: var(--green);
            border: 1px solid rgba(0,255,136,0.2);
            box-shadow: 0 0 20px rgba(0,255,136,0.1);
        }
        .signal-short {
            background: linear-gradient(135deg, rgba(255,68,102,0.15), rgba(255,68,102,0.05));
            color: var(--red);
            border: 1px solid rgba(255,68,102,0.2);
            box-shadow: 0 0 20px rgba(255,68,102,0.1);
        }
        .signal-none {
            background: rgba(255,255,255,0.03);
            color: var(--text-muted);
            border: 1px solid var(--border-color);
        }
        .signal-confidence {
            margin-top: 8px;
            display: flex; align-items: center; gap: 10px;
        }
        .confidence-bar {
            flex: 1; height: 6px;
            background: rgba(255,255,255,0.05);
            border-radius: 3px; overflow: hidden;
        }
        .confidence-fill {
            height: 100%; border-radius: 3px;
            background: linear-gradient(90deg, var(--blue), var(--green));
            transition: width 1s ease;
        }
        .confidence-text {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.85em;
            font-weight: 600;
            min-width: 40px;
            text-align: right;
        }

        /* ===== POSITIONS CARD ===== */
        .positions-card { grid-column: 2 / 4; }
        .position-item {
            display: grid;
            grid-template-columns: 80px 1fr 1fr 1fr 80px;
            align-items: center;
            gap: 16px;
            padding: 14px 16px;
            background: rgba(255,255,255,0.02);
            border-radius: 10px;
            margin-bottom: 8px;
            border: 1px solid var(--border-color);
            transition: all 0.2s;
        }
        .position-item:hover { background: rgba(255,255,255,0.04); }
        .position-direction {
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 0.75em;
            font-weight: 700;
            text-align: center;
            text-transform: uppercase;
        }
        .position-long { background: var(--green-dark); color: var(--green); }
        .position-short { background: var(--red-dark); color: var(--red); }
        .position-field-label { font-size: 0.65em; color: var(--text-muted); text-transform: uppercase; letter-spacing: 1px; }
        .position-field-value { font-family: 'JetBrains Mono', monospace; font-size: 0.9em; font-weight: 600; margin-top: 2px; }
        .no-positions {
            text-align: center; padding: 30px;
            color: var(--text-muted); font-size: 0.9em;
        }

        /* ===== LOG CARD ===== */
        .log-card { grid-column: 1 / 4; }
        .log-container {
            background: rgba(0,0,0,0.3);
            border: 1px solid var(--border-color);
            border-radius: 10px;
            padding: 16px;
            max-height: 240px;
            overflow-y: auto;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.78em;
            line-height: 1.8;
        }
        .log-container::-webkit-scrollbar { width: 6px; }
        .log-container::-webkit-scrollbar-track { background: transparent; }
        .log-container::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 3px; }
        .log-line {
            padding: 2px 0;
            display: flex;
            gap: 8px;
            opacity: 0;
            animation: fadeIn 0.3s ease forwards;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(4px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .log-time { color: var(--text-muted); min-width: 60px; }
        .log-msg { flex: 1; }
        .log-info { color: var(--blue); }
        .log-success { color: var(--green); }
        .log-error { color: var(--red); }
        .log-warn { color: var(--yellow); }

        /* ===== FOOTER ===== */
        .footer {
            text-align: center;
            padding: 20px;
            color: var(--text-muted);
            font-size: 0.75em;
            border-top: 1px solid var(--border-color);
            margin-top: 16px;
        }

        /* ===== RESPONSIVE ===== */
        @media (max-width: 1024px) {
            .main {
                grid-template-columns: 1fr 1fr;
            }
            .chart-card { grid-column: 1 / 3; }
            .indicators-card { grid-column: 1 / 2; }
            .signals-card { grid-column: 2 / 3; }
            .positions-card { grid-column: 1 / 3; }
            .log-card { grid-column: 1 / 3; }
            .price-card, .pnl-card, .status-card { grid-column: auto; }
        }
        @media (max-width: 768px) {
            .main {
                grid-template-columns: 1fr;
                padding: 12px;
            }
            .chart-card, .indicators-card, .signals-card,
            .positions-card, .log-card,
            .price-card, .pnl-card, .status-card { grid-column: 1 / 2; }
            .price-main { font-size: 2.2em; }
            .header { padding: 14px 16px; }
            .header-title { font-size: 1em; }
            .position-item { grid-template-columns: 1fr 1fr; }
        }

        /* ===== SKELETON ===== */
        .skeleton {
            background: linear-gradient(90deg, var(--bg-card) 25%, rgba(255,255,255,0.05) 50%, var(--bg-card) 75%);
            background-size: 200% 100%;
            animation: shimmer 1.5s infinite;
            border-radius: 6px;
        }
        @keyframes shimmer {
            0% { background-position: 200% 0; }
            100% { background-position: -200% 0; }
        }

        /* Number transition */
        .num-transition { transition: all 0.5s ease; }
    </style>
</head>
<body>
<div class="app">
    <!-- HEADER -->
    <header class="header">
        <div class="header-left">
            <div class="logo">S</div>
            <div>
                <div class="header-title">SOL/USDC <span>Trading Bot</span></div>
            </div>
        </div>
        <div class="header-right">
            <div class="connection-status">
                <div class="status-dot" id="ws-dot"></div>
                <span id="ws-status">Conectando...</span>
            </div>
            <span class="mode-badge mode-paper" id="mode-badge">PAPER</span>
        </div>
    </header>

    <!-- MAIN GRID -->
    <main class="main">
        <!-- Row 1: Price, PnL, Status -->
        <div class="card price-card">
            <div class="card-label">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"/></svg>
                Preco Atual
            </div>
            <div class="price-main glow-green" id="price">$---.--</div>
            <span class="price-change up" id="price-change">-- %</span>
            <div class="price-pair">SOL / USDC &middot; <span id="last-update-time">--:--:--</span></div>
        </div>

        <div class="card pnl-card">
            <div class="card-label">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></svg>
                P&amp;L Total
            </div>
            <div class="pnl-value profit" id="total-pnl">$0.00</div>
            <div class="pnl-sub">
                <div class="pnl-sub-item">
                    <span class="pnl-sub-label">Aberto</span>
                    <span class="pnl-sub-value" id="open-pnl">$0.00</span>
                </div>
                <div class="pnl-sub-item">
                    <span class="pnl-sub-label">Win Rate</span>
                    <span class="pnl-sub-value" id="win-rate">N/A</span>
                </div>
                <div class="pnl-sub-item">
                    <span class="pnl-sub-label">Trades</span>
                    <span class="pnl-sub-value" id="total-trades">0</span>
                </div>
            </div>
        </div>

        <div class="card status-card">
            <div class="card-label">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/></svg>
                Status do Bot
            </div>
            <div class="status-grid">
                <div class="status-item">
                    <div class="status-item-value" id="analysis-count" style="color:var(--blue)">0</div>
                    <div class="status-item-label">Analises</div>
                </div>
                <div class="status-item">
                    <div class="status-item-value" id="open-positions" style="color:var(--purple)">0</div>
                    <div class="status-item-label">Posicoes</div>
                </div>
                <div class="status-item">
                    <div class="status-item-value" id="trade-mode" style="color:var(--yellow);font-size:0.9em">Day</div>
                    <div class="status-item-label">Modo</div>
                </div>
                <div class="status-item">
                    <div class="status-item-value" id="loop-timer" style="color:var(--text-secondary)">45s</div>
                    <div class="status-item-label">Intervalo</div>
                </div>
            </div>
        </div>

        <!-- Row 2: Chart + Indicators -->
        <div class="card chart-card">
            <div class="chart-header">
                <div class="card-label" style="margin-bottom:0">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
                    Historico de Precos
                </div>
                <div class="chart-tabs">
                    <button class="chart-tab active" onclick="setChartRange(20)">20</button>
                    <button class="chart-tab" onclick="setChartRange(50)">50</button>
                    <button class="chart-tab" onclick="setChartRange(100)">100</button>
                    <button class="chart-tab" onclick="setChartRange(0)">All</button>
                </div>
            </div>
            <div class="chart-container">
                <canvas id="priceChart"></canvas>
            </div>
        </div>

        <div class="card indicators-card">
            <div class="card-label">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20V10M18 20V4M6 20v-4"/></svg>
                Indicadores
            </div>
            <div id="indicators-list">
                <div class="indicator-row" id="ind-rsi">
                    <div>
                        <div class="indicator-name"><span class="indicator-dot neutral"></span> RSI</div>
                        <div class="indicator-bar"><div class="indicator-bar-fill neutral" style="width:50%"></div></div>
                    </div>
                    <div class="indicator-value">--</div>
                </div>
                <div class="indicator-row" id="ind-ema">
                    <div>
                        <div class="indicator-name"><span class="indicator-dot neutral"></span> EMA</div>
                        <div class="indicator-bar"><div class="indicator-bar-fill neutral" style="width:50%"></div></div>
                    </div>
                    <div class="indicator-value">--</div>
                </div>
                <div class="indicator-row" id="ind-ichimoku">
                    <div>
                        <div class="indicator-name"><span class="indicator-dot neutral"></span> Ichimoku</div>
                        <div class="indicator-bar"><div class="indicator-bar-fill neutral" style="width:50%"></div></div>
                    </div>
                    <div class="indicator-value">--</div>
                </div>
                <div class="indicator-row" id="ind-volume">
                    <div>
                        <div class="indicator-name"><span class="indicator-dot neutral"></span> Volume</div>
                        <div class="indicator-bar"><div class="indicator-bar-fill neutral" style="width:50%"></div></div>
                    </div>
                    <div class="indicator-value">--</div>
                </div>
            </div>
        </div>

        <!-- Row 3: Signal + Positions -->
        <div class="card signals-card">
            <div class="card-label">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
                Ultimo Sinal
            </div>
            <div class="signal-badge signal-none" id="signal-badge">
                <span>AGUARDANDO SINAL</span>
            </div>
            <div class="signal-confidence">
                <span style="font-size:0.75em;color:var(--text-muted)">Confianca</span>
                <div class="confidence-bar">
                    <div class="confidence-fill" id="confidence-fill" style="width:0%"></div>
                </div>
                <span class="confidence-text" id="confidence-text">0%</span>
            </div>
        </div>

        <div class="card positions-card">
            <div class="card-label">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 21V5a2 2 0 00-2-2h-4a2 2 0 00-2 2v16"/></svg>
                Posicoes Abertas
            </div>
            <div id="positions-container">
                <div class="no-positions">Nenhuma posicao aberta</div>
            </div>
        </div>

        <!-- Row 4: Log -->
        <div class="card log-card">
            <div class="card-label">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>
                Terminal
            </div>
            <div class="log-container" id="log-container">
                <div class="log-line"><span class="log-time">--:--</span><span class="log-msg" style="color:var(--text-muted)">Conectando ao bot...</span></div>
            </div>
        </div>
    </main>

    <footer class="footer">
        SOL/USDC Trading Bot &middot; Paper Trading Mode &middot; Powered by Jupiter DEX + GeckoTerminal
    </footer>
</div>

<script>
// ============================================================
// STATE
// ============================================================
let priceHistory = [];
let chartRange = 50;
let ws = null;
let wsReconnectTimer = null;
let lastPrice = 0;
let prevPrice = 0;

// ============================================================
// WEBSOCKET
// ============================================================
function connectWS() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(protocol + '//' + location.host + '/ws');

    ws.onopen = () => {
        document.getElementById('ws-dot').className = 'status-dot';
        document.getElementById('ws-status').textContent = 'Conectado';
        if (wsReconnectTimer) { clearTimeout(wsReconnectTimer); wsReconnectTimer = null; }
    };

    ws.onclose = () => {
        document.getElementById('ws-dot').className = 'status-dot offline';
        document.getElementById('ws-status').textContent = 'Reconectando...';
        wsReconnectTimer = setTimeout(connectWS, 3000);
    };

    ws.onerror = () => { ws.close(); };

    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            updateDashboard(data);
        } catch(e) { console.error('WS parse error:', e); }
    };
}

// ============================================================
// FALLBACK POLLING (se WS falhar)
// ============================================================
async function pollData() {
    try {
        const r = await fetch('/api/status');
        const data = await r.json();
        updateDashboard(data);
    } catch(e) {}
}

// ============================================================
// UPDATE DASHBOARD
// ============================================================
function updateDashboard(data) {
    if (data.error) return;

    // Price
    const price = data.price || 0;
    prevPrice = lastPrice;
    lastPrice = price;
    const priceEl = document.getElementById('price');
    priceEl.textContent = '$' + price.toFixed(2);

    if (prevPrice > 0) {
        priceEl.className = 'price-main ' + (price >= prevPrice ? 'glow-green' : 'glow-red');
        const changePct = ((price - prevPrice) / prevPrice * 100);
        const changeEl = document.getElementById('price-change');
        changeEl.textContent = (changePct >= 0 ? '+' : '') + changePct.toFixed(3) + '%';
        changeEl.className = 'price-change ' + (changePct >= 0 ? 'up' : 'down');
    }

    // Price history for chart
    if (price > 0) {
        priceHistory.push({ time: new Date(), price: price });
        if (priceHistory.length > 500) priceHistory = priceHistory.slice(-500);
        drawChart();
    }

    // Time
    document.getElementById('last-update-time').textContent = data.last_update || '--:--:--';

    // PnL
    const totalPnl = data.total_pnl || 0;
    const totalPnlEl = document.getElementById('total-pnl');
    totalPnlEl.textContent = (totalPnl >= 0 ? '+' : '') + '$' + totalPnl.toFixed(2);
    totalPnlEl.className = 'pnl-value ' + (totalPnl >= 0 ? 'profit' : 'loss');

    const openPnl = data.open_pnl || 0;
    const openPnlEl = document.getElementById('open-pnl');
    openPnlEl.textContent = (openPnl >= 0 ? '+' : '') + '$' + openPnl.toFixed(2);
    openPnlEl.style.color = openPnl >= 0 ? 'var(--green)' : 'var(--red)';

    document.getElementById('win-rate').textContent = data.win_rate || 'N/A';
    document.getElementById('total-trades').textContent = data.total_trades || '0';

    // Status
    document.getElementById('analysis-count').textContent = data.analysis_count || '0';
    document.getElementById('open-positions').textContent = data.open_positions || '0';
    document.getElementById('trade-mode').textContent = (data.mode || 'Day Trade').replace(' Trade', '');

    // Mode badge
    const modeBadge = document.getElementById('mode-badge');
    if (data.paper_trading) {
        modeBadge.textContent = 'PAPER';
        modeBadge.className = 'mode-badge mode-paper';
    } else {
        modeBadge.textContent = 'LIVE';
        modeBadge.className = 'mode-badge mode-live';
    }

    // Indicators
    if (data.indicators) {
        updateIndicator('rsi', 'RSI', data.indicators.RSI, 0, 100, v => {
            if (v < 30) return 'bullish';
            if (v > 70) return 'bearish';
            return 'neutral';
        }, v => v.toFixed(1));

        updateIndicator('ema', 'EMA', data.indicators.EMA, -1, 1, v => {
            if (v > 0.2) return 'bullish';
            if (v < -0.2) return 'bearish';
            return 'neutral';
        }, v => v.toFixed(2));

        updateIndicator('ichimoku', 'Ichimoku', data.indicators.Ichimoku, -1, 1, v => {
            if (v > 0.2) return 'bullish';
            if (v < -0.2) return 'bearish';
            return 'neutral';
        }, v => v.toFixed(2));

        updateIndicator('volume', 'Volume', data.indicators.Volume, 0, 3, v => {
            if (v > 1.5) return 'bullish';
            if (v < 0.5) return 'bearish';
            return 'neutral';
        }, v => v.toFixed(2) + 'x');
    }

    // Signal
    if (data.last_signal) {
        const sig = data.last_signal;
        const sigBadge = document.getElementById('signal-badge');
        if (sig.direction === 'long') {
            sigBadge.className = 'signal-badge signal-long';
            sigBadge.innerHTML = '<span>&#9650; LONG (COMPRA)</span>';
        } else if (sig.direction === 'short') {
            sigBadge.className = 'signal-badge signal-short';
            sigBadge.innerHTML = '<span>&#9660; SHORT (VENDA)</span>';
        }
        const conf = (sig.confidence || 0) * 100;
        document.getElementById('confidence-fill').style.width = conf + '%';
        document.getElementById('confidence-text').textContent = conf.toFixed(0) + '%';
    }

    // Positions
    if (data.positions && data.positions.length > 0) {
        let html = '';
        for (const p of data.positions) {
            const dirCls = p.direction === 'long' ? 'position-long' : 'position-short';
            const pnlColor = p.pnl_pct >= 0 ? 'var(--green)' : 'var(--red)';
            html += `
                <div class="position-item">
                    <span class="position-direction ${dirCls}">${p.direction.toUpperCase()}</span>
                    <div><div class="position-field-label">Entrada</div><div class="position-field-value">$${p.entry_price.toFixed(2)}</div></div>
                    <div><div class="position-field-label">P&L</div><div class="position-field-value" style="color:${pnlColor}">${p.pnl_pct >= 0 ? '+' : ''}${p.pnl_pct.toFixed(2)}%</div></div>
                    <div><div class="position-field-label">SL / TP</div><div class="position-field-value">$${p.stop_loss.toFixed(2)} / $${p.take_profits[0].toFixed(2)}</div></div>
                    <div><div class="position-field-label">USD</div><div class="position-field-value" style="color:${pnlColor}">${p.pnl_usd >= 0 ? '+' : ''}$${p.pnl_usd.toFixed(2)}</div></div>
                </div>`;
        }
        document.getElementById('positions-container').innerHTML = html;
    } else {
        document.getElementById('positions-container').innerHTML = '<div class="no-positions">Nenhuma posicao aberta</div>';
    }

    // Logs
    if (data.logs && data.logs.length > 0) {
        let logHtml = '';
        for (const log of data.logs.slice(-30)) {
            let cls = '';
            if (log.includes('ERRO') || log.includes('ERROR')) cls = 'log-error';
            else if (log.includes('WARN') || log.includes('WARNING')) cls = 'log-warn';
            else if (log.includes('Sinal') || log.includes('Executado') || log.includes('BUY') || log.includes('SELL')) cls = 'log-success';
            else cls = 'log-info';

            const parts = log.split(' ');
            const time = parts[0] || '';
            const msg = parts.slice(1).join(' ');
            logHtml += `<div class="log-line"><span class="log-time">${time}</span><span class="log-msg ${cls}">${msg}</span></div>`;
        }
        const container = document.getElementById('log-container');
        container.innerHTML = logHtml;
        container.scrollTop = container.scrollHeight;
    }
}

// ============================================================
// INDICATOR UPDATE
// ============================================================
function updateIndicator(id, name, value, min, max, getState, format) {
    if (value === undefined || value === null) return;
    const row = document.getElementById('ind-' + id);
    if (!row) return;

    const state = getState(value);
    const pct = Math.max(0, Math.min(100, ((value - min) / (max - min)) * 100));

    const dot = row.querySelector('.indicator-dot');
    dot.className = 'indicator-dot ' + state;

    const bar = row.querySelector('.indicator-bar-fill');
    bar.style.width = pct + '%';
    bar.className = 'indicator-bar-fill ' + state;

    const val = row.querySelector('.indicator-value');
    val.textContent = format(value);
    val.style.color = state === 'bullish' ? 'var(--green)' : state === 'bearish' ? 'var(--red)' : 'var(--text-secondary)';
}

// ============================================================
// CHART (Canvas)
// ============================================================
function drawChart() {
    const canvas = document.getElementById('priceChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const rect = canvas.parentElement.getBoundingClientRect();
    canvas.width = rect.width * 2;
    canvas.height = rect.height * 2;
    ctx.scale(2, 2);
    const W = rect.width;
    const H = rect.height;

    let data = priceHistory;
    if (chartRange > 0) data = data.slice(-chartRange);
    if (data.length < 2) {
        ctx.clearRect(0, 0, W, H);
        ctx.fillStyle = '#555566';
        ctx.font = '13px Inter';
        ctx.textAlign = 'center';
        ctx.fillText('Aguardando dados de preco...', W/2, H/2);
        return;
    }

    const prices = data.map(d => d.price);
    const minP = Math.min(...prices) * 0.9998;
    const maxP = Math.max(...prices) * 1.0002;
    const range = maxP - minP || 1;
    const padTop = 30;
    const padBottom = 30;
    const padLeft = 60;
    const padRight = 20;
    const chartW = W - padLeft - padRight;
    const chartH = H - padTop - padBottom;

    ctx.clearRect(0, 0, W, H);

    // Grid lines
    ctx.strokeStyle = 'rgba(255,255,255,0.04)';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
        const y = padTop + (chartH / 4) * i;
        ctx.beginPath();
        ctx.moveTo(padLeft, y);
        ctx.lineTo(W - padRight, y);
        ctx.stroke();

        const price = maxP - (range / 4) * i;
        ctx.fillStyle = '#555566';
        ctx.font = '10px JetBrains Mono';
        ctx.textAlign = 'right';
        ctx.fillText('$' + price.toFixed(2), padLeft - 8, y + 3);
    }

    // Price line
    const isUp = prices[prices.length - 1] >= prices[0];
    const lineColor = isUp ? '#00ff88' : '#ff4466';
    const glowColor = isUp ? 'rgba(0,255,136,0.3)' : 'rgba(255,68,102,0.3)';

    // Glow
    ctx.strokeStyle = glowColor;
    ctx.lineWidth = 6;
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';
    ctx.beginPath();
    for (let i = 0; i < prices.length; i++) {
        const x = padLeft + (i / (prices.length - 1)) * chartW;
        const y = padTop + ((maxP - prices[i]) / range) * chartH;
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // Main line
    ctx.strokeStyle = lineColor;
    ctx.lineWidth = 2;
    ctx.beginPath();
    for (let i = 0; i < prices.length; i++) {
        const x = padLeft + (i / (prices.length - 1)) * chartW;
        const y = padTop + ((maxP - prices[i]) / range) * chartH;
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // Gradient fill
    const grad = ctx.createLinearGradient(0, padTop, 0, H - padBottom);
    if (isUp) {
        grad.addColorStop(0, 'rgba(0,255,136,0.15)');
        grad.addColorStop(1, 'rgba(0,255,136,0)');
    } else {
        grad.addColorStop(0, 'rgba(255,68,102,0.15)');
        grad.addColorStop(1, 'rgba(255,68,102,0)');
    }
    ctx.lineTo(padLeft + chartW, padTop + chartH);
    ctx.lineTo(padLeft, padTop + chartH);
    ctx.closePath();
    ctx.fillStyle = grad;
    ctx.fill();

    // Current price dot
    const lastX = padLeft + chartW;
    const lastY = padTop + ((maxP - prices[prices.length - 1]) / range) * chartH;
    ctx.beginPath();
    ctx.arc(lastX, lastY, 4, 0, Math.PI * 2);
    ctx.fillStyle = lineColor;
    ctx.fill();
    ctx.beginPath();
    ctx.arc(lastX, lastY, 8, 0, Math.PI * 2);
    ctx.fillStyle = glowColor;
    ctx.fill();

    // Current price label
    ctx.fillStyle = lineColor;
    ctx.font = 'bold 11px JetBrains Mono';
    ctx.textAlign = 'right';
    ctx.fillText('$' + prices[prices.length - 1].toFixed(2), lastX - 12, lastY - 10);
}

function setChartRange(n) {
    chartRange = n;
    document.querySelectorAll('.chart-tab').forEach(t => t.classList.remove('active'));
    event.target.classList.add('active');
    drawChart();
}

window.addEventListener('resize', drawChart);

// ============================================================
// INIT
// ============================================================
connectWS();
// Fallback polling every 5s in case WS fails
setInterval(() => {
    if (!ws || ws.readyState !== WebSocket.OPEN) pollData();
}, 5000);
// Initial data load
pollData();
</script>
</body>
</html>
"""


# ============================================================
# DASHBOARD SERVER
# ============================================================
class DashboardServer:
    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.app = web.Application()
        self.app.router.add_get('/', self.handle_index)
        self.app.router.add_get('/api/status', self.handle_status)
        self.app.router.add_get('/ws', self.handle_websocket)
        self.logs = []
        self.max_logs = 100
        self._ws_clients = set()
        self._push_task = None

    def add_log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.logs.append(f"{timestamp} {message}")
        if len(self.logs) > self.max_logs:
            self.logs = self.logs[-self.max_logs:]

    async def handle_index(self, request):
        return web.Response(text=DASHBOARD_HTML, content_type='text/html')

    def _get_status_data(self, price, dashboard):
        indicators = {}
        if hasattr(self.bot, 'last_indicators'):
            indicators = self.bot.last_indicators

        # Last signal info
        last_signal = None
        if hasattr(self.bot, 'last_signal') and self.bot.last_signal:
            sig = self.bot.last_signal
            last_signal = {
                "direction": sig.direction,
                "confidence": sig.confidence,
                "entry_price": sig.entry_price,
            }

        return {
            "price": price,
            "mode": config.TRADE_MODE.replace("_", " ").title(),
            "paper_trading": config.PAPER_TRADING,
            "analysis_count": self.bot.analysis_count,
            "last_update": datetime.now().strftime("%H:%M:%S"),
            "open_positions": dashboard["open_positions"],
            "open_pnl": dashboard["open_pnl_usd"],
            "total_pnl": dashboard["total_pnl_usd"],
            "win_rate": dashboard["win_rate"],
            "total_trades": dashboard["total_trades"],
            "positions": dashboard.get("positions", []),
            "indicators": indicators,
            "last_signal": last_signal,
            "logs": self.logs[-30:],
        }

    async def handle_status(self, request):
        try:
            price = await self.bot.price_fetcher.get_current_price()
            dashboard = self.bot.executor.get_dashboard_data(price)
            data = self._get_status_data(price, dashboard)
            return web.json_response(data)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    # --------------------------------------------------------
    # WEBSOCKET
    # --------------------------------------------------------
    async def handle_websocket(self, request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self._ws_clients.add(ws)
        logger.info(f"WebSocket client connected ({len(self._ws_clients)} total)")

        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    if msg.data == 'ping':
                        await ws.send_str('pong')
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    break
        finally:
            self._ws_clients.discard(ws)
            logger.info(f"WebSocket client disconnected ({len(self._ws_clients)} total)")

        return ws

    async def _push_loop(self):
        """Pushes updates to all WebSocket clients every 3 seconds."""
        while True:
            try:
                if self._ws_clients:
                    price = await self.bot.price_fetcher.get_current_price()
                    dashboard = self.bot.executor.get_dashboard_data(price)
                    data = self._get_status_data(price, dashboard)
                    payload = json.dumps(data)

                    dead = set()
                    for ws in self._ws_clients:
                        try:
                            await ws.send_str(payload)
                        except Exception:
                            dead.add(ws)
                    self._ws_clients -= dead

            except Exception as e:
                logger.debug(f"WS push error: {e}")

            await asyncio.sleep(3)

    async def start(self, host='0.0.0.0', port=8080):
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, host, port)
        await site.start()
        self._push_task = asyncio.create_task(self._push_loop())
        logger.info(f"Dashboard Pro rodando em http://localhost:{port}")
        logger.info(f"WebSocket ativo em ws://localhost:{port}/ws")
        logger.info(f"Para compartilhar: npx localtunnel --port {port}")
        return runner
