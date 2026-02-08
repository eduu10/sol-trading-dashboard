"""
Dashboard Web Standalone - Deploy na Nuvem (Render/Railway)
============================================================
Roda como servico independente. Recebe dados do bot via POST.
Qualquer pessoa acessa o link fixo para ver o dashboard.

Deploy: Render.com (gratis)
"""

import os
import json
import time
from datetime import datetime
from aiohttp import web
import asyncio
import logging

logger = logging.getLogger("WebDashboard")

# Dados compartilhados (in-memory)
BOT_DATA = {
    "price": 0,
    "capital": 500.0,
    "mode": "Day Trade",
    "paper_trading": True,
    "analysis_count": 0,
    "last_update": "--:--:--",
    "open_positions": 0,
    "open_pnl": 0,
    "total_pnl": 0,
    "win_rate": "N/A",
    "total_trades": 0,
    "positions": [],
    "indicators": {},
    "last_signal": None,
    "logs": [],
    "last_push": 0,
}

# Secret key para o bot enviar dados (evita spam)
API_KEY = os.environ.get("DASHBOARD_API_KEY", "sol-trading-2026")


# ============================================================
# HTML - mesmo dashboard profissional
# ============================================================
def get_dashboard_html():
    return r"""
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
            --yellow: #ffaa00;
            --yellow-dark: rgba(255,170,0,0.1);
            --purple: #aa66ff;
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
        body::before {
            content: '';
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background:
                radial-gradient(ellipse at 20% 50%, rgba(0,255,136,0.03) 0%, transparent 50%),
                radial-gradient(ellipse at 80% 20%, rgba(68,136,255,0.03) 0%, transparent 50%),
                radial-gradient(ellipse at 50% 80%, rgba(170,102,255,0.02) 0%, transparent 50%);
            pointer-events: none; z-index: 0;
        }
        .app { position: relative; z-index: 1; }
        .header {
            padding: 20px 30px;
            display: flex; align-items: center; justify-content: space-between;
            border-bottom: 1px solid var(--border-color);
            backdrop-filter: blur(20px);
            background: rgba(10,10,15,0.8);
            position: sticky; top: 0; z-index: 100;
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
        .header-title { font-size: 1.3em; font-weight: 700; letter-spacing: -0.5px; }
        .header-title span { color: var(--text-muted); font-weight: 400; }
        .header-right { display: flex; align-items: center; gap: 20px; }
        .connection-status { display: flex; align-items: center; gap: 8px; font-size: 0.8em; color: var(--text-secondary); }
        .status-dot {
            width: 8px; height: 8px; border-radius: 50%;
            background: var(--green); box-shadow: 0 0 8px var(--green-glow);
            animation: pulse-dot 2s infinite;
        }
        .status-dot.offline { background: var(--red); box-shadow: 0 0 8px var(--red-glow); animation: none; }
        .status-dot.stale { background: var(--yellow); box-shadow: 0 0 8px rgba(255,170,0,0.4); }
        @keyframes pulse-dot { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.5; transform: scale(0.8); } }
        .mode-badge {
            padding: 6px 14px; border-radius: 8px; font-size: 0.75em;
            font-weight: 600; letter-spacing: 1px; text-transform: uppercase;
        }
        .mode-paper { background: var(--yellow-dark); color: var(--yellow); border: 1px solid rgba(255,170,0,0.2); }
        .mode-live { background: var(--red-dark); color: var(--red); border: 1px solid rgba(255,68,102,0.2); }
        .main {
            max-width: 1440px; margin: 0 auto; padding: 24px;
            display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px;
        }
        .card {
            background: var(--bg-card); border: 1px solid var(--border-color);
            border-radius: 16px; padding: 24px;
            transition: all 0.3s ease; position: relative; overflow: hidden;
        }
        .card::before {
            content: ''; position: absolute; top: 0; left: 0; right: 0; height: 1px;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent);
        }
        .card:hover {
            background: var(--bg-card-hover); border-color: var(--border-glow);
            transform: translateY(-2px); box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        }
        .card-label {
            font-size: 0.7em; font-weight: 600; text-transform: uppercase;
            letter-spacing: 1.5px; color: var(--text-muted); margin-bottom: 16px;
            display: flex; align-items: center; gap: 8px;
        }
        .card-label svg { width: 14px; height: 14px; opacity: 0.5; }
        .price-card { grid-column: 1 / 2; }
        .price-main {
            font-size: 3em; font-weight: 800; letter-spacing: -2px; line-height: 1;
            margin-bottom: 8px; font-family: 'JetBrains Mono', monospace;
        }
        .price-main.glow-green { color: var(--green); text-shadow: 0 0 30px var(--green-glow); }
        .price-main.glow-red { color: var(--red); text-shadow: 0 0 30px var(--red-glow); }
        .price-change {
            display: inline-flex; align-items: center; gap: 4px; padding: 4px 10px;
            border-radius: 6px; font-size: 0.85em; font-weight: 600;
            font-family: 'JetBrains Mono', monospace;
        }
        .price-change.up { background: var(--green-dark); color: var(--green); }
        .price-change.down { background: var(--red-dark); color: var(--red); }
        .price-pair { margin-top: 12px; font-size: 0.85em; color: var(--text-secondary); }
        .pnl-card { grid-column: 2 / 3; }
        .pnl-value { font-size: 2.4em; font-weight: 800; font-family: 'JetBrains Mono', monospace; letter-spacing: -1px; }
        .pnl-value.profit { color: var(--green); text-shadow: 0 0 20px var(--green-glow); }
        .pnl-value.loss { color: var(--red); text-shadow: 0 0 20px var(--red-glow); }
        .pnl-sub { display: flex; gap: 20px; margin-top: 16px; }
        .pnl-sub-item { display: flex; flex-direction: column; gap: 4px; }
        .pnl-sub-label { font-size: 0.7em; color: var(--text-muted); text-transform: uppercase; letter-spacing: 1px; }
        .pnl-sub-value { font-size: 1.1em; font-weight: 600; font-family: 'JetBrains Mono', monospace; }
        .status-card { grid-column: 3 / 4; }
        .status-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
        .status-item { background: rgba(255,255,255,0.02); border-radius: 10px; padding: 14px; text-align: center; }
        .status-item-value { font-size: 1.6em; font-weight: 700; font-family: 'JetBrains Mono', monospace; margin-bottom: 4px; }
        .status-item-label { font-size: 0.7em; color: var(--text-muted); text-transform: uppercase; letter-spacing: 1px; }
        .chart-card { grid-column: 1 / 3; min-height: 320px; }
        .chart-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
        .chart-tabs { display: flex; gap: 4px; }
        .chart-tab {
            padding: 6px 12px; border-radius: 6px; font-size: 0.75em; font-weight: 500;
            cursor: pointer; background: transparent; color: var(--text-muted); border: none; transition: all 0.2s;
        }
        .chart-tab:hover { color: var(--text-secondary); background: rgba(255,255,255,0.05); }
        .chart-tab.active { background: rgba(0,255,136,0.1); color: var(--green); }
        .chart-container { width: 100%; height: 260px; position: relative; }
        canvas#priceChart { width: 100% !important; height: 100% !important; }
        .indicators-card { grid-column: 3 / 4; }
        .indicator-row { display: flex; justify-content: space-between; align-items: center; padding: 12px 0; border-bottom: 1px solid var(--border-color); }
        .indicator-row:last-child { border-bottom: none; }
        .indicator-name { font-size: 0.85em; font-weight: 500; display: flex; align-items: center; gap: 8px; }
        .indicator-dot { width: 6px; height: 6px; border-radius: 50%; }
        .indicator-dot.bullish { background: var(--green); box-shadow: 0 0 6px var(--green-glow); }
        .indicator-dot.bearish { background: var(--red); box-shadow: 0 0 6px var(--red-glow); }
        .indicator-dot.neutral { background: var(--text-muted); }
        .indicator-value { font-family: 'JetBrains Mono', monospace; font-size: 0.85em; font-weight: 600; }
        .indicator-bar { width: 100%; height: 4px; background: rgba(255,255,255,0.05); border-radius: 2px; margin-top: 6px; overflow: hidden; }
        .indicator-bar-fill { height: 100%; border-radius: 2px; transition: width 0.8s ease, background 0.5s ease; }
        .indicator-bar-fill.bullish { background: linear-gradient(90deg, var(--green-dim), var(--green)); }
        .indicator-bar-fill.bearish { background: linear-gradient(90deg, var(--red), var(--red-dim)); }
        .indicator-bar-fill.neutral { background: var(--text-muted); }
        .indicator-toggle { position: relative; display: inline-block; width: 28px; height: 16px; flex-shrink: 0; margin-right: 8px; cursor: pointer; }
        .indicator-toggle input { opacity: 0; width: 0; height: 0; }
        .toggle-slider { position: absolute; top: 0; left: 0; right: 0; bottom: 0; background: rgba(255,255,255,0.08); border-radius: 8px; transition: all 0.3s ease; }
        .toggle-slider::before { content: ''; position: absolute; width: 12px; height: 12px; left: 2px; top: 2px; background: var(--text-muted); border-radius: 50%; transition: all 0.3s ease; }
        .indicator-toggle input:checked + .toggle-slider { background: color-mix(in srgb, var(--toggle-color) 25%, transparent); box-shadow: 0 0 8px color-mix(in srgb, var(--toggle-color) 30%, transparent); }
        .indicator-toggle input:checked + .toggle-slider::before { transform: translateX(12px); background: var(--toggle-color); box-shadow: 0 0 4px var(--toggle-color); }
        .chart-legend { display: flex; gap: 10px; flex-wrap: wrap; padding: 6px 0 0 0; }
        .chart-legend-item { display: flex; align-items: center; gap: 4px; font-size: 0.7em; color: var(--text-secondary); font-family: 'JetBrains Mono', monospace; }
        .chart-legend-dot { width: 8px; height: 3px; border-radius: 1px; }
        .signals-card { grid-column: 1 / 2; }
        .signal-badge {
            display: inline-flex; align-items: center; gap: 6px; padding: 10px 18px;
            border-radius: 10px; font-size: 0.9em; font-weight: 700; letter-spacing: 0.5px;
            width: 100%; justify-content: center; margin-bottom: 12px;
        }
        .signal-long { background: linear-gradient(135deg, rgba(0,255,136,0.15), rgba(0,255,136,0.05)); color: var(--green); border: 1px solid rgba(0,255,136,0.2); box-shadow: 0 0 20px rgba(0,255,136,0.1); }
        .signal-short { background: linear-gradient(135deg, rgba(255,68,102,0.15), rgba(255,68,102,0.05)); color: var(--red); border: 1px solid rgba(255,68,102,0.2); box-shadow: 0 0 20px rgba(255,68,102,0.1); }
        .signal-none { background: rgba(255,255,255,0.03); color: var(--text-muted); border: 1px solid var(--border-color); }
        .signal-confidence { margin-top: 8px; display: flex; align-items: center; gap: 10px; }
        .confidence-bar { flex: 1; height: 6px; background: rgba(255,255,255,0.05); border-radius: 3px; overflow: hidden; }
        .confidence-fill { height: 100%; border-radius: 3px; background: linear-gradient(90deg, var(--blue), var(--green)); transition: width 1s ease; }
        .confidence-text { font-family: 'JetBrains Mono', monospace; font-size: 0.85em; font-weight: 600; min-width: 40px; text-align: right; }
        .positions-card { grid-column: 2 / 4; }
        .position-item {
            display: grid; grid-template-columns: 80px 1fr 1fr 1fr 80px; align-items: center;
            gap: 16px; padding: 14px 16px; background: rgba(255,255,255,0.02);
            border-radius: 10px; margin-bottom: 8px; border: 1px solid var(--border-color); transition: all 0.2s;
        }
        .position-item:hover { background: rgba(255,255,255,0.04); }
        .position-direction { padding: 4px 10px; border-radius: 6px; font-size: 0.75em; font-weight: 700; text-align: center; text-transform: uppercase; }
        .position-long { background: var(--green-dark); color: var(--green); }
        .position-short { background: var(--red-dark); color: var(--red); }
        .position-field-label { font-size: 0.65em; color: var(--text-muted); text-transform: uppercase; letter-spacing: 1px; }
        .position-field-value { font-family: 'JetBrains Mono', monospace; font-size: 0.9em; font-weight: 600; margin-top: 2px; }
        .no-positions { text-align: center; padding: 30px; color: var(--text-muted); font-size: 0.9em; }
        .log-card { grid-column: 1 / 4; }
        .log-container {
            background: rgba(0,0,0,0.3); border: 1px solid var(--border-color);
            border-radius: 10px; padding: 16px; max-height: 240px; overflow-y: auto;
            font-family: 'JetBrains Mono', monospace; font-size: 0.78em; line-height: 1.8;
        }
        .log-container::-webkit-scrollbar { width: 6px; }
        .log-container::-webkit-scrollbar-track { background: transparent; }
        .log-container::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 3px; }
        .log-line { padding: 2px 0; display: flex; gap: 8px; opacity: 0; animation: fadeIn 0.3s ease forwards; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }
        .log-time { color: var(--text-muted); min-width: 60px; }
        .log-msg { flex: 1; }
        .log-info { color: var(--blue); }
        .log-success { color: var(--green); }
        .log-error { color: var(--red); }
        .log-warn { color: var(--yellow); }
        .footer { text-align: center; padding: 20px; color: var(--text-muted); font-size: 0.75em; border-top: 1px solid var(--border-color); margin-top: 16px; }
        @media (max-width: 1024px) {
            .main { grid-template-columns: 1fr 1fr; }
            .chart-card, .positions-card, .log-card { grid-column: 1 / 3; }
            .indicators-card { grid-column: 1 / 2; }
            .signals-card { grid-column: 2 / 3; }
            .price-card, .pnl-card, .status-card { grid-column: auto; }
        }
        @media (max-width: 768px) {
            .main { grid-template-columns: 1fr; padding: 12px; }
            .chart-card, .indicators-card, .signals-card, .positions-card, .log-card,
            .price-card, .pnl-card, .status-card { grid-column: 1 / 2; }
            .price-main { font-size: 2.2em; }
            .header { padding: 14px 16px; }
            .header-title { font-size: 1em; }
            .position-item { grid-template-columns: 1fr 1fr; }
        }
    </style>
</head>
<body>
<div class="app">
    <header class="header">
        <div class="header-left">
            <div class="logo">S</div>
            <div><div class="header-title">SOL/USDC <span>Trading Bot</span></div></div>
        </div>
        <div class="header-right">
            <div class="connection-status">
                <div class="status-dot" id="ws-dot"></div>
                <span id="ws-status">Conectando...</span>
            </div>
            <span class="mode-badge mode-paper" id="mode-badge">PAPER</span>
        </div>
    </header>
    <main class="main">
        <div class="card price-card">
            <div class="card-label"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"/></svg> Preco Atual</div>
            <div class="price-main glow-green" id="price">$---.--</div>
            <span class="price-change up" id="price-change">-- %</span>
            <div class="price-pair">SOL / USDC &middot; <span id="last-update-time">--:--:--</span></div>
        </div>
        <div class="card pnl-card">
            <div class="card-label"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></svg> P&amp;L Total</div>
            <div class="pnl-value profit" id="total-pnl">$0.00</div>
            <div class="pnl-sub">
                <div class="pnl-sub-item"><span class="pnl-sub-label">Capital</span><span class="pnl-sub-value" id="capital" style="color:var(--yellow)">$500.00</span></div>
                <div class="pnl-sub-item"><span class="pnl-sub-label">Aberto</span><span class="pnl-sub-value" id="open-pnl">$0.00</span></div>
                <div class="pnl-sub-item"><span class="pnl-sub-label">Win Rate</span><span class="pnl-sub-value" id="win-rate">N/A</span></div>
                <div class="pnl-sub-item"><span class="pnl-sub-label">Trades</span><span class="pnl-sub-value" id="total-trades">0</span></div>
            </div>
        </div>
        <div class="card status-card">
            <div class="card-label"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/></svg> Status do Bot</div>
            <div class="status-grid">
                <div class="status-item"><div class="status-item-value" id="analysis-count" style="color:var(--blue)">0</div><div class="status-item-label">Analises</div></div>
                <div class="status-item"><div class="status-item-value" id="open-positions" style="color:var(--purple)">0</div><div class="status-item-label">Posicoes</div></div>
                <div class="status-item"><div class="status-item-value" id="trade-mode" style="color:var(--yellow);font-size:0.9em">Day</div><div class="status-item-label">Modo</div></div>
                <div class="status-item"><div class="status-item-value" id="loop-timer" style="color:var(--text-secondary)">45s</div><div class="status-item-label">Intervalo</div></div>
            </div>
        </div>
        <div class="card chart-card">
            <div class="chart-header">
                <div class="card-label" style="margin-bottom:0"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg> Historico de Precos</div>
                <div class="chart-tabs">
                    <button class="chart-tab active" onclick="setChartRange(20)">20</button>
                    <button class="chart-tab" onclick="setChartRange(50)">50</button>
                    <button class="chart-tab" onclick="setChartRange(100)">100</button>
                    <button class="chart-tab" onclick="setChartRange(0)">All</button>
                </div>
            </div>
            <div class="chart-container"><canvas id="priceChart"></canvas></div>
            <div class="chart-legend" id="chart-legend"></div>
        </div>
        <div class="card indicators-card">
            <div class="card-label"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20V10M18 20V4M6 20v-4"/></svg> Indicadores</div>
            <div id="indicators-list">
                <div class="indicator-row" id="ind-rsi"><label class="indicator-toggle"><input type="checkbox" id="chk-rsi" onchange="toggleIndicatorOverlay('rsi')"/><span class="toggle-slider" style="--toggle-color:#ffaa00"></span></label><div style="flex:1;min-width:0"><div class="indicator-name"><span class="indicator-dot neutral"></span> RSI</div><div class="indicator-bar"><div class="indicator-bar-fill neutral" style="width:50%"></div></div></div><div class="indicator-value">--</div></div>
                <div class="indicator-row" id="ind-ema"><label class="indicator-toggle"><input type="checkbox" id="chk-ema" onchange="toggleIndicatorOverlay('ema')"/><span class="toggle-slider" style="--toggle-color:#00aaff"></span></label><div style="flex:1;min-width:0"><div class="indicator-name"><span class="indicator-dot neutral"></span> EMA</div><div class="indicator-bar"><div class="indicator-bar-fill neutral" style="width:50%"></div></div></div><div class="indicator-value">--</div></div>
                <div class="indicator-row" id="ind-ichimoku"><label class="indicator-toggle"><input type="checkbox" id="chk-ichimoku" onchange="toggleIndicatorOverlay('ichimoku')"/><span class="toggle-slider" style="--toggle-color:#ff66ff"></span></label><div style="flex:1;min-width:0"><div class="indicator-name"><span class="indicator-dot neutral"></span> Ichimoku</div><div class="indicator-bar"><div class="indicator-bar-fill neutral" style="width:50%"></div></div></div><div class="indicator-value">--</div></div>
                <div class="indicator-row" id="ind-volume"><label class="indicator-toggle"><input type="checkbox" id="chk-volume" onchange="toggleIndicatorOverlay('volume')"/><span class="toggle-slider" style="--toggle-color:#66ffcc"></span></label><div style="flex:1;min-width:0"><div class="indicator-name"><span class="indicator-dot neutral"></span> Volume</div><div class="indicator-bar"><div class="indicator-bar-fill neutral" style="width:50%"></div></div></div><div class="indicator-value">--</div></div>
            </div>
        </div>
        <div class="card signals-card">
            <div class="card-label"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg> Ultimo Sinal</div>
            <div class="signal-badge signal-none" id="signal-badge"><span>AGUARDANDO SINAL</span></div>
            <div class="signal-confidence">
                <span style="font-size:0.75em;color:var(--text-muted)">Confianca</span>
                <div class="confidence-bar"><div class="confidence-fill" id="confidence-fill" style="width:0%"></div></div>
                <span class="confidence-text" id="confidence-text">0%</span>
            </div>
        </div>
        <div class="card positions-card">
            <div class="card-label"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 21V5a2 2 0 00-2-2h-4a2 2 0 00-2 2v16"/></svg> Posicoes Abertas</div>
            <div id="positions-container"><div class="no-positions">Nenhuma posicao aberta</div></div>
        </div>
        <div class="card log-card">
            <div class="card-label"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg> Terminal</div>
            <div class="log-container" id="log-container">
                <div class="log-line"><span class="log-time">--:--</span><span class="log-msg" style="color:var(--text-muted)">Aguardando dados do bot...</span></div>
            </div>
        </div>
    </main>
    <footer class="footer">SOL/USDC Trading Bot &middot; Paper Trading Mode &middot; Powered by Jupiter DEX + GeckoTerminal</footer>
</div>
<script>
let priceHistory = [];
let chartRange = 50;
let lastPrice = 0;
let prevPrice = 0;
const indicatorOverlays = {
    rsi:      { enabled: false, color: '#ffaa00', label: 'RSI',      history: [], min: 0, max: 100 },
    ema:      { enabled: false, color: '#00aaff', label: 'EMA',      history: [], min: -1, max: 1 },
    ichimoku: { enabled: false, color: '#ff66ff', label: 'Ichimoku', history: [], min: -1, max: 1 },
    volume:   { enabled: false, color: '#66ffcc', label: 'Volume',   history: [], min: 0, max: 3 }
};
function toggleIndicatorOverlay(id) { indicatorOverlays[id].enabled = document.getElementById('chk-' + id).checked; updateChartLegend(); drawChart(); }
function updateChartLegend() { const legend = document.getElementById('chart-legend'); let html = '';
    for (const [id, ind] of Object.entries(indicatorOverlays)) { if (ind.enabled) html += '<div class="chart-legend-item"><span class="chart-legend-dot" style="background:' + ind.color + '"></span>' + ind.label + '</div>'; }
    legend.innerHTML = html; }

async function pollData() {
    try {
        const r = await fetch('/api/data');
        const data = await r.json();
        if (data.price > 0) {
            updateDashboard(data);
            document.getElementById('ws-dot').className = 'status-dot';
            document.getElementById('ws-status').textContent = 'Online';
        }
        // Check staleness
        if (data.last_push && Date.now()/1000 - data.last_push > 120) {
            document.getElementById('ws-dot').className = 'status-dot stale';
            document.getElementById('ws-status').textContent = 'Bot offline';
        }
    } catch(e) {
        document.getElementById('ws-dot').className = 'status-dot offline';
        document.getElementById('ws-status').textContent = 'Erro';
    }
}

function updateDashboard(data) {
    const price = data.price || 0;
    prevPrice = lastPrice; lastPrice = price;
    const priceEl = document.getElementById('price');
    priceEl.textContent = '$' + price.toFixed(2);
    if (prevPrice > 0) {
        priceEl.className = 'price-main ' + (price >= prevPrice ? 'glow-green' : 'glow-red');
        const changePct = ((price - prevPrice) / prevPrice * 100);
        const changeEl = document.getElementById('price-change');
        changeEl.textContent = (changePct >= 0 ? '+' : '') + changePct.toFixed(3) + '%';
        changeEl.className = 'price-change ' + (changePct >= 0 ? 'up' : 'down');
    }
    if (price > 0) { priceHistory.push({time:new Date(),price}); if(priceHistory.length>500) priceHistory=priceHistory.slice(-500); drawChart(); }
    document.getElementById('last-update-time').textContent = data.last_update || '--:--:--';
    const totalPnl = data.total_pnl||0; const tpEl = document.getElementById('total-pnl');
    tpEl.textContent = (totalPnl>=0?'+':'')+'$'+totalPnl.toFixed(2); tpEl.className='pnl-value '+(totalPnl>=0?'profit':'loss');
    const openPnl = data.open_pnl||0; const opEl = document.getElementById('open-pnl');
    opEl.textContent = (openPnl>=0?'+':'')+'$'+openPnl.toFixed(2); opEl.style.color = openPnl>=0?'var(--green)':'var(--red)';
    document.getElementById('win-rate').textContent = data.win_rate||'N/A';
    document.getElementById('total-trades').textContent = data.total_trades||'0';
    if(data.capital){document.getElementById('capital').textContent='$'+data.capital.toFixed(2);}
    document.getElementById('analysis-count').textContent = data.analysis_count||'0';
    document.getElementById('open-positions').textContent = data.open_positions||'0';
    document.getElementById('trade-mode').textContent = (data.mode||'Day Trade').replace(' Trade','');
    const mb = document.getElementById('mode-badge');
    if(data.paper_trading){mb.textContent='PAPER';mb.className='mode-badge mode-paper';}else{mb.textContent='LIVE';mb.className='mode-badge mode-live';}
    if(data.indicators){
        updateIndicator('rsi','RSI',data.indicators.RSI,0,100,v=>{if(v<30)return'bullish';if(v>70)return'bearish';return'neutral';},v=>v.toFixed(1));
        updateIndicator('ema','EMA',data.indicators.EMA,-1,1,v=>{if(v>0.2)return'bullish';if(v<-0.2)return'bearish';return'neutral';},v=>v.toFixed(2));
        updateIndicator('ichimoku','Ichimoku',data.indicators.Ichimoku,-1,1,v=>{if(v>0.2)return'bullish';if(v<-0.2)return'bearish';return'neutral';},v=>v.toFixed(2));
        updateIndicator('volume','Volume',data.indicators.Volume,0,3,v=>{if(v>1.5)return'bullish';if(v<0.5)return'bearish';return'neutral';},v=>v.toFixed(2)+'x');
        const indMap={rsi:'RSI',ema:'EMA',ichimoku:'Ichimoku',volume:'Volume'};
        for(const[key,dk]of Object.entries(indMap)){const val=data.indicators[dk];if(val!==undefined&&val!==null){indicatorOverlays[key].history.push({time:new Date(),value:val});if(indicatorOverlays[key].history.length>500)indicatorOverlays[key].history=indicatorOverlays[key].history.slice(-500);}}
    }
    if(data.last_signal){const sig=data.last_signal;const sb=document.getElementById('signal-badge');
        if(sig.direction==='long'){sb.className='signal-badge signal-long';sb.innerHTML='<span>&#9650; LONG (COMPRA)</span>';}
        else if(sig.direction==='short'){sb.className='signal-badge signal-short';sb.innerHTML='<span>&#9660; SHORT (VENDA)</span>';}
        const conf=(sig.confidence||0)*100;document.getElementById('confidence-fill').style.width=conf+'%';document.getElementById('confidence-text').textContent=conf.toFixed(0)+'%';
    }
    if(data.positions&&data.positions.length>0){let h='';for(const p of data.positions){const dc=p.direction==='long'?'position-long':'position-short';const pc=p.pnl_pct>=0?'var(--green)':'var(--red)';
        h+=`<div class="position-item"><span class="position-direction ${dc}">${p.direction.toUpperCase()}</span><div><div class="position-field-label">Entrada</div><div class="position-field-value">$${p.entry_price.toFixed(2)}</div></div><div><div class="position-field-label">P&L</div><div class="position-field-value" style="color:${pc}">${p.pnl_pct>=0?'+':''}${p.pnl_pct.toFixed(2)}%</div></div><div><div class="position-field-label">SL / TP</div><div class="position-field-value">$${p.stop_loss.toFixed(2)} / $${p.take_profits[0].toFixed(2)}</div></div><div><div class="position-field-label">USD</div><div class="position-field-value" style="color:${pc}">${p.pnl_usd>=0?'+':''}$${p.pnl_usd.toFixed(2)}</div></div></div>`;}
        document.getElementById('positions-container').innerHTML=h;}else{document.getElementById('positions-container').innerHTML='<div class="no-positions">Nenhuma posicao aberta</div>';}
    if(data.logs&&data.logs.length>0){let lh='';for(const log of data.logs.slice(-30)){let cls='';if(log.includes('ERRO')||log.includes('ERROR'))cls='log-error';else if(log.includes('WARN'))cls='log-warn';else if(log.includes('Sinal')||log.includes('BUY')||log.includes('SELL'))cls='log-success';else cls='log-info';
        const parts=log.split(' ');lh+=`<div class="log-line"><span class="log-time">${parts[0]||''}</span><span class="log-msg ${cls}">${parts.slice(1).join(' ')}</span></div>`;}
        const c=document.getElementById('log-container');c.innerHTML=lh;c.scrollTop=c.scrollHeight;}
}
function updateIndicator(id,name,value,min,max,getState,format){if(value===undefined||value===null)return;const row=document.getElementById('ind-'+id);if(!row)return;const state=getState(value);const pct=Math.max(0,Math.min(100,((value-min)/(max-min))*100));
    row.querySelector('.indicator-dot').className='indicator-dot '+state;const bar=row.querySelector('.indicator-bar-fill');bar.style.width=pct+'%';bar.className='indicator-bar-fill '+state;
    const val=row.querySelector('.indicator-value');val.textContent=format(value);val.style.color=state==='bullish'?'var(--green)':state==='bearish'?'var(--red)':'var(--text-secondary)';}
function drawChart(){const canvas=document.getElementById('priceChart');if(!canvas)return;const ctx=canvas.getContext('2d');const rect=canvas.parentElement.getBoundingClientRect();
    canvas.width=rect.width*2;canvas.height=rect.height*2;ctx.scale(2,2);const W=rect.width;const H=rect.height;let data=priceHistory;if(chartRange>0)data=data.slice(-chartRange);
    if(data.length<2){ctx.clearRect(0,0,W,H);ctx.fillStyle='#555566';ctx.font='13px Inter';ctx.textAlign='center';ctx.fillText('Aguardando dados de preco...',W/2,H/2);return;}
    const prices=data.map(d=>d.price);const minP=Math.min(...prices)*0.9998;const maxP=Math.max(...prices)*1.0002;const range=maxP-minP||1;
    const pT=30,pB=30,pL=60,pR=20,cW=W-pL-pR,cH=H-pT-pB;ctx.clearRect(0,0,W,H);
    ctx.strokeStyle='rgba(255,255,255,0.04)';ctx.lineWidth=1;for(let i=0;i<=4;i++){const y=pT+(cH/4)*i;ctx.beginPath();ctx.moveTo(pL,y);ctx.lineTo(W-pR,y);ctx.stroke();ctx.fillStyle='#555566';ctx.font='10px JetBrains Mono';ctx.textAlign='right';ctx.fillText('$'+(maxP-(range/4)*i).toFixed(2),pL-8,y+3);}
    const isUp=prices[prices.length-1]>=prices[0];const lc=isUp?'#00ff88':'#ff4466';const gc=isUp?'rgba(0,255,136,0.3)':'rgba(255,68,102,0.3)';
    ctx.strokeStyle=gc;ctx.lineWidth=6;ctx.lineJoin='round';ctx.lineCap='round';ctx.beginPath();for(let i=0;i<prices.length;i++){const x=pL+(i/(prices.length-1))*cW;const y=pT+((maxP-prices[i])/range)*cH;if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);}ctx.stroke();
    ctx.strokeStyle=lc;ctx.lineWidth=2;ctx.beginPath();for(let i=0;i<prices.length;i++){const x=pL+(i/(prices.length-1))*cW;const y=pT+((maxP-prices[i])/range)*cH;if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);}ctx.stroke();
    const grad=ctx.createLinearGradient(0,pT,0,H-pB);if(isUp){grad.addColorStop(0,'rgba(0,255,136,0.15)');grad.addColorStop(1,'rgba(0,255,136,0)');}else{grad.addColorStop(0,'rgba(255,68,102,0.15)');grad.addColorStop(1,'rgba(255,68,102,0)');}
    ctx.lineTo(pL+cW,pT+cH);ctx.lineTo(pL,pT+cH);ctx.closePath();ctx.fillStyle=grad;ctx.fill();
    const lX=pL+cW,lY=pT+((maxP-prices[prices.length-1])/range)*cH;ctx.beginPath();ctx.arc(lX,lY,4,0,Math.PI*2);ctx.fillStyle=lc;ctx.fill();ctx.beginPath();ctx.arc(lX,lY,8,0,Math.PI*2);ctx.fillStyle=gc;ctx.fill();
    ctx.fillStyle=lc;ctx.font='bold 11px JetBrains Mono';ctx.textAlign='right';ctx.fillText('$'+prices[prices.length-1].toFixed(2),lX-12,lY-10);
    const activeOvl=Object.values(indicatorOverlays).filter(o=>o.enabled&&o.history.length>=2);
    if(activeOvl.length>0){activeOvl.forEach(ind=>{let indData=ind.history;if(chartRange>0)indData=indData.slice(-chartRange);if(indData.length<2)return;
        const len=Math.min(indData.length,prices.length);const aligned=indData.slice(-len);const iMin=ind.min;const iMax=ind.max;const iR=iMax-iMin||1;
        ctx.save();ctx.globalAlpha=0.25;ctx.strokeStyle=ind.color;ctx.lineWidth=4;ctx.lineJoin='round';ctx.lineCap='round';ctx.beginPath();
        for(let i=0;i<aligned.length;i++){const x=pL+((prices.length-len+i)/(prices.length-1))*cW;const y=pT+((iMax-aligned[i].value)/iR)*cH;if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);}ctx.stroke();ctx.restore();
        ctx.save();ctx.globalAlpha=0.85;ctx.strokeStyle=ind.color;ctx.lineWidth=1.5;ctx.lineJoin='round';ctx.lineCap='round';ctx.setLineDash([4,3]);ctx.beginPath();
        for(let i=0;i<aligned.length;i++){const x=pL+((prices.length-len+i)/(prices.length-1))*cW;const y=pT+((iMax-aligned[i].value)/iR)*cH;if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);}ctx.stroke();ctx.setLineDash([]);
        const lastVal=aligned[aligned.length-1].value;const lastIY=pT+((iMax-lastVal)/iR)*cH;ctx.fillStyle=ind.color;ctx.font='bold 9px JetBrains Mono';ctx.textAlign='left';ctx.fillText(ind.label+' '+lastVal.toFixed(1),pL+4,lastIY-5);ctx.restore();});}}
function setChartRange(n){chartRange=n;document.querySelectorAll('.chart-tab').forEach(t=>t.classList.remove('active'));event.target.classList.add('active');drawChart();}
window.addEventListener('resize',drawChart);
setInterval(pollData, 5000);
pollData();
</script>
</body>
</html>
"""


# ============================================================
# ROUTES
# ============================================================
async def handle_index(request):
    return web.Response(text=get_dashboard_html(), content_type='text/html')


async def handle_get_data(request):
    """Frontend polls this endpoint."""
    return web.json_response(BOT_DATA)


async def handle_push_data(request):
    """Bot pushes data here via POST."""
    auth = request.headers.get("X-API-Key", "")
    if auth != API_KEY:
        return web.json_response({"error": "unauthorized"}, status=401)

    try:
        data = await request.json()
        BOT_DATA.update(data)
        BOT_DATA["last_push"] = time.time()
        return web.json_response({"ok": True})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400)


async def handle_health(request):
    return web.json_response({"status": "ok", "last_push": BOT_DATA.get("last_push", 0)})


# ============================================================
# APP
# ============================================================
def create_app():
    app = web.Application()
    app.router.add_get('/', handle_index)
    app.router.add_get('/api/data', handle_get_data)
    app.router.add_post('/api/push', handle_push_data)
    app.router.add_get('/health', handle_health)
    return app


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    logging.basicConfig(level=logging.INFO)
    app = create_app()
    web.run_app(app, host="0.0.0.0", port=port)
