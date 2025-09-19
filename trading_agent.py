import os
import time
import google.generativeai as genai
from pybit.unified_trading import HTTP
import pandas as pd
import talib

# --- KONFIGURASI API ---
# Sebaiknya gunakan environment variables untuk keamanan
BYBIT_API_KEY = "V5cw4djq04rRJv6eT0"
BYBIT_API_SECRET = "5Src6WqjN4hUkxflarUq5apLbhVmGKRnBsY6"
GEMINI_API_KEY = "AIzaSyDjqCZvjo7uoH8iyyCzvVDxa2gQvfx8NfU"

try:
    bybit_session = HTTP(
        testnet=True,
        api_key=BYBIT_API_KEY,
        api_secret=BYBIT_API_SECRET,
    )
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-1.5-flash-latest')
except Exception as e:
    print(f"❌ Gagal melakukan konfigurasi awal: {e}")
    exit()

# --- VARIABEL SIMULASI ---
VIRTUAL_PORTFOLIO = {
    'USDT': 10000.0,
}
SIMULATION_LOG = []

# --- FUNGSI-FUNGSI UTAMA ---

def get_latest_price(symbol):
    try:
        response = bybit_session.get_tickers(category="spot", symbol=symbol)
        if response and response.get('retCode') == 0:
            return float(response['result']['list'][0]['lastPrice'])
    except Exception as e:
        print(f"❌ Error saat mengambil harga {symbol}: {e}")
    return None

def get_market_sentiment(coin_symbol):
    base_coin = coin_symbol.replace('USDT', '')
    print(f"🤖 Menganalisis sentimen untuk {base_coin}...")
    try:
        prompt = (f"Analisis sentimen pasar untuk cryptocurrency {base_coin} saat ini "
                  f"berdasarkan berita global dan data pasar terkini. "
                  f"Jawab hanya dengan satu kata: Bullish, Bearish, atau Neutral.")
        response = gemini_model.generate_content(prompt, request_options={'timeout': 20})
        if response.text:
            sentiment = response.text.strip().capitalize()
            if sentiment in ["Bullish", "Bearish", "Neutral"]:
                print(f"Sentimen dari Gemini: {sentiment}")
                return sentiment
        return "Neutral"
    except Exception as e:
        print(f"❌ Error saat mengambil sentimen dari Gemini: {e}")
        return "Neutral"

def check_potential_coins():
    print("\n💡 Memindai pasar untuk mencari koin berpotensi...")
    try:
        response = bybit_session.get_tickers(category="spot")
        if not (response and response.get('retCode') == 0):
            return []
        df = pd.DataFrame(response['result']['list'])
        numeric_cols = ['turnover24h', 'price24hPcnt']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df.dropna(subset=numeric_cols, inplace=True)
        df = df[df['symbol'].str.endswith('USDT') & ~df['symbol'].str.contains('CUSDT|TUSD|USDC')]
        min_volume_usdt = 100_000
        df = df[df['turnover24h'] > min_volume_usdt]
        if df.empty: return []
        df['abs_price_change'] = abs(df['price24hPcnt'])
        top_5_volatile = df.sort_values(by='abs_price_change', ascending=False).head(5)
        potential_list = top_5_volatile['symbol'].tolist()
        print(f"✅ Top 5 koin potensial ditemukan: {potential_list}")
        return potential_list
    except Exception as e:
        print(f"❌ Error saat memindai koin: {e}")
    return []

# --- FUNGSI BARU UNTUK ANALISIS TEKNIKAL ---
def get_historical_data(symbol, interval='60'):
    """Mengambil data k-line (candlestick) historis dari Bybit."""
    try:
        response = bybit_session.get_kline(
            category="spot", symbol=symbol, interval=interval, limit=100)
        if response and response.get('retCode') == 0:
            df = pd.DataFrame(response['result']['list'], columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover'])
            # Ubah ke numerik dulu, baru konversi ke datetime
            df['timestamp'] = pd.to_datetime(pd.to_numeric(df['timestamp']), unit='ms')
            df['close'] = pd.to_numeric(df['close'])
            return df.iloc[::-1].reset_index(drop=True)
    except Exception as e:
        print(f"❌ Error saat mengambil data historis {symbol}: {e}")
    return None

def calculate_indicators(df):
    """Menghitung indikator teknikal seperti RSI."""
    indicators = {}
    if df is not None and len(df) > 14:
        close_prices = df['close']
        rsi = talib.RSI(close_prices, timeperiod=14)
        indicators['rsi'] = rsi.iloc[-1]
    return indicators

# --- FUNGSI KEPUTUSAN YANG SUDAH DI-UPGRADE ---
def make_decision(sentiment, indicators, symbol):
    """Logika trading yang menggabungkan sentimen dan indikator teknikal (RSI)."""
    base_coin = symbol.replace('USDT', '')
    rsi = indicators.get('rsi')
    
    # Mencetak informasi untuk logging
    if rsi:
        print(f"🤔 Membuat keputusan untuk {symbol}... Sentimen: {sentiment}, RSI: {rsi:.2f}")
    else:
        print(f"🤔 Membuat keputusan untuk {symbol}... Sentimen: {sentiment}, RSI: N/A")

    if rsi is None:
        return "HOLD" # Tidak bisa membuat keputusan tanpa data RSI

    # --- KONDISI BELI (BUY) ---
    if (sentiment == "Bullish" and rsi < 40) or (sentiment == "Neutral" and rsi < 30):
        if VIRTUAL_PORTFOLIO['USDT'] >= 1000:
            return "BUY"

    # --- KONDISI JUAL (SELL) ---
    if (sentiment == "Bearish" and rsi > 60) or (sentiment == "Neutral" and rsi > 70):
        if VIRTUAL_PORTFOLIO.get(base_coin, 0) > 0:
            return "SELL"
            
    return "HOLD"

def execute_virtual_trade(decision, price, symbol):
    base_coin = symbol.replace('USDT', '')
    if decision == "BUY":
        usdt_to_spend = 1000
        amount_bought = usdt_to_spend / price
        VIRTUAL_PORTFOLIO['USDT'] -= usdt_to_spend
        VIRTUAL_PORTFOLIO[base_coin] = VIRTUAL_PORTFOLIO.get(base_coin, 0) + amount_bought
        log_entry = f"[{pd.Timestamp.now()}] BUY {amount_bought:.6f} {base_coin} at ${price:,.2f}"
        print(f"✅ EKSEKUSI BUY: Membeli {amount_bought:.6f} {base_coin} seharga ${usdt_to_spend:,.0f}")
        SIMULATION_LOG.append(log_entry)
    elif decision == "SELL":
        amount_to_sell = VIRTUAL_PORTFOLIO.get(base_coin, 0)
        if amount_to_sell > 0:
            usdt_gained = amount_to_sell * price
            del VIRTUAL_PORTFOLIO[base_coin]
            VIRTUAL_PORTFOLIO['USDT'] += usdt_gained
            log_entry = f"[{pd.Timestamp.now()}] SELL {amount_to_sell:.6f} {base_coin} at ${price:,.2f}"
            print(f"✅ EKSEKUSI SELL: Menjual semua {base_coin} senilai ${usdt_gained:,.2f}")
            SIMULATION_LOG.append(log_entry)
    else:
        print(f"🟡 HOLD: Tidak ada tindakan untuk {symbol}.")

# --- LOOP UTAMA AGENT ---
def main():
    print("🚀 Agent Trading Crypto (Mode Simulasi & Analisis Teknikal) Dimulai!")
    print(f"Portofolio Awal: {VIRTUAL_PORTFOLIO}")
    
    while True:
        potential_coins = check_potential_coins()
        if not potential_coins:
            print("--- Tidak ada koin untuk dianalisis, menunggu 5 menit ---")
            time.sleep(300)
            continue

        for coin_symbol in potential_coins:
            print(f"\n--- Menganalisis {coin_symbol} ---")
            
            # 1. Ambil data harga & historis
            current_price = get_latest_price(coin_symbol)
            historical_data = get_historical_data(coin_symbol)
            
            if not current_price or historical_data is None:
                print(f"⚠️ Gagal mendapatkan data lengkap untuk {coin_symbol}, skip.")
                continue
            
            print(f"📈 Harga {coin_symbol} saat ini: ${current_price:,.2f}")
            
            # 2. Hitung Indikator & Dapatkan Sentimen
            indicators = calculate_indicators(historical_data)
            sentiment = get_market_sentiment(coin_symbol)
            
            # 3. Buat Keputusan
            decision = make_decision(sentiment, indicators, coin_symbol)
            
            # 4. Eksekusi
            execute_virtual_trade(decision, current_price, coin_symbol)
            
            print(f"💼 Portofolio Saat Ini: {VIRTUAL_PORTFOLIO}")
            time.sleep(5)

        print("\n--- Siklus selesai, menunggu 5 menit sebelum pemindaian berikutnya ---")
        time.sleep(300)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n🛑 Agent dihentikan oleh pengguna.")
        print("--- Log Simulasi Terakhir ---")
        for log in SIMULATION_LOG:
            print(log)
        print(f"--- Portofolio Akhir: {VIRTUAL_PORTFOLIO} ---")
    except Exception as e:
        print(f"\n\n💥 Terjadi error fatal: {e}")
        print("--- Portofolio Terakhir Sebelum Error ---")
        print(VIRTUAL_PORTFOLIO)