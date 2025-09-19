import pandas as pd
import talib
import json
from api_clients import get_historical_data, get_market_sentiment

def find_potential_coins(tickers):
    """
    Mencari koin potensial secara dinamis dengan jangkauan yang lebih luas.
    """
    if not tickers:
        return []
    
    MAX_COIN_PRICE = 10.0
    INITIAL_CANDIDATES = 500
    
    print(f"\n💡 Memindai seluruh pasar (Filter harga maks: ${MAX_COIN_PRICE}, Kandidat Awal: {INITIAL_CANDIDATES})...")
    try:
        df = pd.DataFrame(tickers)
        numeric_cols = ['turnover24h', 'price24hPcnt', 'lastPrice']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df.dropna(subset=numeric_cols, inplace=True)
        
        df = df[df['symbol'].str.endswith('USDT')]
        min_volume_usdt = 5_000_000
        df = df[df['turnover24h'] > min_volume_usdt]
        
        if df.empty:
            return []
        
        df['abs_price_change'] = abs(df['price24hPcnt'])
        top_volatile_coins = df.sort_values(by='abs_price_change', ascending=False).head(INITIAL_CANDIDATES)
        
        affordable_coins = top_volatile_coins[top_volatile_coins['lastPrice'] <= MAX_COIN_PRICE]
        
        if affordable_coins.empty:
            return []

        potential_list = affordable_coins['symbol'].tolist()
        print(f"✅ Koin potensial yang terjangkau ditemukan: {potential_list}")
        return potential_list
    except Exception as e:
        print(f"❌ Error saat memindai koin: {e}")
        return []

def calculate_indicators(df):
    """Menghitung semua indikator teknikal yang dibutuhkan."""
    indicators = {}
    if df is None or len(df) < 50:
        return indicators
    try:
        close_prices = pd.to_numeric(df['close'])
        high_prices = pd.to_numeric(df['high'])
        low_prices = pd.to_numeric(df['low'])
        
        indicators['rsi'] = talib.RSI(close_prices, timeperiod=14).iloc[-1]
        indicators['sma50'] = talib.SMA(close_prices, timeperiod=50).iloc[-1]
        
        macd, macd_signal, _ = talib.MACD(close_prices, fastperiod=12, slowperiod=26, signalperiod=9)
        indicators['macd'] = macd.iloc[-1]
        indicators['macd_signal'] = macd_signal.iloc[-1]
        
        upper, middle, lower = talib.BBANDS(close_prices, timeperiod=20, nbdevup=2, nbdevdn=2, matype=0)
        indicators['bband_upper'] = upper.iloc[-1]
        indicators['bband_middle'] = middle.iloc[-1]
        indicators['bband_lower'] = lower.iloc[-1]
        
        indicators['adx'] = talib.ADX(high_prices, low_prices, close_prices, timeperiod=14).iloc[-1]
        indicators['atr'] = talib.ATR(
            pd.to_numeric(df['high']), 
            pd.to_numeric(df['low']), 
            pd.to_numeric(df['close']), 
            timeperiod=14
        ).iloc[-1]
    except Exception as e:
        print(f"❌ Gagal menghitung indikator: {e}")
    return indicators

def make_decision_trend_following(symbol, open_positions, current_price):
    """Logika keputusan Trend Following yang mengembalikan keputusan dan log."""
    long_tf_data = get_historical_data(symbol, interval='240', limit=100)
    long_tf_indicators = calculate_indicators(long_tf_data)
    long_tf_sma50 = long_tf_indicators.get('sma50')
    
    short_tf_data = get_historical_data(symbol, interval='60', limit=100)
    short_tf_indicators = calculate_indicators(short_tf_data)
    short_tf_rsi = short_tf_indicators.get('rsi')
    short_tf_macd = short_tf_indicators.get('macd')
    short_tf_macd_signal = short_tf_indicators.get('macd_signal')

    if not all([long_tf_sma50, short_tf_rsi, short_tf_macd, short_tf_macd_signal]):
        return "HOLD", f"🟡 Data indikator tidak lengkap untuk {symbol} (Trend Following)."
        
    main_trend_is_up = current_price > long_tf_sma50
    macd_bullish_cross = short_tf_macd > short_tf_macd_signal

    log_message = f"🤔 Menganalisis (Trend Following) {symbol} | Tren (4H): {'UP' if main_trend_is_up else 'DOWN'} | RSI (1H): {short_tf_rsi:.2f} | MACD: {'BULL' if macd_bullish_cross else 'BEAR'}"
    decision = "HOLD"
    
    position_exists = symbol in open_positions

    if not position_exists:
        if main_trend_is_up and short_tf_rsi < 40 and macd_bullish_cross:
            decision = "GO_LONG"
        elif not main_trend_is_up and short_tf_rsi > 60 and not macd_bullish_cross:
            decision = "GO_SHORT"
    else:
        pos = open_positions[symbol]
        if pos['side'] == 'LONG' and not macd_bullish_cross:
            decision = "CLOSE_POSITION"
        elif pos['side'] == 'SHORT' and macd_bullish_cross:
            decision = "CLOSE_POSITION"
            
    return decision, log_message

def make_decision_mean_reversion(symbol, open_positions, current_price):
    """Logika keputusan Mean Reversion yang mengembalikan keputusan dan log."""
    data = get_historical_data(symbol, interval='15', limit=100)
    indicators = calculate_indicators(data)
    
    bband_upper = indicators.get('bband_upper')
    bband_middle = indicators.get('bband_middle')
    bband_lower = indicators.get('bband_lower')

    if not all([bband_upper, bband_middle, bband_lower]):
        return "HOLD", f"🟡 Data Bollinger Bands tidak lengkap untuk {symbol}."

    log_message = f"🤔 Menganalisis (Mean Reversion) {symbol} | Harga: ${current_price:,.4f} | Upper: ${bband_upper:,.4f} | Lower: ${bband_lower:,.4f}"
    decision = "HOLD"

    position_exists = symbol in open_positions

    if not position_exists:
        if current_price <= bband_lower:
            decision = "GO_LONG"
        elif current_price >= bband_upper:
            decision = "GO_SHORT"
    else:
        pos = open_positions[symbol]
        if pos['side'] == 'LONG' and current_price >= bband_middle:
            decision = "CLOSE_POSITION"
        elif pos['side'] == 'SHORT' and current_price <= bband_middle:
            decision = "CLOSE_POSITION"
            
    return decision, log_message

def make_adaptive_decision_traditional(symbol, open_positions, current_price):
    """Fungsi master yang memilih strategi dan mengembalikan keputusan + log."""
    market_condition_data = get_historical_data(symbol, interval='60', limit=100)
    indicators = calculate_indicators(market_condition_data)
    adx = indicators.get('adx')

    if not adx:
        log_message = f"🟡 Data ADX tidak lengkap untuk {symbol}, tidak ada tindakan."
        return "HOLD", log_message
    
    log_message = f"🚦 Analisis Kondisi Pasar ({symbol}): ADX = {adx:.2f}"

    if adx > 25:
        log_message += "\n -> Kondisi: TRENDING. Mengaktifkan strategi Trend Following."
        decision, strategy_log = make_decision_trend_following(symbol, open_positions, current_price)
        return decision, log_message + "\n" + strategy_log
    elif adx < 20:
        log_message += "\n -> Kondisi: SIDEWAYS. Mengaktifkan strategi Mean Reversion."
        decision, strategy_log = make_decision_mean_reversion(symbol, open_positions, current_price)
        return decision, log_message + "\n" + strategy_log
    else:
        log_message += "\n -> Kondisi: TIDAK JELAS. Menghindari pasar."
        return "HOLD", log_message

def make_adaptive_decision(symbol, open_positions, current_price):
    """
    Filter 2 lapis dengan pengecekan data ATR di awal.
    """
    log_message = f"🤔 Menganalisis {symbol}..."
    
    # --- PINDAHKAN PENGECEKAN ATR KE ATAS ---
    # Ambil data 1 jam untuk ATR (diperlukan untuk membuka posisi)
    tf_1h_data_for_atr = get_historical_data(symbol, interval='60', limit=100)
    indicators_for_atr = calculate_indicators(tf_1h_data_for_atr)
    atr = indicators_for_atr.get('atr')

    if not atr:
        return "HOLD", log_message + f"\n -> 🟡 Data ATR tidak lengkap untuk {symbol}."

    # --- FILTER LAPIS 1: PEMINDAIAN TEKNIKAL CEPAT ---
    data = get_historical_data(symbol, interval='15', limit=100)
    indicators = calculate_indicators(data)
    rsi = indicators.get('rsi')
    bband_upper = indicators.get('bband_upper')
    bband_lower = indicators.get('bband_lower')

    if not all([rsi, bband_upper, bband_lower]):
        return "HOLD", log_message + "\n -> 🟡 Data teknikal awal tidak lengkap."

    is_potential_long = current_price <= bband_lower and rsi < 35
    is_potential_short = current_price >= bband_upper and rsi > 65

    if not (is_potential_long or is_potential_short):
        log_message += f"\n -> 🟡 Sinyal teknikal awal tidak cukup kuat (RSI: {rsi:.2f})."
        return "HOLD", log_message
    
    # --- FILTER LAPIS 2: ANALISIS AI UNTUK KANDIDAT TERPILIH ---
    log_message += "\n -> ✅ Lolos filter teknikal! Meminta analisis mendalam dari AI..."
    
    # Kumpulkan data tambahan untuk prompt AI
    tf_1h_data = get_historical_data(symbol, interval='60', limit=100)
    tf_1h_indicators = calculate_indicators(tf_1h_data)
    adx = tf_1h_indicators.get('adx', 'N/A')
    
    # Bangun prompt komprehensif (sama seperti sebelumnya)
    prompt = f"""
    Analyze the trading potential for {symbol}. A pre-screening of technical indicators suggests a potential {'LONG' if is_potential_long else 'SHORT'} signal.
    Provide your output ONLY in a JSON format.

    # Context
    - Market Condition (ADX on 1h): {adx}
    - Signal Data (15m): RSI={rsi:.2f}, Price={current_price}, Upper_BB={bband_upper}, Lower_BB={bband_lower}

    # Task
    Confirm if this is a high-probability entry. Provide a confidence score from -10 (strong SHORT) to +10 (strong LONG). A score between -6 and 6 means HOLD. Provide reasoning.
    
    JSON Example: {{"decision": "LONG", "confidence_score": 8, "reason": "Price is at a strong support level (Lower BB) and RSI confirms oversold."}}
    """
    
    ai_response_text = get_market_sentiment(prompt)
    if not ai_response_text: return "HOLD", log_message + "\n -> ⚠️ Tidak ada respons dari AI."

    try:
        clean_json_text = ai_response_text.replace("```json", "").replace("```", "").strip()
        ai_data = json.loads(clean_json_text)
        score = ai_data.get("confidence_score", 0)
        reason = ai_data.get("reason", "N/A")
        log_message += f"\n -> 🧠 Analisis Gemini: Skor = {score}, Alasan = {reason}"

        if not (symbol in open_positions):
            if score >= 7: return "GO_LONG", log_message
            elif score <= -7: return "GO_SHORT", log_message
        
    except Exception as e:
        log_message += f"\n -> ⚠️ Gagal memproses respons AI: {e}"

    return "HOLD", log_message
