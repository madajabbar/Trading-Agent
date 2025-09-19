# api_clients.py
import pandas as pd
from config import bybit_session, gemini_model
# Tambahkan time di import
import time 

def get_latest_price(symbol):
    """Mengambil harga pasar terakhir untuk simbol futures."""
    try:
        response = bybit_session.get_tickers(category="linear", symbol=symbol)
        if response and response.get('retCode') == 0:
            return float(response['result']['list'][0]['lastPrice'])
    except Exception as e:
        print(f"❌ Error API (get_latest_price) untuk {symbol}: {e}")
    return None

def get_market_sentiment(prompt):
    """Mengirim prompt yang sudah dibuat ke Gemini dan mengembalikan responsnya."""
    print("🤖 Meminta analisis dari Gemini...")
    try:
        response = gemini_model.generate_content(prompt, request_options={'timeout': 30})
        if response.text:
            return response.text.strip()
    except Exception as e:
        print(f"❌ Error API (get_market_sentiment): {e}")
    return None

def get_historical_data(symbol, interval='60', limit=100):
    """Mengambil data k-line historis dari Bybit."""
    try:
        response = bybit_session.get_kline(
            category="linear", symbol=symbol, interval=interval, limit=limit)
        if response and response.get('retCode') == 0:
            df = pd.DataFrame(response['result']['list'], columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover'])
            df['timestamp'] = pd.to_datetime(pd.to_numeric(df['timestamp']), unit='ms')
            df['close'] = pd.to_numeric(df['close'])
            df['volume'] = pd.to_numeric(df['volume']) # <-- TAMBAHKAN INI
            return df.iloc[::-1].reset_index(drop=True)
    except Exception as e:
        print(f"❌ Error API (get_historical_data) untuk {symbol}: {e}")
    return None

def get_all_futures_tickers():
    """Mengambil data semua ticker dari pasar futures Bybit."""
    try:
        response = bybit_session.get_tickers(category="linear")
        if response and response.get('retCode') == 0:
            return response['result']['list']
    except Exception as e:
        print(f"❌ Error API (get_all_futures_tickers): {e}")
    return 
    
def download_historical_data(symbol, interval='60', start_time=None):
    """
    Mengunduh data historis dalam jumlah besar dan menyimpannya ke CSV.
    Bybit API v5 mengizinkan pengambilan 1000 bar per permintaan.
    """
    all_data = []
    limit = 1000
    
    while True:
        try:
            print(f"Mengambil data {symbol} dari {pd.to_datetime(start_time, unit='ms')}...")
            response = bybit_session.get_kline(
                category="linear",
                symbol=symbol,
                interval=interval,
                start=start_time,
                limit=limit
            )
            
            if response and response.get('retCode') == 0:
                data = response['result']['list']
                if not data:
                    break # Berhenti jika tidak ada data lagi
                
                all_data.extend(data)
                # Atur start_time untuk permintaan berikutnya
                start_time = int(data[-1][0]) + (int(interval) * 60 * 1000)
            else:
                print(f"⚠️ Peringatan API: {response.get('retMsg')}")
                break
                
            time.sleep(0.5) # Jeda sopan untuk API

        except Exception as e:
            print(f"❌ Error saat mengunduh data: {e}")
            break

    if all_data:
        df = pd.DataFrame(all_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover'])
        df = df.iloc[::-1].reset_index(drop=True) # Balik urutan agar dari terlama -> terbaru
        df['timestamp'] = pd.to_datetime(pd.to_numeric(df['timestamp']), unit='ms')
        
        filename = f"{symbol}_{interval}m_data.csv"
        df.to_csv(filename, index=False)
        print(f"✅ Data berhasil disimpan ke {filename}")
        return filename
    
    return None


if __name__ == "__main__":
    # Unduh data 5 menit untuk DOGEUSDT, dimulai dari 3 bulan yang lalu
    three_months_ago = pd.Timestamp.now() - pd.DateOffset(days=1)
    start_date_ms = int(three_months_ago.timestamp() * 1000)

    print(f"📅 Akan mengunduh data 5 menit untuk DOGEUSDT selama 3 bulan terakhir...")
    
    # Ganti nama file agar tidak menimpa data lama
    filename = download_historical_data("DOGEUSDT", interval='5', start_time=start_date_ms)
    if filename:
        print(f"File disimpan sebagai: {filename}") # Output: DOGEUSDT_5m_data.csv