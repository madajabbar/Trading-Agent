import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sys
import talib
import time

# --- Impor dari Modul Proyek Anda ---
try:
    from config import SETTINGS
    from api_clients import download_historical_data
except ImportError as e:
    print(f"Error: Gagal mengimpor modul. Detail: {e}")
    sys.exit()

# --- KONFIGURASI BACKTEST ---
SYMBOL_TO_TEST = "DOGEUSDT"
DATA_INTERVAL = '15' # Timeframe: '60' untuk 1 jam
START_DATE = "2025-09-01"
INITIAL_BALANCE = 10.0

# Ambil pengaturan dari file settings.json
MARGIN_PER_TRADE = SETTINGS['trading_settings']['margin_per_trade']
LEVERAGE = SETTINGS['trading_settings']['leverage']
BYBIT_TAKER_FEE = SETTINGS['trading_settings']['bybit_taker_fee']
ATR_SL_MULTIPLIER = SETTINGS['risk_management']['atr_sl_multiplier']
ATR_TP_MULTIPLIER = SETTINGS['risk_management']['atr_tp_multiplier']


def run_backtest(data_file):
    """Menjalankan simulasi trading dengan indikator yang sudah dihitung sebelumnya."""
    try:
        df = pd.read_csv(data_file, parse_dates=['timestamp'])
        print(f"📈 Memuat {len(df)} bar data dari {data_file}...")
    except FileNotFoundError:
        print(f"❌ File data '{data_file}' tidak ditemukan.")
        return

    # --- TAHAP 1: PRA-KALKULASI SEMUA INDIKATOR ---
    print("⏳ Menghitung semua indikator (ini mungkin butuh beberapa saat)...")
    start_calc_time = time.time()
    try:
        close = pd.to_numeric(df['close'])
        high = pd.to_numeric(df['high'])
        low = pd.to_numeric(df['low'])

        df['rsi'] = talib.RSI(close, timeperiod=14)
        df['sma50'] = talib.SMA(close, timeperiod=50)
        df['adx'] = talib.ADX(high, low, close, timeperiod=14)
        df['atr'] = talib.ATR(high, low, close, timeperiod=14)
        
        upper, middle, lower = talib.BBANDS(close, timeperiod=20, nbdevup=2, nbdevdn=2)
        df['bband_upper'] = upper
        df['bband_lower'] = lower
        
        # Hapus baris awal yang tidak memiliki data indikator lengkap
        df.dropna(inplace=True)
        df.reset_index(drop=True, inplace=True)
        print(f"✅ Indikator berhasil dihitung dalam {time.time() - start_calc_time:.2f} detik.")

    except Exception as e:
        print(f"❌ Gagal menghitung indikator: {e}")
        return

    balance = INITIAL_BALANCE
    position = None
    trades = []
    balance_history = []

    print("🚀 Memulai proses backtest loop...")
    # --- TAHAP 2: LOOP BACKTEST YANG JAUH LEBIH CEPAT ---
    for i, row in df.iterrows():
        current_price = row['close']
        current_time = row['timestamp']
        
        # --- Manajemen Posisi (SL/TP) ---
        if position:
            pnl = (current_price - position['entry_price']) * position['size'] if position['side'] == 'LONG' else (position['entry_price'] - current_price) * position['size']
            sl_hit, tp_hit = False, False
            if position['side'] == 'LONG':
                if current_price <= position['stop_loss_price']: sl_hit = True
                elif current_price >= position['take_profit_price']: tp_hit = True
            elif position['side'] == 'SHORT':
                if current_price >= position['stop_loss_price']: sl_hit = True
                elif current_price <= position['take_profit_price']: tp_hit = True

            if sl_hit or tp_hit:
                entry_val = position['entry_price'] * position['size']
                exit_val = current_price * position['size']
                total_fee = (entry_val * BYBIT_TAKER_FEE) + (exit_val * BYBIT_TAKER_FEE)
                net_pnl = pnl - total_fee
                balance += position['margin'] + net_pnl
                trades.append({'exit_time': current_time, 'exit_price': current_price, 'pnl': net_pnl, **position})
                position = None

        # --- Mencari Sinyal Posisi Baru ---
        if not position:
            # Ambil nilai indikator yang sudah dihitung dari baris saat ini
            adx = row['adx']
            rsi = row['rsi']
            upper_band = row['bband_upper']
            lower_band = row['bband_lower']
            
            decision = "HOLD"
            # Simulasi logika adaptif sederhana
            if adx < 20: # Kondisi Ranging -> Mean Reversion
                if current_price <= lower_band and rsi < 30: decision = "GO_LONG"
                elif current_price >= upper_band and rsi > 70: decision = "GO_SHORT"
            
            if (decision in ["GO_LONG", "GO_SHORT"]) and balance >= MARGIN_PER_TRADE:
                side = "LONG" if decision == "GO_LONG" else "SHORT"
                atr = row['atr']
                if atr > 0:
                    sl_price = current_price - (atr * ATR_SL_MULTIPLIER)
                    tp_price = current_price + (atr * ATR_TP_MULTIPLIER)
                    if side == 'SHORT':
                        sl_price = current_price + (atr * ATR_SL_MULTIPLIER)
                        tp_price = current_price - (atr * ATR_TP_MULTIPLIER)
                    
                    size = (MARGIN_PER_TRADE * LEVERAGE) / current_price
                    balance -= MARGIN_PER_TRADE
                    position = {'entry_time': current_time, 'entry_price': current_price, 'side': side, 'size': size, 'margin': MARGIN_PER_TRADE, 'stop_loss_price': sl_price, 'take_profit_price': tp_price}

        # --- Catat Perkembangan Saldo (Equity) ---
        current_equity = balance
        if position:
            current_pnl = (current_price - position['entry_price']) * position['size'] if position['side'] == 'LONG' else (position['entry_price'] - current_price) * position['size']
            current_equity += (position['margin'] + current_pnl)
        balance_history.append({'timestamp': current_time, 'balance': current_equity})

    print("\n--- ✅ Backtest Selesai ---")
    analyze_results(pd.DataFrame(trades), pd.DataFrame(balance_history))


def analyze_results(trades_df, balance_df):
    """Menganalisis dan memvisualisasikan hasil backtest."""
    if trades_df.empty:
        print("🟡 Tidak ada trade yang dieksekusi selama periode backtest.")
        return

    total_trades = len(trades_df)
    win_trades = trades_df[trades_df['pnl'] > 0]
    win_rate = (len(win_trades) / total_trades * 100) if total_trades > 0 else 0
    total_pnl = trades_df['pnl'].sum()
    
    print("\n--- HASIL BACKTEST ---")
    print(f"Periode Data: {balance_df['timestamp'].iloc[0].date()} -> {balance_df['timestamp'].iloc[-1].date()}")
    print(f"Total Trade Selesai: {total_trades}")
    print(f"Win Rate: {win_rate:.2f}%")
    print(f"Total PnL: ${total_pnl:,.2f}")
    print(f"Profit/Loss vs. Modal Awal: {(total_pnl / INITIAL_BALANCE * 100):.2f}%")
    
    fig = make_subplots(rows=1, cols=1)
    fig.add_trace(go.Scatter(x=balance_df['timestamp'], y=balance_df['balance'], mode='lines', name='Equity Curve'))
    fig.update_layout(title=f'Performa Strategi Backtest ({SYMBOL_TO_TEST} - {DATA_INTERVAL}m)', xaxis_title='Tanggal', yaxis_title='Saldo Margin ($)', height=600)
    
    report_filename = "backtest_report.html"
    fig.write_html(report_filename)
    print(f"\n📊 Laporan visual backtest disimpan ke {report_filename}")


if __name__ == "__main__":
    data_filename = f"{SYMBOL_TO_TEST}_{DATA_INTERVAL}m_data.csv"
    try:
        pd.read_csv(data_filename)
        print(f"Menggunakan file data yang sudah ada: {data_filename}")
    except FileNotFoundError:
        print(f"File data {data_filename} tidak ditemukan, memulai unduhan...")
        start_date_ms = int(pd.Timestamp(START_DATE).timestamp() * 1000)
        download_historical_data(SYMBOL_TO_TEST, interval=DATA_INTERVAL, start_time=start_date_ms)
    
    run_backtest(data_filename)