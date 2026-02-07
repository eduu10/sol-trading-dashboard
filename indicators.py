"""
Módulo de Indicadores Técnicos
================================
Ichimoku Kinko Hyo, Retração/Extensão de Fibonacci, EMAs, RSI, ATR, Volume
Adaptado para dados de DEX (Solana/Jupiter)
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
import config


# ============================================================
# RSI - Relative Strength Index (ESSENCIAL!)
# ============================================================

def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Calcula RSI - indicador chave para evitar sobrecompra/sobrevenda."""
    delta = df["close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    df["rsi"] = 100 - (100 / (1 + rs))
    return df


def rsi_signal(df: pd.DataFrame) -> Dict:
    """
    RSI Score: evita comprar em sobrecompra, evita vender em sobrevenda.
    RSI < 30 = sobrevenda (bom para comprar)
    RSI > 70 = sobrecompra (bom para vender)
    RSI 40-60 = neutro
    """
    if "rsi" not in df.columns or len(df) < 2:
        return {"signal": None, "strength": 0, "value": 50}

    rsi = df.iloc[-1]["rsi"]
    rsi_prev = df.iloc[-2]["rsi"]

    if pd.isna(rsi):
        return {"signal": None, "strength": 0, "value": 50}

    # Sinais fortes
    if rsi < 25:
        return {"signal": "buy", "strength": 1.0, "value": rsi}
    elif rsi < 35 and rsi > rsi_prev:  # Saindo de sobrevenda
        return {"signal": "buy", "strength": 0.7, "value": rsi}
    elif rsi > 75:
        return {"signal": "sell", "strength": 1.0, "value": rsi}
    elif rsi > 65 and rsi < rsi_prev:  # Entrando em sobrecompra
        return {"signal": "sell", "strength": 0.7, "value": rsi}
    elif 45 <= rsi <= 55:
        return {"signal": None, "strength": 0, "value": rsi}
    elif rsi < 45:
        return {"signal": "buy", "strength": 0.3, "value": rsi}
    else:
        return {"signal": "sell", "strength": 0.3, "value": rsi}


# ============================================================
# ATR - Average True Range (para stop loss dinâmico)
# ============================================================

def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Calcula ATR para dimensionamento de stop loss."""
    high_low = df["high"] - df["low"]
    high_close = abs(df["high"] - df["close"].shift(1))
    low_close = abs(df["low"] - df["close"].shift(1))
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["atr"] = tr.rolling(window=period).mean()
    df["atr_pct"] = df["atr"] / df["close"] * 100  # ATR como % do preço
    return df


# ============================================================
# VOLUME - Confirmação de força do movimento
# ============================================================

def calculate_volume_profile(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """Calcula perfil de volume para confirmar movimentos."""
    df["volume_sma"] = df["volume"].rolling(window=period).mean()
    df["volume_ratio"] = df["volume"] / df["volume_sma"]
    return df


def volume_signal(df: pd.DataFrame) -> Dict:
    """
    Confirma se o movimento tem volume suficiente.
    Volume alto = movimento confiável
    Volume baixo = possível armadilha
    """
    if "volume_ratio" not in df.columns or len(df) < 2:
        return {"signal": None, "strength": 0, "ratio": 1.0}

    ratio = df.iloc[-1]["volume_ratio"]
    price_change = (df.iloc[-1]["close"] - df.iloc[-2]["close"]) / df.iloc[-2]["close"]

    if pd.isna(ratio):
        return {"signal": None, "strength": 0, "ratio": 1.0}

    # Volume alto + preço subindo = bullish forte
    if ratio > 1.5 and price_change > 0:
        return {"signal": "buy", "strength": min(ratio / 2, 1.0), "ratio": ratio}
    # Volume alto + preço caindo = bearish forte
    elif ratio > 1.5 and price_change < 0:
        return {"signal": "sell", "strength": min(ratio / 2, 1.0), "ratio": ratio}
    # Volume baixo = sinal fraco
    elif ratio < 0.5:
        return {"signal": None, "strength": -0.3, "ratio": ratio}
    else:
        return {"signal": None, "strength": 0, "ratio": ratio}


# ============================================================
# EMAs - Médias Móveis Exponenciais
# ============================================================

def calculate_emas(df: pd.DataFrame, periods: List[int] = None) -> pd.DataFrame:
    if periods is None:
        periods = config.EMA_PERIODS
    for period in periods:
        df[f"ema_{period}"] = df["close"].ewm(span=period, adjust=False).mean()
    return df


def ema_alignment_score(df: pd.DataFrame) -> float:
    """Score -1 a 1. +1 = bullish perfeito, -1 = bearish perfeito."""
    last = df.iloc[-1]
    periods = sorted(config.EMA_PERIODS)
    bullish_pairs = 0
    total_pairs = 0
    for i in range(len(periods)):
        for j in range(i + 1, len(periods)):
            total_pairs += 1
            if last[f"ema_{periods[i]}"] > last[f"ema_{periods[j]}"]:
                bullish_pairs += 1
    return (2 * bullish_pairs / total_pairs) - 1 if total_pairs > 0 else 0


def ema_crossover_signal(df: pd.DataFrame, short: int = 9, long: int = 21) -> Dict:
    if len(df) < 3:
        return {"signal": None, "strength": 0}
    curr_s, prev_s = df.iloc[-1][f"ema_{short}"], df.iloc[-2][f"ema_{short}"]
    curr_l, prev_l = df.iloc[-1][f"ema_{long}"], df.iloc[-2][f"ema_{long}"]
    if prev_s <= prev_l and curr_s > curr_l:
        return {"signal": "buy", "strength": min(abs(curr_s - curr_l) / curr_l * 100, 1.0)}
    if prev_s >= prev_l and curr_s < curr_l:
        return {"signal": "sell", "strength": min(abs(curr_s - curr_l) / curr_l * 100, 1.0)}
    return {"signal": None, "strength": 0}


# ============================================================
# ICHIMOKU KINKO HYO
# ============================================================

def calculate_ichimoku(df: pd.DataFrame) -> pd.DataFrame:
    t, k, s = config.ICHIMOKU_TENKAN, config.ICHIMOKU_KIJUN, config.ICHIMOKU_SENKOU_B
    
    df["tenkan_sen"] = (df["high"].rolling(t).max() + df["low"].rolling(t).min()) / 2
    df["kijun_sen"] = (df["high"].rolling(k).max() + df["low"].rolling(k).min()) / 2
    df["senkou_span_a"] = ((df["tenkan_sen"] + df["kijun_sen"]) / 2).shift(k)
    df["senkou_span_b"] = ((df["high"].rolling(s).max() + df["low"].rolling(s).min()) / 2).shift(k)
    df["chikou_span"] = df["close"].shift(-k)
    df["kumo_top"] = df[["senkou_span_a", "senkou_span_b"]].max(axis=1)
    df["kumo_bottom"] = df[["senkou_span_a", "senkou_span_b"]].min(axis=1)
    return df


def ichimoku_trend_score(df: pd.DataFrame) -> float:
    last = df.iloc[-1]
    close = last["close"]
    scores = []
    
    if pd.notna(last.get("kumo_top")) and pd.notna(last.get("kumo_bottom")):
        if close > last["kumo_top"]:
            scores.append(1.0)
        elif close < last["kumo_bottom"]:
            scores.append(-1.0)
        else:
            mid = (last["kumo_top"] + last["kumo_bottom"]) / 2
            scores.append(0.3 if close > mid else -0.3)
    
    if pd.notna(last.get("tenkan_sen")) and pd.notna(last.get("kijun_sen")):
        if last["tenkan_sen"] > last["kijun_sen"]:
            scores.append(0.8)
        elif last["tenkan_sen"] < last["kijun_sen"]:
            scores.append(-0.8)
    
    if pd.notna(last.get("senkou_span_a")) and pd.notna(last.get("senkou_span_b")):
        scores.append(0.6 if last["senkou_span_a"] > last["senkou_span_b"] else -0.6)
    
    return float(np.mean(scores)) if scores else 0.0


def ichimoku_signal(df: pd.DataFrame) -> Dict:
    if len(df) < 3:
        return {"signal": None, "strength": 0, "type": None}
    curr, prev = df.iloc[-1], df.iloc[-2]
    
    # TK Cross
    if (pd.notna(curr.get("tenkan_sen")) and pd.notna(curr.get("kijun_sen")) and
        pd.notna(prev.get("tenkan_sen")) and pd.notna(prev.get("kijun_sen"))):
        if prev["tenkan_sen"] <= prev["kijun_sen"] and curr["tenkan_sen"] > curr["kijun_sen"]:
            return {"signal": "buy", "strength": 0.7, "type": "tk_cross"}
        if prev["tenkan_sen"] >= prev["kijun_sen"] and curr["tenkan_sen"] < curr["kijun_sen"]:
            return {"signal": "sell", "strength": 0.7, "type": "tk_cross"}
    
    # Kumo Breakout
    if pd.notna(curr.get("kumo_top")) and pd.notna(curr.get("kumo_bottom")):
        if prev["close"] <= prev.get("kumo_top", float("inf")) and curr["close"] > curr["kumo_top"]:
            return {"signal": "buy", "strength": 0.9, "type": "kumo_breakout"}
        if prev["close"] >= prev.get("kumo_bottom", 0) and curr["close"] < curr["kumo_bottom"]:
            return {"signal": "sell", "strength": 0.9, "type": "kumo_breakout"}
    
    return {"signal": None, "strength": 0, "type": None}


# ============================================================
# FIBONACCI
# ============================================================

def find_swing_points(df: pd.DataFrame, lookback: int = None) -> Tuple[Optional[float], Optional[float]]:
    if lookback is None:
        lookback = config.FIBONACCI_LOOKBACK
    recent = df.tail(lookback)
    if len(recent) < 10:
        return None, None
    return recent["high"].max(), recent["low"].min()


def calculate_fibonacci_levels(high: float, low: float, direction: str = "up") -> Dict[float, float]:
    diff = high - low
    levels = {}
    if direction == "up":
        for lv in config.FIBONACCI_LEVELS:
            levels[lv] = high - (diff * lv)
        levels[1.272] = high + (diff * 0.272)
        levels[1.618] = high + (diff * 0.618)
    else:
        for lv in config.FIBONACCI_LEVELS:
            levels[lv] = low + (diff * lv)
        levels[1.272] = low - (diff * 0.272)
        levels[1.618] = low - (diff * 0.618)
    return levels


def fibonacci_score(df: pd.DataFrame) -> Dict:
    high, low = find_swing_points(df)
    if high is None:
        return {"support_score": 0, "resistance_score": 0, "levels": {}}
    
    price = df.iloc[-1]["close"]
    direction = "up" if price > (high + low) / 2 else "down"
    levels = calculate_fibonacci_levels(high, low, direction)
    
    # Proximidade
    tolerance = 0.005
    min_dist = float("inf")
    nearest = None
    for lv, lv_price in levels.items():
        dist = abs(price - lv_price) / price
        if dist < min_dist:
            min_dist = dist
            nearest = {"level": lv, "price": lv_price}
    
    strength = max(0, 1.0 - (min_dist / tolerance)) if min_dist <= tolerance else 0
    if nearest and nearest["level"] in [0.382, 0.5, 0.618]:
        strength = min(1.0, strength * 1.3)
    
    is_support = nearest and price >= nearest["price"]
    return {
        "support_score": strength if is_support else 0,
        "resistance_score": strength if not is_support else 0,
        "levels": levels,
        "nearest": nearest,
        "direction": direction,
    }


# ============================================================
# INTEGRAÇÃO
# ============================================================

def calculate_all(df: pd.DataFrame) -> pd.DataFrame:
    """Calcula todos os indicadores de uma vez."""
    df = calculate_emas(df)
    df = calculate_ichimoku(df)
    df = calculate_rsi(df)
    df = calculate_atr(df)
    df = calculate_volume_profile(df)
    return df


def get_all_scores(df: pd.DataFrame) -> Dict:
    """Retorna scores de todos os indicadores."""
    df = calculate_all(df)
    return {
        "ema_alignment": ema_alignment_score(df),
        "ema_crossover": ema_crossover_signal(df),
        "ichimoku_trend": ichimoku_trend_score(df),
        "ichimoku_signal": ichimoku_signal(df),
        "fibonacci": fibonacci_score(df),
        "rsi": rsi_signal(df),
        "volume": volume_signal(df),
        "atr": df.iloc[-1]["atr"] if "atr" in df.columns else 0,
        "atr_pct": df.iloc[-1]["atr_pct"] if "atr_pct" in df.columns else 1.0,
        "dataframe": df,
    }
