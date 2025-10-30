# strategy.py — Versi Perbaikan: "Tren + Volume + Reversi"
from typing import Dict, Any, Tuple, List
import pandas as pd
import talib
from api_clients import get_historical_data

def find_potential_coins(tickers: List[Dict[str, Any]]) -> List[str]:
    """
    PINDAI SEMUA koin USDT dengan filter dasar (tanpa batas jumlah).
    """
    if not tickers:
        return []
    df = pd.DataFrame(tickers)
    df['turnover24h'] = pd.to_numeric(df['turnover24h'], errors='coerce')
    df['lastPrice'] = pd.to_numeric(df['lastPrice'], errors='coerce')
    df = df[
        (df['symbol'].str.endswith('USDT')) &
        (df['lastPrice'] >= 0.1) &
        (df['turnover24h'] > 100_000)  # longgarkan volume
    ]
    # 🔥 HAPUS .head(5) → proses SEMUA koin
    return df['symbol'].tolist()

def make_decision(symbol: str, open_positions: Dict[str, Any], current_price: float) -> Tuple[str, str, float]:
    """
    Strategi baru:
    - Hanya trade jika tren jelas (EMA8 > EMA21 = uptrend, sebaliknya downtrend)
    - Entry hanya saat terjadi REVERSI KUAT (pinbar, engulfing) di area support/resistance
    - Konfirmasi volume tinggi
    """
    data = get_historical_data(symbol, interval='1', limit=50)
    if data is None or len(data) < 30:
        return "HOLD", f"🟡 Data tidak cukup untuk {symbol}", None

    close = pd.to_numeric(data['close'])
    high = pd.to_numeric(data['high'])
    low = pd.to_numeric(data['low'])
    opn = pd.to_numeric(data['open'])
    volume = pd.to_numeric(data['volume'])

    # --- Filter: Tren jelas (EMA8 vs EMA21) ---
    ema8 = talib.EMA(close, timeperiod=8).iloc[-1]
    ema21 = talib.EMA(close, timeperiod=21).iloc[-1]
    is_uptrend = ema8 > ema21
    is_downtrend = ema8 < ema21

    if not (is_uptrend or is_downtrend):
        return "HOLD", f"⏸️ {symbol} | Tren tidak jelas", None

    position_exists = symbol in open_positions
    if position_exists:
        return "HOLD", f"🔒 {symbol} | Sudah ada posisi", None

    # --- Filter volume ---
    current_vol = volume.iloc[-1]
    avg_vol = volume.iloc[-10:-1].mean()
    if current_vol < 0.8 * avg_vol:
        return "HOLD", f"🔇 {symbol} | Volume rendah", None

    # --- Cek candle terakhir: apakah reversal kuat? ---
    c0_open = opn.iloc[-1]
    c0_close = close.iloc[-1]
    c0_high = high.iloc[-1]
    c0_low = low.iloc[-1]
    c0_range = c0_high - c0_low

    # LONG: Bullish reversal di uptrend
    if is_uptrend:
        # Syarat: candle bullish kuat (close > open) dan dekat low
        if c0_close > c0_open and (c0_close - c0_open) > 0.6 * c0_range:
            # Dan harga dekat support (low 10 candle terakhir)
            support = low.iloc[-10:].min()
            if c0_low <= support * 1.001:
                return "GO_LONG", f"✅ {symbol} | BULLISH REVERSAL DI TREN NAIK", None

    # SHORT: Bearish reversal di downtrend
    if is_downtrend:
        if c0_close < c0_open and (c0_open - c0_close) > 0.6 * c0_range:
            resistance = high.iloc[-10:].max()
            if c0_high >= resistance * 0.999:
                return "GO_SHORT", f"✅ {symbol} | BEARISH REVERSAL DI TREN TURUN", None

    return "HOLD", f"⏸️ {symbol} | Tidak ada setup valid", None