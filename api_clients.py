#api_clients.py
import time
from typing import Dict, List, Any, Optional

import pandas as pd
from config import bybit_session

def _process_kline_data(kline_list: List[list]) -> pd.DataFrame:
    """Mengubah list data k-line mentah dari Bybit menjadi DataFrame yang bersih."""
    if not kline_list:
        return pd.DataFrame()

    df = pd.DataFrame(kline_list, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover'])
    
    numeric_cols = ['open', 'high', 'low', 'close', 'volume']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')
        
    df['timestamp'] = pd.to_datetime(pd.to_numeric(df['timestamp']), unit='ms')
    
    return df.iloc[::-1].reset_index(drop=True)

def get_latest_price(symbol: str) -> Optional[float]:
    """Mengambil harga pasar terakhir untuk simbol futures."""
    try:
        response = bybit_session.get_tickers(category="linear", symbol=symbol)
        if response and response.get('retCode') == 0:
            result_list = response['result']['list']
            if result_list:
                return float(result_list[0]['lastPrice'])
    except Exception as e:
        print(f"❌ Error API (get_latest_price) untuk {symbol}: {e}")
    return None

def get_historical_data(symbol: str, interval: str, limit: int) -> Optional[pd.DataFrame]:
    """Mengambil data k-line historis dari Bybit."""
    try:
        response = bybit_session.get_kline(
            category="linear", symbol=symbol, interval=interval, limit=limit)
        if response and response.get('retCode') == 0:
            return _process_kline_data(response['result']['list'])
    except Exception as e:
        print(f"❌ Error API (get_historical_data) untuk {symbol}: {e}")
    return None

def get_all_futures_tickers() -> Optional[List[Dict[str, Any]]]:
    """Mengambil data semua ticker dari pasar futures Bybit."""
    try:
        response = bybit_session.get_tickers(category="linear")
        if response and response.get('retCode') == 0:
            return response['result']['list']
    except Exception as e:
        print(f"❌ Error API (get_all_futures_tickers): {e}")
    return None

def download_historical_data(symbol: str, interval: str, start_time: int) -> Optional[str]:
    """Mengunduh data historis dalam jumlah besar dan menyimpannya ke CSV."""
    all_data = []
    limit = 1000
    
    while True:
        try:
            print(f"Mengambil data {symbol} dari {pd.to_datetime(start_time, unit='ms')}...")
            response = bybit_session.get_kline(
                category="linear", symbol=symbol, interval=interval,
                start=start_time, limit=limit
            )
            
            if response and response.get('retCode') == 0:
                data = response['result']['list']
                if not data:
                    break
                
                all_data.extend(data)
                # Pindah ke timestamp berikutnya untuk permintaan selanjutnya
                start_time = int(data[-1][0]) + (int(interval) * 60 * 1000)
            else:
                print(f"⚠️ Peringatan API: {response.get('retMsg')}")
                break
                
            time.sleep(0.5) # Jeda sopan untuk API
        except Exception as e:
            print(f"❌ Error saat mengunduh data: {e}")
            break

    if all_data:
        df = _process_kline_data(all_data)
        filename = f"{symbol}_{interval}m_data.csv"
        df.to_csv(filename, index=False)
        print(f"✅ Data berhasil disimpan ke {filename}")
        return filename
    
    return None
