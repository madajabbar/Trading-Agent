# main.py
import time
import pandas as pd
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, Tuple
from api_clients import get_latest_price, get_all_futures_tickers
from strategy import find_potential_coins, make_decision
from config import SETTINGS

# --- Pengaturan dari config ---
LEVERAGE = SETTINGS['trading_settings']['leverage']
BYBIT_TAKER_FEE = SETTINGS['trading_settings']['bybit_taker_fee']
MARGIN_PER_TRADE = SETTINGS['trading_settings']['margin_per_trade']
SL_PCT = SETTINGS['risk_management']['scalping_sl_pct']      # e.g., 0.0012
TP_PCT = SETTINGS['risk_management']['scalping_tp_pct']      # e.g., 0.0040

# --- File Penyimpanan ---
STATUS_FILE = "status.json"
POSITIONS_FILE = "positions.csv"
LOG_FILE = "trade_log.csv"

# --- State Global ---
MARGIN_BALANCE = 10.0
OPEN_POSITIONS: Dict[str, Any] = {}
data_lock = threading.Lock()
LAST_TRADE_TIME = {}  # cooldown per simbol

# --- Fungsi State ---
def load_state_on_startup():
    global MARGIN_BALANCE, OPEN_POSITIONS
    print("🔄 Memuat status terakhir...")
    with data_lock:
        if os.path.exists(STATUS_FILE):
            try:
                with open(STATUS_FILE, "r") as f:
                    MARGIN_BALANCE = json.load(f).get("margin_balance", 10.0)
            except Exception as e:
                print(f"⚠️ Gagal muat {STATUS_FILE}: {e}")
        if os.path.exists(POSITIONS_FILE):
            try:
                df = pd.read_csv(POSITIONS_FILE)
                float_cols = ['entry_price', 'size', 'margin', 'stop_loss_price', 'take_profit_price']
                for col in float_cols:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                OPEN_POSITIONS = {row['symbol']: row.to_dict() for _, row in df.iterrows()}
            except Exception as e:
                print(f"⚠️ Gagal muat {POSITIONS_FILE}: {e}")
                OPEN_POSITIONS = {}
    print("✅ Status dimuat.")

def save_all_states():
    with data_lock:
        balance = MARGIN_BALANCE
        positions = OPEN_POSITIONS.copy()
    try:
        with open(STATUS_FILE, "w") as f:
            json.dump({"margin_balance": balance}, f, indent=4)
    except Exception as e:
        print(f"⚠️ Gagal simpan {STATUS_FILE}: {e}")
    try:
        if positions:
            pd.DataFrame.from_dict(positions, orient='index').to_csv(POSITIONS_FILE, index=False)
        elif os.path.exists(POSITIONS_FILE):
            os.remove(POSITIONS_FILE)
    except Exception as e:
        print(f"⚠️ Gagal simpan {POSITIONS_FILE}: {e}")

def append_to_trade_log(entry: Dict[str, Any]):
    try:
        entry = {k: (float(v) if isinstance(v, (int, float)) else str(v)) for k, v in entry.items()}
        header = not os.path.exists(LOG_FILE)
        pd.DataFrame([entry]).to_csv(LOG_FILE, mode='a', header=header, index=False)
    except Exception as e:
        print(f"⚠️ Gagal log ke {LOG_FILE}: {e}")

# --- Eksekusi Posisi ---
def open_position(symbol: str, side: str, price: float):
    global MARGIN_BALANCE, OPEN_POSITIONS, LAST_TRADE_TIME
    with data_lock:
        if symbol in OPEN_POSITIONS or MARGIN_BALANCE < MARGIN_PER_TRADE:
            return
        sl_price = price * (1 - SL_PCT) if side == 'LONG' else price * (1 + SL_PCT)
        tp_price = price * (1 + TP_PCT) if side == 'LONG' else price * (1 - TP_PCT)
        size_in_coin = (MARGIN_PER_TRADE * LEVERAGE) / price
        MARGIN_BALANCE -= MARGIN_PER_TRADE
        OPEN_POSITIONS[symbol] = {
            "symbol": symbol, "side": side, "entry_price": price, "size": size_in_coin,
            "margin": MARGIN_PER_TRADE, "stop_loss_price": sl_price, "take_profit_price": tp_price
        }
        LAST_TRADE_TIME[symbol] = pd.Timestamp.now()
    print(f"✅ SCALP DIBUKA: {side} {symbol} | SL: ${sl_price:.6f} ({SL_PCT*100:.2f}%) | TP: ${tp_price:.6f} ({TP_PCT*100:.2f}%)")

def close_position(symbol: str, price: float, reason: str = "Sinyal"):
    global MARGIN_BALANCE
    pos_data = {}
    net_pnl = 0
    with data_lock:
        if symbol not in OPEN_POSITIONS: return
        pos = OPEN_POSITIONS.pop(symbol)
        gross_pnl = (price - pos['entry_price']) * pos['size'] if pos['side'] == 'LONG' else (pos['entry_price'] - price) * pos['size']
        fee = (pos['entry_price'] * pos['size'] + price * pos['size']) * BYBIT_TAKER_FEE
        net_pnl = gross_pnl - fee
        MARGIN_BALANCE += (pos['margin'] + net_pnl)
        pos_data = {
            "timestamp": pd.Timestamp.now().isoformat(),
            "symbol": symbol, "action": "CLOSE", "side": pos['side'],
            "price": price, "size": pos['size'], "margin": pos['margin'],
            "pnl": net_pnl, "reason": reason
        }
    if pos_data:
        append_to_trade_log(pos_data)
    print(f"✅ TUTUP {symbol} ({reason}) | PnL: ${net_pnl:.4f}")

def check_risk_management():
    with data_lock:
        positions = list(OPEN_POSITIONS.items())
    for symbol, pos in positions:
        price = get_latest_price(symbol)
        if not price: continue
        sl_hit = tp_hit = False
        sl = pos['stop_loss_price']
        tp = pos['take_profit_price']
        if pos['side'] == 'LONG':
            sl_hit = price <= sl
            tp_hit = price >= tp
        else:
            sl_hit = price >= sl
            tp_hit = price <= tp
        if sl_hit:
            close_position(symbol, price, "Stop Loss")
        elif tp_hit:
            close_position(symbol, price, "Take Profit")

def close_all_positions():
    print("\n🚨 Menutup semua posisi...")
    with data_lock:
        symbols = list(OPEN_POSITIONS.keys())
    for sym in symbols:
        price = get_latest_price(sym)
        if price:
            close_position(sym, price, "Shutdown")

# --- Loop Utama ---
def analyze_and_trade_coin(symbol: str) -> Tuple[str, str]:
    price = get_latest_price(symbol)
    if not price: return "ERROR", f"Tidak bisa ambil harga {symbol}"
    with data_lock:
        open_pos = OPEN_POSITIONS.copy()
    # Cooldown 120 detik per simbol (dari 60)
    if symbol in LAST_TRADE_TIME:
        if (pd.Timestamp.now() - LAST_TRADE_TIME[symbol]).total_seconds() < 120:
            return "HOLD", f"⏳ Cooldown aktif untuk {symbol}"
    decision, log_msg, _ = make_decision(symbol, open_pos, price)
    if decision in ["GO_LONG", "GO_SHORT"]:
        open_position(symbol, "LONG" if decision == "GO_LONG" else "SHORT", price)
    return decision, log_msg

def run_trading_loop():
    print(f"🚀 SCALPING AGENT DIMULAI | Saldo: ${MARGIN_BALANCE:.2f}")
    while True:
        check_risk_management()
        with data_lock:
            balance = MARGIN_BALANCE
            open_symbols = list(OPEN_POSITIONS.keys())
        coins = []
        if balance >= MARGIN_PER_TRADE:
            tickers = get_all_futures_tickers()
            coins = find_potential_coins(tickers)
        all_coins = list(set(coins + open_symbols))
        if not all_coins:
            time.sleep(60)
            continue

        # Batasi maksimal posisi aktif = 8 (dari modal $10)
        with data_lock:
            if len(OPEN_POSITIONS) >= 8:
                # Hanya pantau posisi terbuka, jangan buka baru
                all_coins = open_symbols

        with ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(analyze_and_trade_coin, all_coins))
        print("\n--- Hasil Siklus ---")
        for _, msg in results:
            if msg: print(msg)
        save_all_states()
        time.sleep(6)  # optimal untuk scalping 1-menit

if __name__ == "__main__":
    try:
        load_state_on_startup()
        run_trading_loop()
    except KeyboardInterrupt:
        print("\n🛑 Dihentikan oleh user.")
        close_all_positions()
        save_all_states()
        print("✅ Status disimpan.")
    except Exception as e:
        print(f"\n💥 Error: {e}")