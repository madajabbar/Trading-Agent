import time
import pandas as pd
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor

# Impor dari modul lain
from api_clients import get_latest_price, get_all_futures_tickers, get_historical_data
from strategy import find_potential_coins, make_adaptive_decision as make_decision, calculate_indicators
from config import bybit_session, gemini_model

# --- Variabel Global & Konfigurasi ---
MARGIN_BALANCE = 10.0
OPEN_POSITIONS = {}
LEVERAGE = 5
SIMULATION_LOG = []
BYBIT_TAKER_FEE = 0.00055
# --- PARAMETER MANAJEMEN RISIKO BARU ---
ATR_SL_MULTIPLIER = 2.0  # Stop-loss pada jarak 2x ATR
ATR_TP_MULTIPLIER = 4.0  # Take-profit pada jarak 4x ATR (Risk/Reward Ratio 1:2)

# --- Kunci untuk Keamanan Thread ---
data_lock = threading.Lock()

def load_state_on_startup():
    """Memuat status terakhir dari file (thread-safe)."""
    global MARGIN_BALANCE, OPEN_POSITIONS, SIMULATION_LOG
    with data_lock:
        if os.path.exists("live_data.json"):
            try:
                with open("live_data.json", "r") as f:
                    saved_data = json.load(f)
                    MARGIN_BALANCE = saved_data.get("margin_balance", 10.0)
                    OPEN_POSITIONS = saved_data.get("open_positions", {})
                    SIMULATION_LOG = saved_data.get("simulation_log", [])
                    print("✅ Status terakhir berhasil dimuat.")
                    if OPEN_POSITIONS:
                        print(f"Posisi terbuka yang ditemukan: {list(OPEN_POSITIONS.keys())}")
            except Exception as e:
                print(f"⚠️ Gagal memuat status: {e}. Memulai sesi baru.")

def open_position(symbol, side, price, atr):
    """Membuka posisi dengan SL dan TP dinamis berbasis ATR."""
    global MARGIN_BALANCE, OPEN_POSITIONS
    with data_lock:
        if symbol in OPEN_POSITIONS: return
        MARGIN_PER_TRADE = 1.0 
        if MARGIN_BALANCE < MARGIN_PER_TRADE: return

        sl_price = price - (atr * ATR_SL_MULTIPLIER) if side == 'LONG' else price + (atr * ATR_SL_MULTIPLIER)
        tp_price = price + (atr * ATR_TP_MULTIPLIER) if side == 'LONG' else price - (atr * ATR_TP_MULTIPLIER)
        
        position_size_usdt = MARGIN_PER_TRADE * LEVERAGE
        size_in_coin = position_size_usdt / price
        MARGIN_BALANCE -= MARGIN_PER_TRADE
        
        OPEN_POSITIONS[symbol] = {
            "side": side, "entry_price": price, "size": size_in_coin, "margin": MARGIN_PER_TRADE,
            "stop_loss_price": sl_price, # <-- BARU
            "take_profit_price": tp_price # <-- BARU
        }
        
        # tsl_price = OPEN_POSITIONS[symbol]['trailing_stop_price']
        log_entry = { "timestamp": pd.Timestamp.now().isoformat(), "symbol": symbol, "action": "OPEN", "side": side, "price": price, "size": size_in_coin, "margin": MARGIN_PER_TRADE, "pnl": 0 }
        print(f"✅ POSISI DIBUKA: {side} {symbol} | SL @ ${sl_price:,.4f} | TP @ ${tp_price:,.4f}")
        SIMULATION_LOG.append(log_entry)

def close_position(symbol, price):
    """Menutup posisi yang ada (thread-safe)."""
    global MARGIN_BALANCE, OPEN_POSITIONS, SIMULATION_LOG
    with data_lock:
        if symbol not in OPEN_POSITIONS: return
        pos = OPEN_POSITIONS.pop(symbol)
        
        gross_pnl = (price - pos['entry_price']) * pos['size'] if pos['side'] == 'LONG' else (pos['entry_price'] - price) * pos['size']
        entry_val = pos['entry_price'] * pos['size']
        exit_val = price * pos['size']
        total_fee = (entry_val * BYBIT_TAKER_FEE) + (exit_val * BYBIT_TAKER_FEE)
        net_pnl = gross_pnl - total_fee
        MARGIN_BALANCE += (pos['margin'] + net_pnl)
        
        log_entry = { "timestamp": pd.Timestamp.now().isoformat(), "symbol": symbol, "action": "CLOSE", "side": pos['side'], "price": price, "size": pos['size'], "margin": pos['margin'], "pnl": net_pnl, "fee": total_fee }
        result = "UNTUNG" if net_pnl >= 0 else "RUGI"
        print(f"✅ POSISI DITUTUP: {symbol} | PnL Bersih ${net_pnl:,.2f} ({result}) | Saldo: ${MARGIN_BALANCE:,.2f}")
        SIMULATION_LOG.append(log_entry)

def check_risk_management():
    """Memeriksa SL dan TP untuk semua posisi."""
    with data_lock:
        positions_to_check = list(OPEN_POSITIONS.keys())
    
    for symbol in positions_to_check:
        with data_lock:
            if symbol not in OPEN_POSITIONS: continue
            pos = OPEN_POSITIONS[symbol]
        
        current_price = get_latest_price(symbol)
        if not current_price: continue

        sl_hit, tp_hit = False, False
        if pos['side'] == 'LONG':
            if current_price <= pos['stop_loss_price']: sl_hit = True
            elif current_price >= pos['take_profit_price']: tp_hit = True
        elif pos['side'] == 'SHORT':
            if current_price >= pos['stop_loss_price']: sl_hit = True
            elif current_price <= pos['take_profit_price']: tp_hit = True
        
        if sl_hit:
            print(f"🛑 STOP LOSS tercapai untuk {symbol}!")
            close_position(symbol, current_price)
        elif tp_hit:
            print(f"🎯 TAKE PROFIT tercapai untuk {symbol}!")
            close_position(symbol, current_price)

def save_live_data():
    """Menyimpan status agent saat ini (thread-safe)."""
    with data_lock:
        live_data = { "margin_balance": MARGIN_BALANCE, "open_positions": OPEN_POSITIONS, "simulation_log": SIMULATION_LOG, "last_update": pd.Timestamp.now().isoformat() }
    try:
        with open("live_data.json", "w") as f:
            json.dump(live_data, f, indent=4)
    except Exception as e:
        print(f"⚠️ Gagal menyimpan data live: {e}")

def analyze_and_trade_coin(symbol):
    """Fungsi 'pekerja' yang menganalisis dan mengeksekusi satu koin."""
    price = get_latest_price(symbol)
    if not price: return None, f"Gagal mendapatkan harga untuk {symbol}"

    with data_lock:
        current_open_positions = OPEN_POSITIONS.copy()

    # Keputusan sekarang sepenuhnya ditangani oleh strategy.py
    # Termasuk pengambilan data historis dan kalkulasi indikator
    decision, log_message = make_decision(symbol, current_open_positions, price)
    
    # Eksekusi berdasarkan keputusan
    if decision == "GO_LONG" or decision == "GO_SHORT":
        # Ambil ATR untuk menentukan SL/TP, gunakan timeframe yang relevan (misal: 1 jam)
        data = get_historical_data(symbol, interval='60', limit=100)
        indicators = calculate_indicators(data)
        atr = indicators.get('atr')
        if atr:
            open_position(symbol, "LONG" if decision == "GO_LONG" else "SHORT", price, atr)
        else:
            log_message += f"\n⚠️ Tidak bisa membuka posisi {symbol}, data ATR tidak ada."
    elif decision == "CLOSE_POSITION":
        close_position(symbol, price)
    
    return decision, log_message

    
def run_trading_loop():
    """Loop utama yang menjalankan analisis paralel dan logging terpusat."""
    print("🚀 Agent Trading FUTURES (Mode Paralel & Adaptif) Dimulai!")
    print(f"Saldo Margin Awal: ${MARGIN_BALANCE:,.2f} | Leverage: {LEVERAGE}x")

    while True:
        check_risk_management()
        
        with data_lock:
            current_open_positions_keys = list(OPEN_POSITIONS.keys())
        
        all_tickers = get_all_futures_tickers()
        potential_coins = find_potential_coins(all_tickers)
        coins_to_check = list(set(potential_coins + current_open_positions_keys))

        if not coins_to_check:
            print("\n--- Tidak ada koin untuk dianalisis, menunggu 1 menit ---")
            time.sleep(60)
            continue

        # Eksekusi paralel dan kumpulkan hasilnya
        results = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(analyze_and_trade_coin, coins_to_check))

        # Cetak log secara terpusat dan rapi
        print("\n--- Hasil Analisis Siklus Ini ---")
        for decision, log_message in results:
            if log_message:
                print(log_message)
        
        print("\n--- Siklus paralel selesai, menunggu 1 menit ---")
        save_live_data()
        time.sleep(60)

def close_all_positions():
    """Menutup semua posisi virtual yang terbuka saat shutdown."""
    print("\n🚨 Menerima sinyal shutdown. Menutup semua posisi terbuka...")
    with data_lock:
        positions_to_close = list(OPEN_POSITIONS.keys())
    
    if not positions_to_close:
        print("✅ Tidak ada posisi terbuka untuk ditutup.")
        return

    for symbol in positions_to_close:
        latest_price = get_latest_price(symbol)
        if latest_price:
            print(f"-> Menutup posisi {symbol}...")
            close_position(symbol, latest_price)
        else:
            print(f"⚠️ Tidak bisa mendapatkan harga untuk menutup {symbol}.")
    print("✅ Semua posisi berhasil ditutup.")

if __name__ == "__main__":
    try:
        load_state_on_startup()
        run_trading_loop()
    except KeyboardInterrupt:
        print("\n\n🛑 Agent dihentikan oleh pengguna.")
        close_all_positions()
        save_live_data()
        print("✅ Status terakhir berhasil disimpan.")
        print(f"--- Saldo Margin Akhir: ${MARGIN_BALANCE:,.2f} ---")
    except Exception as e:
        print(f"\n\n💥 Terjadi error fatal: {e}")