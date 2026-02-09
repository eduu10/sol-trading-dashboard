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
from datetime import datetime, timezone, timedelta
from aiohttp import web

BR_TZ = timezone(timedelta(hours=-3))

def now_br():
    return datetime.now(BR_TZ)
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
        .settings-btn {
            background: rgba(255,255,255,0.06); border: 1px solid var(--border-color); cursor: pointer;
            padding: 8px; border-radius: 10px;
            color: var(--text-primary); transition: all 0.2s;
            display: flex; align-items: center; justify-content: center;
        }
        .settings-btn:hover { background: rgba(255,255,255,0.12); transform: rotate(45deg); border-color: var(--purple); color: var(--purple); }
        .settings-btn svg { width: 22px; height: 22px; }
        .modal-overlay {
            display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.7); backdrop-filter: blur(8px);
            z-index: 9999; align-items: center; justify-content: center;
        }
        .modal-overlay.active { display: flex; }
        .modal-box {
            background: var(--bg-card); border: 1px solid var(--border-color);
            border-radius: 16px; padding: 32px; width: 440px; max-width: 95vw;
            box-shadow: 0 20px 60px rgba(0,0,0,0.5);
        }
        .modal-header {
            display: flex; align-items: center; justify-content: space-between;
            margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid var(--border-color);
        }
        .modal-header h2 {
            font-size: 1.2em; font-weight: 700; display: flex; align-items: center; gap: 10px;
        }
        .modal-header h2 svg { width: 22px; height: 22px; color: var(--purple); }
        .modal-close {
            background: none; border: none; cursor: pointer; color: var(--text-muted);
            font-size: 1.5em; line-height: 1; padding: 4px 8px; border-radius: 8px;
            transition: background 0.2s, color 0.2s;
        }
        .modal-close:hover { background: rgba(255,255,255,0.05); color: var(--text-primary); }
        .setting-group { margin-bottom: 20px; }
        .setting-label {
            font-size: 0.8em; font-weight: 600; color: var(--text-secondary);
            text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;
        }
        .setting-desc { font-size: 0.75em; color: var(--text-muted); margin-bottom: 8px; }
        .setting-input-wrap {
            position: relative; display: flex; align-items: center;
        }
        .setting-input-wrap input {
            width: 100%; background: var(--bg-secondary); border: 1px solid var(--border-color);
            border-radius: 10px; padding: 12px 44px 12px 14px; color: var(--text-primary);
            font-family: 'JetBrains Mono', monospace; font-size: 0.85em;
            transition: border-color 0.2s;
        }
        .setting-input-wrap input:focus { outline: none; border-color: var(--purple); }
        .setting-input-wrap input::placeholder { color: var(--text-muted); }
        .toggle-pw-btn {
            position: absolute; right: 8px; background: none; border: none;
            cursor: pointer; color: var(--text-muted); padding: 6px;
            transition: color 0.2s;
        }
        .toggle-pw-btn:hover { color: var(--text-primary); }
        .toggle-pw-btn svg { width: 18px; height: 18px; }
        .setting-toggle {
            display: flex; align-items: center; justify-content: space-between;
            background: var(--bg-secondary); border: 1px solid var(--border-color);
            border-radius: 10px; padding: 14px;
        }
        .setting-toggle-label { font-size: 0.9em; font-weight: 500; }
        .setting-toggle-sub { font-size: 0.7em; color: var(--text-muted); margin-top: 2px; }
        .switch {
            position: relative; width: 48px; height: 26px; flex-shrink: 0;
        }
        .switch input { opacity: 0; width: 0; height: 0; }
        .switch-slider {
            position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0;
            background: var(--text-muted); border-radius: 26px; transition: 0.3s;
        }
        .switch-slider:before {
            content: ''; position: absolute; height: 20px; width: 20px;
            left: 3px; bottom: 3px; background: white; border-radius: 50%; transition: 0.3s;
        }
        .switch input:checked + .switch-slider { background: var(--green); }
        .switch input:checked + .switch-slider:before { transform: translateX(22px); }
        .modal-save-btn {
            width: 100%; padding: 14px; border: none; border-radius: 10px;
            background: linear-gradient(135deg, var(--purple), var(--blue));
            color: white; font-size: 0.95em; font-weight: 600; cursor: pointer;
            transition: opacity 0.2s, transform 0.1s; margin-top: 8px;
        }
        .modal-save-btn:hover { opacity: 0.9; }
        .modal-save-btn:active { transform: scale(0.98); }
        .modal-save-btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .setting-status {
            text-align: center; font-size: 0.8em; margin-top: 12px;
            padding: 8px; border-radius: 8px; display: none;
        }
        .setting-status.success { display: block; color: var(--green); background: var(--green-dark); }
        .setting-status.error { display: block; color: var(--red); background: var(--red-dark); }
        .key-mask { color: var(--text-muted); font-style: italic; font-size: 0.8em; }

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

        /* ===== INDICATOR TOGGLE ===== */
        .indicator-toggle {
            position: relative;
            display: inline-block;
            width: 28px;
            height: 16px;
            flex-shrink: 0;
            margin-right: 8px;
            cursor: pointer;
        }
        .indicator-toggle input { opacity: 0; width: 0; height: 0; }
        .toggle-slider {
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(255,255,255,0.08);
            border-radius: 8px;
            transition: all 0.3s ease;
        }
        .toggle-slider::before {
            content: '';
            position: absolute;
            width: 12px; height: 12px;
            left: 2px; top: 2px;
            background: var(--text-muted);
            border-radius: 50%;
            transition: all 0.3s ease;
        }
        .indicator-toggle input:checked + .toggle-slider {
            background: color-mix(in srgb, var(--toggle-color) 25%, transparent);
            box-shadow: 0 0 8px color-mix(in srgb, var(--toggle-color) 30%, transparent);
        }
        .indicator-toggle input:checked + .toggle-slider::before {
            transform: translateX(12px);
            background: var(--toggle-color);
            box-shadow: 0 0 4px var(--toggle-color);
        }

        /* ===== CHART OVERLAY LEGEND ===== */
        .chart-legend {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            padding: 6px 0 0 0;
        }
        .chart-legend-item {
            display: flex;
            align-items: center;
            gap: 4px;
            font-size: 0.7em;
            color: var(--text-secondary);
            font-family: 'JetBrains Mono', monospace;
        }
        .chart-legend-dot {
            width: 8px; height: 3px;
            border-radius: 1px;
        }

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
        /* ===== WALLET CARD ===== */
        .wallet-card { grid-column: 1 / 4; }
        .wallet-inner { display: flex; align-items: center; gap: 24px; flex-wrap: wrap; }
        .wallet-status { display: flex; align-items: center; gap: 8px; }
        .wallet-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--text-muted); }
        .wallet-dot.connected { background: var(--green); box-shadow: 0 0 8px var(--green); }
        .wallet-addr { font-family: 'JetBrains Mono', monospace; font-size: 0.8em; color: var(--text-secondary); background: rgba(255,255,255,0.04); padding: 4px 10px; border-radius: 6px; }
        .wallet-balances { display: flex; gap: 28px; flex-wrap: wrap; }
        .wallet-bal { text-align: center; }
        .wallet-bal-label { font-size: 0.65em; color: var(--text-muted); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px; }
        .wallet-bal-value { font-family: 'JetBrains Mono', monospace; font-size: 1.1em; font-weight: 700; }
        .wallet-bal-sub { font-size: 0.65em; color: var(--text-muted); margin-top: 2px; }
        .wallet-readonly { font-size: 0.65em; color: var(--text-muted); background: rgba(255,255,255,0.04); padding: 3px 8px; border-radius: 4px; margin-left: auto; }
        .wallet-allocate { margin-top: 16px; padding-top: 16px; border-top: 1px solid var(--border-color); }
        .wallet-alloc-title { font-size: 0.8em; font-weight: 700; color: var(--yellow); margin-bottom: 10px; letter-spacing: 0.5px; }
        .wallet-alloc-form { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
        .alloc-select {
            background: var(--bg-secondary); color: var(--text-primary); border: 1px solid var(--border-color);
            padding: 8px 12px; border-radius: 8px; font-size: 0.8em; font-family: 'Inter', sans-serif;
            cursor: pointer; min-width: 180px; outline: none; transition: border-color 0.3s;
        }
        .alloc-select:focus { border-color: var(--green); }
        .alloc-select option { background: var(--bg-secondary); color: var(--text-primary); }
        .alloc-amount-wrap {
            display: flex; align-items: center; background: var(--bg-secondary);
            border: 1px solid var(--border-color); border-radius: 8px; padding: 0 10px; transition: border-color 0.3s;
        }
        .alloc-amount-wrap:focus-within { border-color: var(--green); }
        .alloc-currency { color: var(--text-muted); font-size: 0.85em; font-weight: 600; }
        .alloc-input {
            background: transparent; border: none; color: var(--text-primary);
            padding: 8px 6px; font-size: 0.85em; font-family: 'JetBrains Mono', monospace;
            width: 90px; outline: none;
        }
        .alloc-input::placeholder { color: var(--text-muted); }
        .alloc-play-btn {
            display: flex; align-items: center; gap: 6px; padding: 8px 18px;
            background: linear-gradient(135deg, var(--green-dim), var(--green));
            color: #000; border: none; border-radius: 8px; font-size: 0.8em;
            font-weight: 700; cursor: pointer; transition: all 0.3s; font-family: 'Inter', sans-serif;
        }
        .alloc-play-btn:hover { transform: translateY(-1px); box-shadow: 0 4px 20px var(--green-glow); }
        .alloc-play-btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; box-shadow: none; }
        .alloc-play-btn svg { width: 14px; height: 14px; }
        .alloc-stop-btn {
            display: flex; align-items: center; gap: 6px; padding: 8px 18px;
            background: linear-gradient(135deg, var(--red-dim), var(--red));
            color: #fff; border: none; border-radius: 8px; font-size: 0.8em;
            font-weight: 700; cursor: pointer; transition: all 0.3s; font-family: 'Inter', sans-serif;
        }
        .alloc-stop-btn:hover { transform: translateY(-1px); box-shadow: 0 4px 20px var(--red-glow); }
        .wallet-alloc-active { margin-top: 12px; display: flex; flex-direction: column; gap: 6px; }
        .alloc-active-item {
            display: flex; align-items: center; justify-content: space-between; gap: 10px;
            background: rgba(0,255,136,0.05); border: 1px solid rgba(0,255,136,0.12);
            border-radius: 8px; padding: 8px 12px; font-size: 0.78em;
        }
        .alloc-active-item .alloc-strat-name { font-weight: 600; color: var(--green); }
        .alloc-active-item .alloc-strat-amount { font-family: 'JetBrains Mono', monospace; color: var(--yellow); }
        .alloc-active-item .alloc-strat-status { font-size: 0.85em; color: var(--text-muted); }
        .wallet-alloc-warning { margin-top: 8px; font-size: 0.65em; color: var(--red-dim); opacity: 0.7; }
        /* ===== STRATEGY PANELS ===== */
        .strategies-section { grid-column: 1 / 4; }
        .strategies-title-row { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; }
        .strategies-title { font-size: 1.1em; font-weight: 700; letter-spacing: -0.3px; }
        .strategies-subtitle { font-size: 0.75em; color: var(--text-muted); padding: 4px 10px; background: rgba(255,170,0,0.08); border: 1px solid rgba(255,170,0,0.15); border-radius: 6px; color: var(--yellow); font-weight: 600; letter-spacing: 0.5px; }
        .strategies-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 14px; }
        .strat-card { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 16px; padding: 20px; position: relative; transition: all 0.4s ease; }
        .strat-card::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px; border-radius: 16px 16px 0 0; transition: opacity 0.3s; }
        .strat-card.risk-alto::before { background: linear-gradient(90deg, var(--red), var(--yellow)); }
        .strat-card.risk-muito-alto::before { background: linear-gradient(90deg, #ff0044, var(--red)); }
        .strat-card.risk-medio::before { background: linear-gradient(90deg, var(--yellow), var(--blue)); }
        .strat-card.risk-medio-baixo::before { background: linear-gradient(90deg, var(--blue), var(--green)); }
        .strat-card:hover { background: var(--bg-card-hover); border-color: var(--border-glow); transform: translateY(-4px); box-shadow: 0 12px 40px rgba(0,0,0,0.4); }
        .strat-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 14px; }
        .strat-name { font-size: 0.8em; font-weight: 700; letter-spacing: -0.2px; line-height: 1.3; max-width: 80%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .strat-help { width: 22px; height: 22px; border-radius: 50%; background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.1); display: flex; align-items: center; justify-content: center; font-size: 0.72em; font-weight: 700; color: var(--text-muted); cursor: help; transition: all 0.3s; flex-shrink: 0; }
        .strat-help:hover { background: rgba(0,255,136,0.15); border-color: var(--green); color: var(--green); }
        .strat-tooltip { display: none; position: fixed; z-index: 9999; width: 300px; max-width: 90vw; padding: 16px; border-radius: 12px; background: #1a1a2e; border: 1px solid rgba(255,255,255,0.12); box-shadow: 0 16px 48px rgba(0,0,0,0.8); font-weight: 400; font-size: 13px; line-height: 1.6; color: var(--text-secondary); }
        .strat-tooltip.visible { display: block; }
        .strat-tooltip-title { font-weight: 700; color: var(--text-primary); margin-bottom: 8px; font-size: 1em; }
        .strat-tooltip-tools { margin-top: 8px; padding-top: 8px; border-top: 1px solid rgba(255,255,255,0.06); font-size: 0.9em; color: var(--text-muted); }
        .strat-tooltip-tools span { color: var(--blue); font-weight: 500; }
        .strat-badges { display: flex; gap: 4px; flex-wrap: wrap; margin-bottom: 10px; }
        .strat-badge { padding: 3px 8px; border-radius: 5px; font-size: 0.6em; font-weight: 700; letter-spacing: 0.5px; text-transform: uppercase; }
        .strat-badge.risk-high { background: rgba(255,68,102,0.12); color: var(--red); }
        .strat-badge.risk-vhigh { background: rgba(255,0,68,0.15); color: #ff3366; }
        .strat-badge.risk-med { background: rgba(255,170,0,0.12); color: var(--yellow); }
        .strat-badge.risk-low { background: rgba(0,255,136,0.12); color: var(--green); }
        .strat-badge.return-badge { background: rgba(68,136,255,0.12); color: var(--blue); }
        .strat-badge.time-badge { background: rgba(170,102,255,0.10); color: var(--purple); }
        .strat-stats { display: flex; flex-direction: column; gap: 8px; }
        .strat-stat-row { display: flex; justify-content: space-between; align-items: center; }
        .strat-stat-label { font-size: 0.68em; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; }
        .strat-stat-value { font-family: 'JetBrains Mono', monospace; font-size: 0.82em; font-weight: 600; }
        .strat-pnl { font-size: 1.2em; font-weight: 800; font-family: 'JetBrains Mono', monospace; margin: 8px 0 6px 0; letter-spacing: -0.5px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .strat-pnl.profit { color: var(--green); text-shadow: 0 0 15px var(--green-glow); }
        .strat-pnl.loss { color: var(--red); text-shadow: 0 0 15px var(--red-glow); }
        .strat-pnl.neutral { color: var(--text-muted); }
        .strat-winrate-bar { width: 100%; height: 4px; background: rgba(255,255,255,0.05); border-radius: 2px; overflow: hidden; margin-top: 4px; }
        .strat-winrate-fill { height: 100%; border-radius: 2px; transition: width 1s ease; }
        .strat-recent { margin-top: 12px; padding-top: 10px; border-top: 1px solid var(--border-color); max-height: 0; overflow: hidden; transition: max-height 0.4s ease; }
        .strat-card:hover .strat-recent { max-height: 200px; }
        .strat-toggle-btn { width: 100%; margin-top: 12px; padding: 8px 0; border: 1px solid var(--border-color); border-radius: 8px; background: rgba(255,255,255,0.03); color: var(--text-secondary); font-size: 0.75em; font-weight: 600; letter-spacing: 0.5px; cursor: pointer; transition: all 0.3s; text-transform: uppercase; }
        .strat-toggle-btn:hover { background: rgba(255,255,255,0.08); border-color: var(--border-glow); }
        .strat-toggle-btn.running { color: var(--red); border-color: rgba(255,68,102,0.3); }
        .strat-toggle-btn.running:hover { background: rgba(255,68,102,0.1); }
        .strat-toggle-btn.paused { color: var(--green); border-color: rgba(0,255,136,0.3); }
        .strat-toggle-btn.paused:hover { background: rgba(0,255,136,0.1); }
        .strat-card.is-paused { opacity: 0.5; }
        .strat-card.is-paused .strat-pnl { color: var(--text-muted) !important; }
        .strat-paused-badge { display: none; font-size: 0.6em; color: var(--red); background: rgba(255,68,102,0.1); border: 1px solid rgba(255,68,102,0.2); padding: 2px 8px; border-radius: 4px; font-weight: 600; letter-spacing: 0.5px; margin-left: auto; }
        .strat-card.is-paused .strat-paused-badge { display: inline-block; }
        .strat-card.real-mode { border-color: rgba(0,255,136,0.2); }
        .strat-card.real-mode::before { background: linear-gradient(90deg, var(--green), var(--blue)) !important; }
        .real-mode-badge { font-size: 0.6em; color: var(--green); background: rgba(0,255,136,0.1); border: 1px solid rgba(0,255,136,0.2); padding: 2px 8px; border-radius: 4px; font-weight: 600; letter-spacing: 0.5px; }
        .real-coin-badge { font-size: 0.6em; color: var(--yellow); background: rgba(255,170,0,0.1); border: 1px solid rgba(255,170,0,0.2); padding: 2px 8px; border-radius: 4px; font-weight: 600; letter-spacing: 0.5px; }
        .real-pnl-row { display: flex; justify-content: space-between; align-items: center; margin: 6px 0; }
        .real-pnl-label { font-size: 0.7em; color: var(--text-muted); }
        .real-pnl-value { font-family: 'JetBrains Mono', monospace; font-size: 0.85em; font-weight: 700; }
        .strat-recent-title { font-size: 0.65em; color: var(--text-muted); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px; }
        .strat-recent-item { display: flex; justify-content: space-between; align-items: center; padding: 3px 0; font-size: 0.72em; font-family: 'JetBrains Mono', monospace; }
        .strat-recent-name { color: var(--text-secondary); }
        .strat-recent-pnl { font-weight: 600; }
        .strat-capital { display: grid; grid-template-columns: 1fr 1fr; gap: 4px 8px; margin: 10px 0; padding: 8px 10px; background: rgba(255,255,255,0.05); border-radius: 8px; border: 1px solid var(--border-color); overflow: hidden; }
        .strat-cap-item { display: flex; flex-direction: column; gap: 1px; min-width: 0; }
        .strat-cap-label { font-size: 0.6em; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.5px; }
        .strat-cap-value { font-family: 'JetBrains Mono', monospace; font-size: 0.75em; font-weight: 700; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .strat-cap-full { grid-column: 1 / 3; border-top: 1px solid var(--border-color); padding-top: 4px; margin-top: 2px; }

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
            .wallet-card, .strategies-section { grid-column: 1 / 3; }
        }
        @media (max-width: 768px) {
            .main {
                grid-template-columns: 1fr;
                padding: 12px;
            }
            .chart-card, .indicators-card, .signals-card,
            .positions-card, .log-card,
            .price-card, .pnl-card, .status-card { grid-column: 1 / 2; }
            .wallet-card, .strategies-section { grid-column: 1 / 2; }
            .wallet-inner { gap: 12px; }
            .wallet-balances { gap: 16px; }
            .alloc-select { min-width: 140px; }
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
            <button class="settings-btn" onclick="openSettings()" title="Configuracoes">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/></svg>
            </button>
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
            <div class="chart-legend" id="chart-legend"></div>
        </div>

        <div class="card indicators-card">
            <div class="card-label">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20V10M18 20V4M6 20v-4"/></svg>
                Indicadores
            </div>
            <div id="indicators-list">
                <div class="indicator-row" id="ind-rsi">
                    <label class="indicator-toggle">
                        <input type="checkbox" id="chk-rsi" onchange="toggleIndicatorOverlay('rsi')" />
                        <span class="toggle-slider" style="--toggle-color:#ffaa00"></span>
                    </label>
                    <div style="flex:1;min-width:0">
                        <div class="indicator-name"><span class="indicator-dot neutral"></span> RSI</div>
                        <div class="indicator-bar"><div class="indicator-bar-fill neutral" style="width:50%"></div></div>
                    </div>
                    <div class="indicator-value">--</div>
                </div>
                <div class="indicator-row" id="ind-ema">
                    <label class="indicator-toggle">
                        <input type="checkbox" id="chk-ema" onchange="toggleIndicatorOverlay('ema')" />
                        <span class="toggle-slider" style="--toggle-color:#00aaff"></span>
                    </label>
                    <div style="flex:1;min-width:0">
                        <div class="indicator-name"><span class="indicator-dot neutral"></span> EMA</div>
                        <div class="indicator-bar"><div class="indicator-bar-fill neutral" style="width:50%"></div></div>
                    </div>
                    <div class="indicator-value">--</div>
                </div>
                <div class="indicator-row" id="ind-ichimoku">
                    <label class="indicator-toggle">
                        <input type="checkbox" id="chk-ichimoku" onchange="toggleIndicatorOverlay('ichimoku')" />
                        <span class="toggle-slider" style="--toggle-color:#ff66ff"></span>
                    </label>
                    <div style="flex:1;min-width:0">
                        <div class="indicator-name"><span class="indicator-dot neutral"></span> Ichimoku</div>
                        <div class="indicator-bar"><div class="indicator-bar-fill neutral" style="width:50%"></div></div>
                    </div>
                    <div class="indicator-value">--</div>
                </div>
                <div class="indicator-row" id="ind-volume">
                    <label class="indicator-toggle">
                        <input type="checkbox" id="chk-volume" onchange="toggleIndicatorOverlay('volume')" />
                        <span class="toggle-slider" style="--toggle-color:#66ffcc"></span>
                    </label>
                    <div style="flex:1;min-width:0">
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

        <!-- ===== CARTEIRA PHANTOM ===== -->
        <div class="card wallet-card" id="wallet-card" style="display:none">
            <div class="card-label"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="6" width="20" height="12" rx="2"/><circle cx="16" cy="12" r="2"/><path d="M2 10h4"/></svg> Carteira Phantom</div>
            <div class="wallet-inner">
                <div class="wallet-status"><div class="wallet-dot" id="wallet-dot"></div><span class="wallet-addr" id="wallet-addr">----...----</span></div>
                <div class="wallet-balances">
                    <div class="wallet-bal"><div class="wallet-bal-label">SOL</div><div class="wallet-bal-value" id="wallet-sol" style="color:var(--purple)">0.0000</div><div class="wallet-bal-sub" id="wallet-sol-usd">~$0.00</div></div>
                    <div class="wallet-bal"><div class="wallet-bal-label">USDC</div><div class="wallet-bal-value" id="wallet-usdc" style="color:var(--green)">$0.00</div></div>
                    <div class="wallet-bal"><div class="wallet-bal-label">Total</div><div class="wallet-bal-value" id="wallet-total" style="color:var(--yellow)">$0.00</div></div>
                </div>
            </div>
            <div class="wallet-allocate" id="wallet-allocate">
                <div class="wallet-alloc-title">Alocar Capital Real</div>
                <div class="wallet-alloc-form">
                    <select id="alloc-strategy" class="alloc-select">
                        <option value="">Estrategia...</option>
                        <option value="sniper">Sniping Pump.fun</option>
                        <option value="memecoin">Meme Coins</option>
                        <option value="arbitrage">Arbitragem DEX</option>
                        <option value="scalping">Scalping Tokens</option>
                        <option value="leverage">Leverage Trading</option>
                    </select>
                    <select id="alloc-coin" class="alloc-select" style="min-width:120px">
                        <option value="SOL">SOL</option>
                        <option value="USDC">USDC</option>
                        <option value="USDT">USDT</option>
                        <option value="JUP">JUP</option>
                        <option value="BONK">BONK</option>
                        <option value="WBTC">WBTC</option>
                    </select>
                    <div class="alloc-amount-wrap">
                        <span class="alloc-currency">$</span>
                        <input type="number" id="alloc-amount" class="alloc-input" placeholder="0.00" min="0.01" step="0.01"/>
                    </div>
                    <button class="alloc-play-btn" id="alloc-play-btn" onclick="allocateStrategy()">
                        <svg viewBox="0 0 24 24" fill="currentColor" width="16" height="16"><polygon points="5,3 19,12 5,21"/></svg>
                        Play
                    </button>
                </div>
                <div class="wallet-alloc-active" id="alloc-active-list"></div>
                <div class="wallet-alloc-warning">Trades reais via Jupiter DEX. Risco de perda.</div>
            </div>
        </div>
        <!-- ===== 5 ESTRATEGIAS DE DAY TRADE ===== -->
        <div class="strategies-section">
            <div class="strategies-title-row">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:20px;height:20px;color:var(--yellow)"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>
                <span class="strategies-title">Estrategias de Day Trade</span>
                <span class="strategies-subtitle">MODO TESTE</span>
            </div>
            <div class="strategies-grid">
                <div class="strat-card risk-alto" id="strat-sniper">
                    <div class="strat-header"><div class="strat-name">Sniping Pump.fun</div><span class="strat-paused-badge">PAUSADO</span><div class="strat-help">?<div class="strat-tooltip"><div class="strat-tooltip-title">Sniping de Novos Tokens</div>Usa bots automatizados para detectar e comprar tokens no momento exato do lancamento no Pump.fun, antes que aparecam para usuarios comuns (vantagem de 0.01s vs 60s). Opera em velocidade ultra-rapida (segundos).<div class="strat-tooltip-tools">Ferramentas: <span>Solana Sniper Bot, MEV Bots</span></div></div></div></div>
                    <div class="strat-badges"><span class="strat-badge risk-high">Risco Alto</span><span class="strat-badge return-badge">Retorno Muito Alto</span><span class="strat-badge time-badge">Segundos</span></div>
                    <div class="strat-pnl neutral" id="strat-sniper-pnl">$0.00</div>
                    <div class="strat-capital"><div class="strat-cap-item"><span class="strat-cap-label">Capital</span><span class="strat-cap-value" id="strat-sniper-cap" style="color:var(--yellow)">$100.00</span></div><div class="strat-cap-item"><span class="strat-cap-label">Investido</span><span class="strat-cap-value" id="strat-sniper-inv">$0.00</span></div><div class="strat-cap-item"><span class="strat-cap-label">Ganhos</span><span class="strat-cap-value" id="strat-sniper-gain" style="color:var(--green)">$0.00</span></div><div class="strat-cap-item"><span class="strat-cap-label">Perdas</span><span class="strat-cap-value" id="strat-sniper-loss" style="color:var(--red)">$0.00</span></div><div class="strat-cap-item strat-cap-full"><span class="strat-cap-label">Hoje</span><span class="strat-cap-value" id="strat-sniper-today">$0.00</span></div></div>
                    <div class="strat-stats"><div class="strat-stat-row"><span class="strat-stat-label">Snipes</span><span class="strat-stat-value" id="strat-sniper-trades">0</span></div><div class="strat-stat-row"><span class="strat-stat-label">Win Rate</span><span class="strat-stat-value" id="strat-sniper-wr">0%</span></div><div class="strat-winrate-bar"><div class="strat-winrate-fill" id="strat-sniper-wrbar" style="width:0%;background:var(--red)"></div></div><div class="strat-stat-row"><span class="strat-stat-label">Rugged</span><span class="strat-stat-value" id="strat-sniper-rug" style="color:var(--red)">0</span></div></div>
                    <div class="strat-recent"><div class="strat-recent-title">Ultimos Snipes</div><div id="strat-sniper-recent"></div></div>
                    <button class="strat-toggle-btn running" id="strat-sniper-btn" onclick="toggleStrategy('sniper')">Parar</button>
                </div>
                <div class="strat-card risk-alto" id="strat-memecoin">
                    <div class="strat-header"><div class="strat-name">Meme Coins Liquidez</div><span class="strat-paused-badge">PAUSADO</span><div class="strat-help">?<div class="strat-tooltip"><div class="strat-tooltip-title">Trading de Meme Coins</div>Identifica meme coins da Solana com liquidez real, volume crescente e tempo de mercado. Foca em entradas e saidas rapidas baseadas em momentum e analise on-chain.<div class="strat-tooltip-tools">Ferramentas: <span>DexScreener, Birdeye, Jupiter</span></div></div></div></div>
                    <div class="strat-badges"><span class="strat-badge risk-high">Risco Alto</span><span class="strat-badge return-badge">Retorno Alto</span><span class="strat-badge time-badge">Min a Horas</span></div>
                    <div class="strat-pnl neutral" id="strat-meme-pnl">$0.00</div>
                    <div class="strat-capital"><div class="strat-cap-item"><span class="strat-cap-label">Capital</span><span class="strat-cap-value" id="strat-meme-cap" style="color:var(--yellow)">$100.00</span></div><div class="strat-cap-item"><span class="strat-cap-label">Investido</span><span class="strat-cap-value" id="strat-meme-inv">$0.00</span></div><div class="strat-cap-item"><span class="strat-cap-label">Ganhos</span><span class="strat-cap-value" id="strat-meme-gain" style="color:var(--green)">$0.00</span></div><div class="strat-cap-item"><span class="strat-cap-label">Perdas</span><span class="strat-cap-value" id="strat-meme-loss" style="color:var(--red)">$0.00</span></div><div class="strat-cap-item strat-cap-full"><span class="strat-cap-label">Hoje</span><span class="strat-cap-value" id="strat-meme-today">$0.00</span></div></div>
                    <div class="strat-stats"><div class="strat-stat-row"><span class="strat-stat-label">Trades</span><span class="strat-stat-value" id="strat-meme-trades">0</span></div><div class="strat-stat-row"><span class="strat-stat-label">Win Rate</span><span class="strat-stat-value" id="strat-meme-wr">0%</span></div><div class="strat-winrate-bar"><div class="strat-winrate-fill" id="strat-meme-wrbar" style="width:0%;background:var(--red)"></div></div><div class="strat-stat-row"><span class="strat-stat-label">Momentum</span><span class="strat-stat-value" id="strat-meme-momentum" style="color:var(--blue)">0</span></div></div>
                    <div class="strat-recent"><div class="strat-recent-title">Ultimos Sinais</div><div id="strat-meme-recent"></div></div>
                    <button class="strat-toggle-btn running" id="strat-meme-btn" onclick="toggleStrategy('memecoin')">Parar</button>
                </div>
                <div class="strat-card risk-medio" id="strat-arbitrage">
                    <div class="strat-header"><div class="strat-name">Arbitragem DEX</div><span class="strat-paused-badge">PAUSADO</span><div class="strat-help">?<div class="strat-tooltip"><div class="strat-tooltip-title">Arbitragem entre DEXs</div>Explora diferencas de preco do mesmo token entre Raydium, Jupiter, Meteora e Orca. Executa compra/venda simultanea via bots customizados para lucro sem risco direcional.<div class="strat-tooltip-tools">Ferramentas: <span>Python/Rust Bots, APIs DEX, Jito MEV</span></div></div></div></div>
                    <div class="strat-badges"><span class="strat-badge risk-med">Risco Medio</span><span class="strat-badge return-badge">Consistente</span><span class="strat-badge time-badge">Milissegundos</span></div>
                    <div class="strat-pnl neutral" id="strat-arb-pnl">$0.00</div>
                    <div class="strat-capital"><div class="strat-cap-item"><span class="strat-cap-label">Capital</span><span class="strat-cap-value" id="strat-arb-cap" style="color:var(--yellow)">$100.00</span></div><div class="strat-cap-item"><span class="strat-cap-label">Investido</span><span class="strat-cap-value" id="strat-arb-inv">$0.00</span></div><div class="strat-cap-item"><span class="strat-cap-label">Ganhos</span><span class="strat-cap-value" id="strat-arb-gain" style="color:var(--green)">$0.00</span></div><div class="strat-cap-item"><span class="strat-cap-label">Perdas</span><span class="strat-cap-value" id="strat-arb-loss" style="color:var(--red)">$0.00</span></div><div class="strat-cap-item strat-cap-full"><span class="strat-cap-label">Hoje</span><span class="strat-cap-value" id="strat-arb-today">$0.00</span></div></div>
                    <div class="strat-stats"><div class="strat-stat-row"><span class="strat-stat-label">Executados</span><span class="strat-stat-value" id="strat-arb-trades">0</span></div><div class="strat-stat-row"><span class="strat-stat-label">Avg Spread</span><span class="strat-stat-value" id="strat-arb-spread">0%</span></div><div class="strat-winrate-bar"><div class="strat-winrate-fill" id="strat-arb-wrbar" style="width:0%;background:var(--blue)"></div></div><div class="strat-stat-row"><span class="strat-stat-label">$/hora</span><span class="strat-stat-value" id="strat-arb-perhr" style="color:var(--green)">$0.00</span></div></div>
                    <div class="strat-recent"><div class="strat-recent-title">Ultimas Oportunidades</div><div id="strat-arb-recent"></div></div>
                    <button class="strat-toggle-btn running" id="strat-arb-btn" onclick="toggleStrategy('arbitrage')">Parar</button>
                </div>
                <div class="strat-card risk-medio-baixo" id="strat-scalping">
                    <div class="strat-header"><div class="strat-name">Scalping Tokens</div><span class="strat-paused-badge">PAUSADO</span><div class="strat-help">?<div class="strat-tooltip"><div class="strat-tooltip-title">Scalping em Tokens Estabelecidos</div>Multiplas operacoes rapidas (1-5 min) em tokens com boa liquidez (SOL, JUP, BONK, WIF). Aproveita micro-movimentos de preco com stop-loss rigido. Foco em consistencia.<div class="strat-tooltip-tools">Ferramentas: <span>Jupiter Router, Graficos 1m/5m</span></div></div></div></div>
                    <div class="strat-badges"><span class="strat-badge risk-low">Risco Medio-Baixo</span><span class="strat-badge return-badge">Consistente</span><span class="strat-badge time-badge">1-5 min</span></div>
                    <div class="strat-pnl neutral" id="strat-scalp-pnl">$0.00</div>
                    <div class="strat-capital"><div class="strat-cap-item"><span class="strat-cap-label">Capital</span><span class="strat-cap-value" id="strat-scalp-cap" style="color:var(--yellow)">$100.00</span></div><div class="strat-cap-item"><span class="strat-cap-label">Investido</span><span class="strat-cap-value" id="strat-scalp-inv">$0.00</span></div><div class="strat-cap-item"><span class="strat-cap-label">Ganhos</span><span class="strat-cap-value" id="strat-scalp-gain" style="color:var(--green)">$0.00</span></div><div class="strat-cap-item"><span class="strat-cap-label">Perdas</span><span class="strat-cap-value" id="strat-scalp-loss" style="color:var(--red)">$0.00</span></div><div class="strat-cap-item strat-cap-full"><span class="strat-cap-label">Hoje</span><span class="strat-cap-value" id="strat-scalp-today">$0.00</span></div></div>
                    <div class="strat-stats"><div class="strat-stat-row"><span class="strat-stat-label">Trades</span><span class="strat-stat-value" id="strat-scalp-trades">0</span></div><div class="strat-stat-row"><span class="strat-stat-label">Win Rate</span><span class="strat-stat-value" id="strat-scalp-wr">0%</span></div><div class="strat-winrate-bar"><div class="strat-winrate-fill" id="strat-scalp-wrbar" style="width:0%;background:var(--green)"></div></div><div class="strat-stat-row"><span class="strat-stat-label">Sharpe</span><span class="strat-stat-value" id="strat-scalp-sharpe" style="color:var(--purple)">0.0</span></div></div>
                    <div class="strat-recent"><div class="strat-recent-title">Ultimos Trades</div><div id="strat-scalp-recent"></div></div>
                    <button class="strat-toggle-btn running" id="strat-scalp-btn" onclick="toggleStrategy('scalping')">Parar</button>
                </div>
                <div class="strat-card risk-muito-alto" id="strat-leverage">
                    <div class="strat-header"><div class="strat-name">Leverage Trading</div><span class="strat-paused-badge">PAUSADO</span><div class="strat-help">?<div class="strat-tooltip"><div class="strat-tooltip-title">Leverage Trading em DEX</div>Usa Jupiter Perpetuals e Drift Protocol para operar com alavancagem (2x-20x) em SOL e tokens principais. Multiplica exposicao - risco muito alto de liquidacao.<div class="strat-tooltip-tools">Ferramentas: <span>Jupiter Perps, Drift, Mango</span></div></div></div></div>
                    <div class="strat-badges"><span class="strat-badge risk-vhigh">Risco Muito Alto</span><span class="strat-badge return-badge">Retorno Muito Alto</span><span class="strat-badge time-badge">Horas a Dias</span></div>
                    <div class="strat-pnl neutral" id="strat-lev-pnl">$0.00</div>
                    <div class="strat-capital"><div class="strat-cap-item"><span class="strat-cap-label">Capital</span><span class="strat-cap-value" id="strat-lev-cap" style="color:var(--yellow)">$100.00</span></div><div class="strat-cap-item"><span class="strat-cap-label">Investido</span><span class="strat-cap-value" id="strat-lev-inv">$0.00</span></div><div class="strat-cap-item"><span class="strat-cap-label">Ganhos</span><span class="strat-cap-value" id="strat-lev-gain" style="color:var(--green)">$0.00</span></div><div class="strat-cap-item"><span class="strat-cap-label">Perdas</span><span class="strat-cap-value" id="strat-lev-loss" style="color:var(--red)">$0.00</span></div><div class="strat-cap-item strat-cap-full"><span class="strat-cap-label">Hoje</span><span class="strat-cap-value" id="strat-lev-today">$0.00</span></div></div>
                    <div class="strat-stats"><div class="strat-stat-row"><span class="strat-stat-label">Trades</span><span class="strat-stat-value" id="strat-lev-trades">0</span></div><div class="strat-stat-row"><span class="strat-stat-label">Win Rate</span><span class="strat-stat-value" id="strat-lev-wr">0%</span></div><div class="strat-winrate-bar"><div class="strat-winrate-fill" id="strat-lev-wrbar" style="width:0%;background:var(--red)"></div></div><div class="strat-stat-row"><span class="strat-stat-label">Liquidacoes</span><span class="strat-stat-value" id="strat-lev-liq" style="color:var(--red)">0</span></div></div>
                    <div class="strat-recent"><div class="strat-recent-title">Ultimas Posicoes</div><div id="strat-lev-recent"></div></div>
                    <button class="strat-toggle-btn running" id="strat-lev-btn" onclick="toggleStrategy('leverage')">Parar</button>
                </div>
            </div>
        </div>

        <!-- ===== MODO REAL ===== -->
        <div class="strategies-section" id="real-mode-section" style="display:none">
            <div class="strategies-title-row">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:20px;height:20px;color:var(--green)"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>
                <span class="strategies-title">Estrategias de Day Trade</span>
                <span class="strategies-subtitle" style="background:rgba(0,255,136,0.08);border-color:rgba(0,255,136,0.15);color:var(--green)">MODO REAL</span>
            </div>
            <div class="strategies-grid" id="real-strategies-grid">
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
    <!-- Settings Modal -->
    <div class="modal-overlay" id="settings-modal">
        <div class="modal-box">
            <div class="modal-header">
                <h2><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/></svg> Configuracoes</h2>
                <button class="modal-close" onclick="closeSettings()">&times;</button>
            </div>
            <div class="setting-group">
                <div class="setting-label">Chave Privada (Phantom Wallet)</div>
                <div class="setting-desc">Base58 private key para executar trades reais. A chave fica salva no servidor e nunca e exposta.</div>
                <div class="setting-input-wrap">
                    <input type="password" id="setting-pk" placeholder="Cole sua private key aqui..." autocomplete="off" spellcheck="false">
                    <button class="toggle-pw-btn" onclick="togglePkVisibility()" title="Mostrar/Esconder">
                        <svg id="eye-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                    </button>
                </div>
                <div id="pk-current" class="key-mask" style="margin-top:6px;"></div>
            </div>
            <div class="setting-group">
                <div class="setting-label">Modo de Operacao</div>
                <div class="setting-toggle">
                    <div>
                        <div class="setting-toggle-label" id="mode-toggle-label">Paper Trading (Simulado)</div>
                        <div class="setting-toggle-sub" id="mode-toggle-sub">Nenhum dinheiro real sera usado</div>
                    </div>
                    <label class="switch">
                        <input type="checkbox" id="setting-live-mode" onchange="updateModeLabel()">
                        <span class="switch-slider"></span>
                    </label>
                </div>
            </div>
            <button class="modal-save-btn" id="settings-save-btn" onclick="saveSettings()">Salvar Configuracoes</button>
            <div class="setting-status" id="settings-status"></div>
        </div>
    </div>
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

// Indicator overlays
const indicatorOverlays = {
    rsi:      { enabled: false, color: '#ffaa00', label: 'RSI',      history: [], min: 0, max: 100 },
    ema:      { enabled: false, color: '#00aaff', label: 'EMA',      history: [], min: -1, max: 1 },
    ichimoku: { enabled: false, color: '#ff66ff', label: 'Ichimoku', history: [], min: -1, max: 1 },
    volume:   { enabled: false, color: '#66ffcc', label: 'Volume',   history: [], min: 0, max: 3 }
};

function toggleIndicatorOverlay(id) {
    indicatorOverlays[id].enabled = document.getElementById('chk-' + id).checked;
    updateChartLegend();
    drawChart();
}

function updateChartLegend() {
    const legend = document.getElementById('chart-legend');
    let html = '';
    for (const [id, ind] of Object.entries(indicatorOverlays)) {
        if (ind.enabled) {
            html += '<div class="chart-legend-item"><span class="chart-legend-dot" style="background:' + ind.color + '"></span>' + ind.label + '</div>';
        }
    }
    legend.innerHTML = html;
}

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
    if (!data || data.error) return;

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
    currentPaperMode=!!data.paper_trading;
    if(data.pk_mask)currentPkMask=data.pk_mask;

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

        // Store indicator history for chart overlay
        const indMap = { rsi: 'RSI', ema: 'EMA', ichimoku: 'Ichimoku', volume: 'Volume' };
        for (const [key, dataKey] of Object.entries(indMap)) {
            const val = data.indicators[dataKey];
            if (val !== undefined && val !== null) {
                indicatorOverlays[key].history.push({ time: new Date(), value: val });
                if (indicatorOverlays[key].history.length > 500) {
                    indicatorOverlays[key].history = indicatorOverlays[key].history.slice(-500);
                }
            }
        }
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

    // Wallet
    if(data.wallet&&data.wallet.connected){
        const wc=document.getElementById('wallet-card');wc.style.display='';
        const wd=document.getElementById('wallet-dot');wd.className='wallet-dot connected';
        document.getElementById('wallet-addr').textContent=data.wallet.address_short||'';
        const sol=data.wallet.sol_balance||0;const usdc=data.wallet.usdc_balance||0;
        document.getElementById('wallet-sol').textContent=sol.toFixed(4);
        const solUsd=sol*(data.price||0);
        document.getElementById('wallet-sol-usd').textContent='~$'+solUsd.toFixed(2);
        document.getElementById('wallet-usdc').textContent='$'+usdc.toFixed(2);
        document.getElementById('wallet-total').textContent='$'+(solUsd+usdc).toFixed(2);
    }
    if(data.allocations){updateAllocationsFromData(data.allocations);}

    // Strategies
    if(data.strategies){updateStrategies(data.strategies);}
}

// ============================================================
// STRATEGY PANELS UPDATE
// ============================================================
function updateStrategies(strats){
    if(!strats)return;
    function setCap(prefix,cap){if(!cap)return;setText(prefix+'-cap','$'+(cap.current||0).toFixed(2));setText(prefix+'-inv','$'+(cap.total_invested||0).toFixed(2));setText(prefix+'-gain','$'+(cap.total_gains||0).toFixed(2));setText(prefix+'-loss','$'+(cap.total_losses||0).toFixed(2));var te=document.getElementById(prefix+'-today');if(te){var tp=cap.today_pnl||0;te.textContent=(tp>=0?'+$':'-$')+Math.abs(tp).toFixed(2);te.style.color=tp>=0?'var(--green)':'var(--red)';}}
    function setPaused(cardId,btnId,paused){const card=document.getElementById(cardId);const btn=document.getElementById(btnId);if(card){if(paused){card.classList.add('is-paused');}else{card.classList.remove('is-paused');}}if(btn){btn.textContent=paused?'Continuar':'Parar';btn.className='strat-toggle-btn '+(paused?'paused':'running');}}
    if(strats.sniper){const s=strats.sniper.stats||{},c=strats.sniper.capital||{};setPnl('strat-sniper-pnl',c.pnl_usd||0,false);setCap('strat-sniper',c);setText('strat-sniper-trades',s.total_snipes||0);setText('strat-sniper-wr',(s.win_rate||0).toFixed(0)+'%');setBar('strat-sniper-wrbar',s.win_rate||0);setText('strat-sniper-rug',s.rugged||0);setRecent('strat-sniper-recent',(strats.sniper.recent_targets||[]).slice(0,4),t=>`<div class="strat-recent-item"><span class="strat-recent-name">${t.name}</span><span class="strat-recent-pnl" style="color:${t.pnl_pct>=0?'var(--green)':'var(--red)'}">${t.pnl_pct>=0?'+':''}${t.pnl_pct}%</span></div>`);}
    if(strats.memecoin){const s=strats.memecoin.stats||{},c=strats.memecoin.capital||{};setPnl('strat-meme-pnl',c.pnl_usd||0,false);setCap('strat-meme',c);setText('strat-meme-trades',s.total_trades||0);setText('strat-meme-wr',(s.win_rate||0).toFixed(0)+'%');setBar('strat-meme-wrbar',s.win_rate||0);setText('strat-meme-momentum',s.high_momentum_count||0);setRecent('strat-meme-recent',(strats.memecoin.recent_signals||[]).slice(0,4),t=>`<div class="strat-recent-item"><span class="strat-recent-name">${t.name}</span><span class="strat-recent-pnl" style="color:${t.pnl_pct>=0?'var(--green)':'var(--red)'}">${t.pnl_pct>=0?'+':''}${t.pnl_pct}%</span></div>`);}
    if(strats.arbitrage){const s=strats.arbitrage.stats||{},c=strats.arbitrage.capital||{};setPnl('strat-arb-pnl',c.pnl_usd||0,false);setCap('strat-arb',c);setText('strat-arb-trades',s.executed||0);setText('strat-arb-spread',(s.avg_spread_pct||0).toFixed(3)+'%');setBar('strat-arb-wrbar',s.executed>0?((s.executed/(s.executed+s.failed+s.missed||1))*100):0);setText('strat-arb-perhr','$'+(s.profit_per_hour||0).toFixed(2));setRecent('strat-arb-recent',(strats.arbitrage.recent_opportunities||[]).slice(0,4),t=>`<div class="strat-recent-item"><span class="strat-recent-name">${t.token} ${t.buy_dex}>${t.sell_dex}</span><span class="strat-recent-pnl" style="color:${t.profit>=0?'var(--green)':'var(--red)'}">$${t.profit.toFixed(3)}</span></div>`);}
    if(strats.scalping){const s=strats.scalping.stats||{},c=strats.scalping.capital||{};setPnl('strat-scalp-pnl',c.pnl_usd||0,false);setCap('strat-scalp',c);setText('strat-scalp-trades',s.total_trades||0);setText('strat-scalp-wr',(s.win_rate||0).toFixed(0)+'%');setBar('strat-scalp-wrbar',s.win_rate||0);setText('strat-scalp-sharpe',(s.sharpe_estimate||0).toFixed(1));setRecent('strat-scalp-recent',(strats.scalping.recent_trades||[]).slice(0,4),t=>`<div class="strat-recent-item"><span class="strat-recent-name">${t.token} ${t.direction}</span><span class="strat-recent-pnl" style="color:${t.pnl_pct>=0?'var(--green)':'var(--red)'}">${t.pnl_pct>=0?'+':''}${t.pnl_pct.toFixed(2)}%</span></div>`);}
    if(strats.leverage){const s=strats.leverage.stats||{},c=strats.leverage.capital||{};setPnl('strat-lev-pnl',c.pnl_usd||0,false);setCap('strat-lev',c);setText('strat-lev-trades',s.total_trades||0);setText('strat-lev-wr',(s.win_rate||0).toFixed(0)+'%');setBar('strat-lev-wrbar',s.win_rate||0);setText('strat-lev-liq',s.liquidations||0);setRecent('strat-lev-recent',(strats.leverage.recent_positions||[]).slice(0,4),t=>`<div class="strat-recent-item"><span class="strat-recent-name">${t.token} ${t.direction} ${t.leverage}</span><span class="strat-recent-pnl" style="color:${t.pnl_pct>=0?'var(--green)':'var(--red)'}">${t.pnl_pct>=0?'+':''}${t.pnl_pct}%</span></div>`);}
    // Update pause states
    if(strats.sniper)setPaused('strat-sniper','strat-sniper-btn',!!strats.sniper.paused);
    if(strats.memecoin)setPaused('strat-memecoin','strat-meme-btn',!!strats.memecoin.paused);
    if(strats.arbitrage)setPaused('strat-arbitrage','strat-arb-btn',!!strats.arbitrage.paused);
    if(strats.scalping)setPaused('strat-scalping','strat-scalp-btn',!!strats.scalping.paused);
    if(strats.leverage)setPaused('strat-leverage','strat-lev-btn',!!strats.leverage.paused);
}
function setPnl(id,val,isPct){const el=document.getElementById(id);if(!el)return;const txt=isPct?((val>=0?'+':'')+val.toFixed(1)+'%'):((val>=0?'+$':'-$')+Math.abs(val).toFixed(2));el.textContent=txt;el.className='strat-pnl '+(val>0?'profit':val<0?'loss':'neutral');}
function setText(id,val){const el=document.getElementById(id);if(el)el.textContent=val;}
function setBar(id,pct){const el=document.getElementById(id);if(!el)return;el.style.width=Math.min(100,Math.max(0,pct))+'%';el.style.background=pct>=60?'var(--green)':pct>=40?'var(--yellow)':'var(--red)';}
function setRecent(id,items,renderer){const el=document.getElementById(id);if(!el||!items.length)return;el.innerHTML=items.map(renderer).join('');}
async function toggleStrategy(key){
    try{
        const resp=await fetch('/api/toggle-strategy',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({strategy:key})});
        const data=await resp.json();
        if(data.ok){
            const map={sniper:['strat-sniper','strat-sniper-btn'],memecoin:['strat-memecoin','strat-meme-btn'],arbitrage:['strat-arbitrage','strat-arb-btn'],scalping:['strat-scalping','strat-scalp-btn'],leverage:['strat-leverage','strat-lev-btn']};
            const ids=map[key];if(ids){const card=document.getElementById(ids[0]);
            if(data.paused){card.classList.add('is-paused');}else{card.classList.remove('is-paused');}
            const btn=document.getElementById(ids[1]);if(btn){btn.textContent=data.paused?'Continuar':'Parar';btn.className='strat-toggle-btn '+(data.paused?'paused':'running');}}
        }
    }catch(e){console.error('Toggle error:',e);}
}
// === Allocation system ===
let activeAllocations={};
async function allocateStrategy(){
    const sel=document.getElementById('alloc-strategy');
    const coinSel=document.getElementById('alloc-coin');
    const inp=document.getElementById('alloc-amount');
    const strategy=sel.value;
    const coin=coinSel.value;
    const amount=parseFloat(inp.value);
    if(!strategy){alert('Escolha uma estrategia!');return;}
    if(!amount||amount<=0){alert('Informe um valor valido!');return;}
    const btn=document.getElementById('alloc-play-btn');
    btn.disabled=true;btn.textContent='Enviando...';
    try{
        const resp=await fetch('/api/allocate-strategy',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({strategy:strategy,amount:amount,coin:coin})});
        const data=await resp.json();
        if(data.ok){
            activeAllocations[strategy]={amount:amount,coin:coin,status:'active'};
            renderAllocations();
            sel.value='';inp.value='';
        }else{alert('Erro: '+(data.error||'desconhecido'));}
    }catch(e){alert('Erro de conexao: '+e);}
    btn.disabled=false;btn.innerHTML='<svg viewBox="0 0 24 24" fill="currentColor" width="16" height="16"><polygon points="5,3 19,12 5,21"/></svg> Play';
}
async function deallocateStrategy(key){
    try{
        const a=activeAllocations[key]||{};
        const nameMap={sniper:'Sniping Pump.fun',memecoin:'Meme Coins',arbitrage:'Arbitragem DEX',scalping:'Scalping Tokens',leverage:'Leverage Trading'};
        const pnl=a.pnl||0;
        const trades=a.trades||0;
        const pnlStr=pnl>=0?'+$'+pnl.toFixed(4):'-$'+Math.abs(pnl).toFixed(4);
        if(!confirm('Parar MODO REAL para '+(nameMap[key]||key)+'?\n\nTrades: '+trades+'\nP&L: '+pnlStr+'\n\nO USDC sera convertido de volta para SOL.'))return;
        const resp=await fetch('/api/deallocate-strategy',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({strategy:key})});
        const result=await resp.json();
        if(result.ok){
            alert((nameMap[key]||key)+' encerrado!\n\nTrades: '+trades+'\nP&L Final: '+pnlStr+'\n\nO bot convertera o USDC restante para SOL.');
            delete activeAllocations[key];
            renderAllocations();
            renderRealModeSection();
        }else{
            alert('Erro ao parar: '+(result.error||'desconhecido'));
        }
    }catch(e){alert('Erro de conexao: '+e.message);}
}
function renderAllocations(){
    const container=document.getElementById('alloc-active-list');
    if(!container)return;
    const keys=Object.keys(activeAllocations);
    if(keys.length===0){container.innerHTML='';return;}
    const nameMap={sniper:'Sniping Pump.fun',memecoin:'Meme Coins',arbitrage:'Arbitragem DEX',scalping:'Scalping Tokens',leverage:'Leverage Trading'};
    let html='';
    for(const k of keys){
        const a=activeAllocations[k];
        html+=`<div class="alloc-active-item">
            <span class="alloc-strat-name">${nameMap[k]||k}</span>
            <span class="alloc-strat-amount">$${a.amount.toFixed(2)} ${a.coin||'SOL'}</span>
            <span class="alloc-strat-status">ATIVO</span>
            <button class="alloc-stop-btn" onclick="deallocateStrategy('${k}')">
                <svg viewBox="0 0 24 24" fill="currentColor" width="12" height="12"><rect x="4" y="4" width="16" height="16" rx="2"/></svg> Stop
            </button>
        </div>`;
    }
    container.innerHTML=html;
}
function updateAllocationsFromData(allocData){
    if(!allocData)return;
    activeAllocations={};
    for(const[k,v]of Object.entries(allocData)){
        if(v.active)activeAllocations[k]={amount:v.amount,coin:v.coin||'SOL',status:'active',pnl:v.pnl||0,trades:v.trades||0,last_tx:v.last_tx||'',sim_pnl_pct:v.sim_pnl_pct||0,last_trade_info:v.last_trade_info||null,trade_history:v.trade_history||[]};
    }
    renderAllocations();
    renderRealModeSection();
}
function renderRealModeSection(){
    const section=document.getElementById('real-mode-section');
    const grid=document.getElementById('real-strategies-grid');
    if(!section||!grid)return;
    const keys=Object.keys(activeAllocations);
    if(keys.length===0){section.style.display='none';return;}
    section.style.display='';
    const nameMap={sniper:'Sniping Pump.fun',memecoin:'Meme Coins',arbitrage:'Arbitragem DEX',scalping:'Scalping Tokens',leverage:'Leverage Trading'};
    const riskMap={sniper:'risk-alto',memecoin:'risk-alto',arbitrage:'risk-medio',scalping:'risk-medio-baixo',leverage:'risk-muito-alto'};
    let html='';
    for(const k of keys){
        const a=activeAllocations[k];
        const pnl=a.pnl||0;
        const simPct=a.sim_pnl_pct||0;
        const trades=a.trades||0;
        const pnlCls=pnl>0?'profit':pnl<0?'loss':'neutral';
        const pnlColor=pnl>0?'var(--green)':pnl<0?'var(--red)':'var(--text-muted)';
        const pctColor=simPct>0?'var(--green)':simPct<0?'var(--red)':'var(--text-muted)';
        const lastTx=a.last_tx||'';
        const txLink=lastTx&&!lastTx.startsWith('PAPER')?`https://solscan.io/tx/${lastTx}`:'';
        const info=a.last_trade_info;
        let infoHtml='';
        if(info){const ip=info.pnl_pct||0;infoHtml=`<div class="strat-cap-item strat-cap-full"><span class="strat-cap-label">Ultimo Sinal</span><span class="strat-cap-value" style="color:${ip>=0?'var(--green)':'var(--red)'}">${info.name||info.token||'?'} ${info.status||'?'} ${ip>=0?'+':''}${ip.toFixed(1)}%</span></div>`;}
        let txHtml='';
        if(lastTx){
            if(txLink){txHtml=`<div class="strat-cap-item strat-cap-full"><span class="strat-cap-label">Ultima TX</span><span class="strat-cap-value" style="word-break:break-all;font-size:0.7em;line-height:1.4"><a href="${txLink}" target="_blank" style="color:var(--purple);text-decoration:underline;">${lastTx}</a></span></div>`;}
            else{txHtml=`<div class="strat-cap-item strat-cap-full"><span class="strat-cap-label">Ultima TX</span><span class="strat-cap-value" style="color:var(--text-muted);word-break:break-all;font-size:0.7em;line-height:1.4">${lastTx}</span></div>`;}
        }
        html+=`<div class="strat-card real-mode ${riskMap[k]||''}" id="real-${k}">
            <div class="strat-header">
                <div class="strat-name">${nameMap[k]||k}</div>
                <span class="real-mode-badge">REAL</span>
            </div>
            <div class="strat-badges">
                <span class="real-coin-badge">${a.coin||'SOL'}</span>
                <span class="strat-badge return-badge">$${a.amount.toFixed(2)}</span>
                <span class="strat-badge time-badge">${trades} trade${trades!==1?'s':''}</span>
            </div>
            <div class="strat-pnl ${pnlCls}" id="real-${k}-pnl">${pnl>=0?'+$':'-$'}${Math.abs(pnl).toFixed(4)}</div>
            <div class="strat-capital">
                <div class="strat-cap-item"><span class="strat-cap-label">Alocado</span><span class="strat-cap-value" style="color:var(--yellow)">$${a.amount.toFixed(2)}</span></div>
                <div class="strat-cap-item"><span class="strat-cap-label">Moeda</span><span class="strat-cap-value" style="color:var(--purple)">${a.coin||'SOL'}</span></div>
                <div class="strat-cap-item"><span class="strat-cap-label">Sim %</span><span class="strat-cap-value" style="color:${pctColor}">${simPct>=0?'+':''}${simPct.toFixed(1)}%</span></div>
                <div class="strat-cap-item"><span class="strat-cap-label">P&L Real</span><span class="strat-cap-value" style="color:${pnlColor}">${pnl>=0?'+$':'-$'}${Math.abs(pnl).toFixed(4)}</span></div>
                ${infoHtml}
                ${txHtml}
            </div>
            <div class="strat-stats">
                <div class="strat-stat-row"><span class="strat-stat-label">Status</span><span class="strat-stat-value" style="color:var(--green)">ATIVO</span></div>
                <div class="strat-stat-row" style="cursor:pointer;" onclick="showTradeHistory('${k}')"><span class="strat-stat-label" style="text-decoration:underline;text-underline-offset:3px;">Trades Executados</span><span class="strat-stat-value" style="display:flex;align-items:center;gap:4px;">${trades} <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg></span></div>
            </div>
            <button class="alloc-stop-btn" style="width:100%;margin-top:12px;justify-content:center;" onclick="deallocateStrategy('${k}')">
                <svg viewBox="0 0 24 24" fill="currentColor" width="12" height="12"><rect x="4" y="4" width="16" height="16" rx="2"/></svg> Parar Modo Real
            </button>
        </div>`;
    }
    grid.innerHTML=html;
}
function showTradeHistory(stratKey){
    const a=activeAllocations[stratKey];
    if(!a)return;
    const nameMap={sniper:'Sniping Pump.fun',memecoin:'Meme Coins',arbitrage:'Arbitragem DEX',scalping:'Scalping Tokens',leverage:'Leverage Trading'};
    const history=(a.trade_history||[]).slice().reverse();
    let existing=document.getElementById('trade-history-modal');
    if(existing)existing.remove();
    const modal=document.createElement('div');
    modal.id='trade-history-modal';
    modal.style.cssText='position:fixed;inset:0;z-index:9999;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,0.7);backdrop-filter:blur(6px);';
    let rows='';
    if(history.length===0){
        rows='<div style="text-align:center;padding:30px;color:var(--text-muted);">Nenhum trade executado ainda</div>';
    } else {
        let totalPnl=0;
        let wins=0;
        for(const t of history){
            totalPnl+=t.pnl||0;
            if((t.pnl||0)>0)wins++;
            const d=new Date((t.time||0)*1000);
            const dt=d.toLocaleDateString('pt-BR',{day:'2-digit',month:'2-digit'})+' '+d.toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit'});
            const pnl=t.pnl||0;
            const pnlColor=pnl>0?'var(--green)':pnl<0?'var(--red)':'var(--text-muted)';
            const statusIcon=t.status==='ok'?'✅':t.status==='partial'?'⚠️':'❌';
            const simPct=t.sim_pnl_pct||0;
            const txSell=t.tx_sell||'';
            const txBuy=t.tx_buy||'';
            const mainTx=txSell||txBuy;
            const solscanLink=mainTx&&!mainTx.startsWith('PAPER')?`https://solscan.io/tx/${mainTx}`:'';
            const txBtn=solscanLink?`<a href="${solscanLink}" target="_blank" style="color:var(--purple);font-size:0.7em;text-decoration:none;">Solscan ↗</a>`:'';
            rows+=`<div style="display:grid;grid-template-columns:70px 1fr 80px 70px 50px;align-items:center;padding:10px 12px;border-bottom:1px solid rgba(255,255,255,0.05);font-size:0.82em;">
                <span style="color:var(--text-secondary);font-family:'JetBrains Mono',monospace;font-size:0.85em;">${dt}</span>
                <span style="display:flex;align-items:center;gap:6px;"><span>${statusIcon}</span><span style="color:var(--text-primary)">${t.signal||'?'}</span><span style="color:var(--text-muted);font-size:0.85em;">${t.direction||''} $${(t.amount||0).toFixed(2)}</span></span>
                <span style="text-align:right;font-family:'JetBrains Mono',monospace;font-weight:600;color:${pnlColor}">${pnl>=0?'+':'-'}$${Math.abs(pnl).toFixed(4)}</span>
                <span style="text-align:right;color:var(--text-muted);font-size:0.85em;">Sim ${simPct>=0?'+':''}${simPct.toFixed(1)}%</span>
                <span style="text-align:right;">${txBtn}</span>
            </div>`;
        }
        const wr=history.length>0?((wins/history.length)*100).toFixed(0):'0';
        rows=`<div style="display:flex;gap:16px;padding:12px 16px;background:rgba(255,255,255,0.03);border-bottom:1px solid rgba(255,255,255,0.08);font-size:0.8em;">
            <span>Total: <b style="color:${totalPnl>=0?'var(--green)':'var(--red)'}">${totalPnl>=0?'+':'-'}$${Math.abs(totalPnl).toFixed(4)}</b></span>
            <span>Win Rate: <b style="color:var(--green)">${wr}%</b> (${wins}/${history.length})</span>
        </div>`+rows;
    }
    modal.innerHTML=`<div style="background:var(--bg-card);border:1px solid var(--border-color);border-radius:16px;width:90%;max-width:680px;max-height:80vh;display:flex;flex-direction:column;box-shadow:0 20px 60px rgba(0,0,0,0.5);">
        <div style="display:flex;justify-content:space-between;align-items:center;padding:16px 20px;border-bottom:1px solid var(--border-color);">
            <div style="font-weight:700;font-size:1.05em;">📊 ${nameMap[stratKey]||stratKey} — Historico de Trades</div>
            <button onclick="document.getElementById('trade-history-modal').remove()" style="background:none;border:none;color:var(--text-secondary);cursor:pointer;font-size:1.4em;line-height:1;">×</button>
        </div>
        <div style="overflow-y:auto;flex:1;">${rows}</div>
    </div>`;
    modal.addEventListener('click',function(e){if(e.target===modal)modal.remove();});
    document.body.appendChild(modal);
}
// Tooltip positioning - move to body so overflow:hidden won't clip
(function(){
    document.querySelectorAll('.strat-help').forEach(function(helpBtn){
        var tip=helpBtn.querySelector('.strat-tooltip');
        if(!tip)return;
        document.body.appendChild(tip);
        function showTip(){
            tip.classList.add('visible');
            var r=helpBtn.getBoundingClientRect();
            var tw=300,gap=8;
            var left=r.left+r.width/2-tw/2;
            var top=r.bottom+gap;
            if(left<gap)left=gap;
            if(left+tw>window.innerWidth-gap)left=window.innerWidth-tw-gap;
            tip.style.left=left+'px';
            tip.style.top=top+'px';
            requestAnimationFrame(function(){
                var tipRect=tip.getBoundingClientRect();
                if(tipRect.bottom>window.innerHeight-gap){
                    tip.style.top=(r.top-tipRect.height-gap)+'px';
                }
            });
        }
        function hideTip(){tip.classList.remove('visible');}
        helpBtn.addEventListener('mouseenter',showTip);
        helpBtn.addEventListener('mouseleave',hideTip);
        tip.addEventListener('mouseenter',showTip);
        tip.addEventListener('mouseleave',hideTip);
    });
})();

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

    // ---- Draw indicator overlays ----
    const activeOverlays = Object.values(indicatorOverlays).filter(o => o.enabled && o.history.length >= 2);
    if (activeOverlays.length > 0) {
        // Right-side Y axis area for indicators
        const indAxisX = W - padRight + 2;

        activeOverlays.forEach((ind, idx) => {
            let indData = ind.history;
            if (chartRange > 0) indData = indData.slice(-chartRange);
            if (indData.length < 2) return;

            // Align indicator data length to price data length
            const len = Math.min(indData.length, prices.length);
            const alignedInd = indData.slice(-len);

            const indMin = ind.min;
            const indMax = ind.max;
            const indRange = indMax - indMin || 1;

            // Draw indicator line with glow
            ctx.save();
            ctx.globalAlpha = 0.25;
            ctx.strokeStyle = ind.color;
            ctx.lineWidth = 4;
            ctx.lineJoin = 'round';
            ctx.lineCap = 'round';
            ctx.beginPath();
            for (let i = 0; i < alignedInd.length; i++) {
                const x = padLeft + ((prices.length - len + i) / (prices.length - 1)) * chartW;
                const y = padTop + ((indMax - alignedInd[i].value) / indRange) * chartH;
                if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
            }
            ctx.stroke();
            ctx.restore();

            // Main indicator line
            ctx.save();
            ctx.globalAlpha = 0.85;
            ctx.strokeStyle = ind.color;
            ctx.lineWidth = 1.5;
            ctx.lineJoin = 'round';
            ctx.lineCap = 'round';
            ctx.setLineDash([4, 3]);
            ctx.beginPath();
            for (let i = 0; i < alignedInd.length; i++) {
                const x = padLeft + ((prices.length - len + i) / (prices.length - 1)) * chartW;
                const y = padTop + ((indMax - alignedInd[i].value) / indRange) * chartH;
                if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
            }
            ctx.stroke();
            ctx.setLineDash([]);

            // Current value label on the right edge
            const lastVal = alignedInd[alignedInd.length - 1].value;
            const lastIndY = padTop + ((indMax - lastVal) / indRange) * chartH;
            ctx.fillStyle = ind.color;
            ctx.font = 'bold 9px JetBrains Mono';
            ctx.textAlign = 'left';
            ctx.fillText(ind.label + ' ' + lastVal.toFixed(1), padLeft + 4, lastIndY - 5);
            ctx.restore();
        });
    }
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
// === SETTINGS MODAL ===
let currentPkMask='';
let currentPaperMode=true;
function openSettings(){
    document.getElementById('settings-modal').classList.add('active');
    document.getElementById('setting-pk').value='';
    document.getElementById('settings-status').className='setting-status';
    document.getElementById('settings-status').textContent='';
    const pkEl=document.getElementById('pk-current');
    if(currentPkMask){pkEl.textContent='Chave atual: '+currentPkMask;}else{pkEl.textContent='Nenhuma chave configurada';}
    document.getElementById('setting-live-mode').checked=!currentPaperMode;
    updateModeLabel();
}
function closeSettings(){document.getElementById('settings-modal').classList.remove('active');}
document.getElementById('settings-modal').addEventListener('click',function(e){if(e.target===this)closeSettings();});
function togglePkVisibility(){
    const inp=document.getElementById('setting-pk');
    inp.type=inp.type==='password'?'text':'password';
}
function updateModeLabel(){
    const live=document.getElementById('setting-live-mode').checked;
    const lbl=document.getElementById('mode-toggle-label');
    const sub=document.getElementById('mode-toggle-sub');
    if(live){lbl.textContent='MODO REAL (Live)';sub.textContent='Trades reais serao executados com dinheiro real!';sub.style.color='var(--red)';}
    else{lbl.textContent='Paper Trading (Simulado)';sub.textContent='Nenhum dinheiro real sera usado';sub.style.color='var(--text-muted)';}
}
async function saveSettings(){
    const btn=document.getElementById('settings-save-btn');
    const status=document.getElementById('settings-status');
    const pk=document.getElementById('setting-pk').value.trim();
    const liveMode=document.getElementById('setting-live-mode').checked;
    btn.disabled=true;btn.textContent='Salvando...';
    status.className='setting-status';status.textContent='';
    try{
        const resp=await fetch('/api/save-settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({private_key:pk||null,paper_trading:!liveMode})});
        const data=await resp.json();
        if(data.ok){
            status.className='setting-status success';
            status.textContent='Configuracoes salvas com sucesso!';
            if(pk){currentPkMask=pk.substring(0,4)+'...'+pk.substring(pk.length-4);document.getElementById('pk-current').textContent='Chave atual: '+currentPkMask;}
            currentPaperMode=!liveMode;
            setTimeout(closeSettings,2000);
        }else{status.className='setting-status error';status.textContent=data.error||'Erro ao salvar';}
    }catch(e){status.className='setting-status error';status.textContent='Erro de conexao: '+e.message;}
    btn.disabled=false;btn.textContent='Salvar Configuracoes';
}
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
        self.app.router.add_post('/api/toggle-strategy', self.handle_toggle_strategy)
        self.app.router.add_post('/api/allocate-strategy', self.handle_allocate_strategy)
        self.app.router.add_post('/api/deallocate-strategy', self.handle_deallocate_strategy)
        self.app.router.add_post('/api/save-settings', self.handle_save_settings)
        self.app.router.add_get('/ws', self.handle_websocket)
        self.logs = []
        self.max_logs = 100
        self._ws_clients = set()
        self._push_task = None

    def add_log(self, message: str):
        timestamp = now_br().strftime("%H:%M:%S")
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
            "last_update": now_br().strftime("%H:%M:%S"),
            "open_positions": dashboard["open_positions"],
            "open_pnl": dashboard["open_pnl_usd"],
            "total_pnl": dashboard["total_pnl_usd"],
            "win_rate": dashboard["win_rate"],
            "total_trades": dashboard["total_trades"],
            "positions": dashboard.get("positions", []),
            "indicators": indicators,
            "last_signal": last_signal,
            "logs": self.logs[-30:],
            "strategies": self.bot.strategies.get_all_dashboard_data() if hasattr(self.bot, 'strategies') else {},
            "wallet": self.bot.wallet.get_data() if hasattr(self.bot, 'wallet') and self.bot.wallet else {},
            "allocations": self.bot.strategies.get_all_allocations() if hasattr(self.bot, 'strategies') else {},
            "pk_mask": (config.SOLANA_PRIVATE_KEY[:4] + "..." + config.SOLANA_PRIVATE_KEY[-4:]) if len(config.SOLANA_PRIVATE_KEY) > 8 else "",
        }

    async def handle_status(self, request):
        try:
            price = await self.bot.price_fetcher.get_current_price()
            dashboard = self.bot.executor.get_dashboard_data(price)
            data = self._get_status_data(price, dashboard)
            return web.json_response(data)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def handle_toggle_strategy(self, request):
        try:
            data = await request.json()
            key = data.get("strategy", "")
            if hasattr(self.bot, 'strategies'):
                paused = self.bot.strategies.toggle_strategy(key)
                return web.json_response({"ok": True, "strategy": key, "paused": paused})
            return web.json_response({"error": "strategies not available"}, status=500)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    async def handle_allocate_strategy(self, request):
        try:
            data = await request.json()
            key = data.get("strategy", "")
            amount = float(data.get("amount", 0))
            coin = data.get("coin", "SOL")
            valid_keys = ["sniper", "memecoin", "arbitrage", "scalping", "leverage"]
            if key not in valid_keys:
                return web.json_response({"error": "invalid strategy"}, status=400)
            if amount <= 0:
                return web.json_response({"error": "invalid amount"}, status=400)
            if hasattr(self.bot, 'strategies'):
                ok = self.bot.strategies.allocate_strategy(key, amount, coin)
                return web.json_response({"ok": ok, "strategy": key, "amount": amount, "coin": coin})
            return web.json_response({"error": "strategies not available"}, status=500)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    async def handle_deallocate_strategy(self, request):
        try:
            data = await request.json()
            key = data.get("strategy", "")
            if hasattr(self.bot, 'strategies'):
                ok = self.bot.strategies.deallocate_strategy(key)
                return web.json_response({"ok": ok, "strategy": key})
            return web.json_response({"error": "strategies not available"}, status=500)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    async def handle_save_settings(self, request):
        try:
            data = await request.json()
            if hasattr(self.bot, '_apply_settings'):
                self.bot._apply_settings(data)
                return web.json_response({"ok": True})
            return web.json_response({"error": "bot not available"}, status=500)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

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
