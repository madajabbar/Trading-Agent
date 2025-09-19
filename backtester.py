import time
import pandas as pd
import json

# Impor fungsi-fungsi yang relevan
from api_clients import get_latest_price, get_all_futures_tickers
# --- PERUBAHAN UTAMA: Impor strategi spesifik ---
from strategy import find_potential_coins, make_decision_mean_reversion as make_decision

# --- KONFIGURASI AGENT ---
# Sesuaikan dengan modal Anda saat live
MARGIN_BALANCE = 10.0
LEVERAGE = 5 # Leverage lebih rendah untuk live
# Jarak TSL lebih ketat untuk strategi fast trading
TRAILING_STOP_LOSS_PERCENT = 5.0 

# --- Variabel Global ---
OPEN_POSITIONS = {}
SIMULATION_LOG = []

def open_position(symbol, side, price):
    """Membuka posisi virtual baru dengan manajemen risiko."""
    global MARGIN_BALANCE
    if symbol in OPEN_POSITIONS: return

    # Alokasi 10% dari modal per trade
    MARGIN_PER_TRADE = MARGIN_BALANCE * 0.1
    if MARGIN_PER_TRADE < 1.0: # Batas minimum margin $1
        MARGIN_PER_TRADE = 1.0

    if MARGIN_BALANCE < MARGIN_PER_TRADE:
        print(f"❌ Margin tidak cukup untuk membuka posisi.")
        return

    position_size_usdt = MARGIN_PER_TRADE * LEVERAGE
    size_in_coin = position_size_usdt / price
    
    MARGIN_BALANCE -= MARGIN_PER_TRADE
    
    OPEN_POSITIONS[symbol] = {
        "side": side,
        "entry_price": price,
        "size": size_in_coin,
        "margin": MARGIN_PER_TRADE,
        "highest_price_since_entry": price if side == 'LONG' else 0,
        "lowest_price_since_entry": price if side == 'SHORT' else float('inf'),
        "trailing_stop_price": price * (1 - (TRAILING_STOP_LOSS_PERCENT / 100)) if side == 'LONG' else price * (1 + (TRAILING_STOP_LOSS_PERCENT / 100))
    }
    
    tsl_price = OPEN_POSITIONS[symbol]['trailing_stop_price']
    log_entry = { "timestamp": pd.Timestamp.now().isoformat(), "symbol": symbol, "action": "OPEN", "side": side, "price": price, "size": size_in_coin, "margin": MARGIN_PER_TRADE, "pnl": 0 }
    print(f"✅ POSISI DIBUKA: {side} {symbol} senilai ${position_size_usdt:,.2f} (TSL di ${tsl_price:,.2f})")
    SIMULATION_LOG.append(log_entry)

def close_position(symbol, price):
    """Menutup posisi yang ada dan merealisasikan PnL."""
    global MARGIN_BALANCE
    if symbol not in OPEN_POSITIONS: return
    
    pos = OPEN_POSITIONS.pop(symbol)
    pnl = (price - pos['entry_price']) * pos['size'] if pos['side'] == 'LONG' else (pos['entry_price'] - price) * pos['size']
    MARGIN_BALANCE += (pos['margin'] + pnl)
    
    log_entry = { "timestamp": pd.Timestamp.now().isoformat(), "symbol": symbol, "action": "CLOSE", "side": pos['side'], "price": price, "size": pos['size'], "margin": pos['margin'], "pnl": pnl }
    result = "UNTUNG" if pnl >= 0 else "RUGI"
    print(f"✅ POSISI DITUTUP: {symbol} | PnL ${pnl:,.2f} ({result}) | Saldo Margin: ${MARGIN_BALANCE:,.2f}")
    SIMULATION_LOG.append(log_entry)

def check_risk_management():
    """Memeriksa semua posisi terbuka untuk trigger Trailing Stop-Loss."""
    if not OPEN_POSITIONS: return
    positions_to_check = list(OPEN_POSITIONS.keys())
    
    for symbol in positions_to_check:
        if symbol not in OPEN_POSITIONS: continue
        pos = OPEN_POSITIONS[symbol]
        current_price = get_latest_price(symbol)
        if not current_price: continue

        if pos['side'] == 'LONG':
            if current_price > pos['highest_price_since_entry']:
                pos['highest_price_since_entry'] = current_price
                new_tsl = current_price * (1 - (TRAILING_STOP_LOSS_PERCENT / 100))
                if new_tsl > pos['trailing_stop_price']:
                    pos['trailing_stop_price'] = new_tsl
                    print(f"🔒 TSL {symbol} (LONG) naik ke ${new_tsl:,.2f}")
            if current_price <= pos['trailing_stop_price']:
                print(f"🛑 TRAILING STOP LOSS tercapai untuk {symbol} (LONG)!")
                close_position(symbol, current_price)
        elif pos['side'] == 'SHORT':
            if current_price < pos['lowest_price_since_entry']:
                pos['lowest_price_since_entry'] = current_price
                new_tsl = current_price * (1 + (TRAILING_STOP_LOSS_PERCENT / 100))
                if new_tsl < pos['trailing_stop_price']:
                    pos['trailing_stop_price'] = new_tsl
                    print(f"🔒 TSL {symbol} (SHORT) turun ke ${new_tsl:,.2f}")
            if current_price >= pos['trailing_stop_price']:
                print(f"🛑 TRAILING STOP LOSS tercapai untuk {symbol} (SHORT)!")
                close_position(symbol, current_price)

def update_unrealized_pnl():
    """Memperbarui dan menampilkan PnL untuk semua posisi terbuka."""
    if not OPEN_POSITIONS: return
    print("\n--- Posisi Terbuka ---")
    for symbol, pos in OPEN_POSITIONS.items():
        current_price = get_latest_price(symbol)
        if current_price:
            pnl = (current_price - pos['entry_price']) * pos['size'] if pos['side'] == 'LONG' else (pos['entry_price'] - current_price) * pos['size']
            pnl_percent = (pnl / pos['margin']) * 100
            print(f"{symbol} ({pos['side']}) | PnL: ${pnl:,.2f} ({pnl_percent:+.2f}%) | TSL @ ${pos['trailing_stop_price']:,.2f}")

def save_live_data():
    """Menyimpan status agent saat ini ke file JSON untuk dibaca oleh dashboard."""
    live_data = {
        "margin_balance": MARGIN_BALANCE,
        "open_positions": OPEN_POSITIONS,
        "simulation_log": SIMULATION_LOG,
        "last_update": pd.Timestamp.now().isoformat()
    }
    try:
        with open("live_data.json", "w") as f:
            json.dump(live_data, f, indent=4)
    except Exception as e:
        print(f"⚠️ Gagal menyimpan data live: {e}")

def run_trading_loop():
    """Loop utama yang menjalankan semua logika agent."""
    print("🚀 Agent Trading FUTURES (Strategi: Mean Reversion) Dimulai!")
    print(f"Saldo Margin Awal: ${MARGIN_BALANCE:,.2f} | Leverage: {LEVERAGE}x")
    print(f"Trailing Stop-Loss: {TRAILING_STOP_LOSS_PERCENT}%")

    while True:
        check_risk_management()
        update_unrealized_pnl()
        
        all_tickers = get_all_futures_tickers()
        potential_coins = find_potential_coins(all_tickers)
        
        coins_to_check = list(set(potential_coins + list(OPEN_POSITIONS.keys())))

        if not coins_to_check:
            print("\n--- Tidak ada koin untuk dianalisis, menunggu 1 menit ---")
            time.sleep(60)
            continue

        for symbol in coins_to_check:
            print(f"\n--- Menganalisis {symbol} ---")
            price = get_latest_price(symbol)
            if not price: continue

            # Memanggil fungsi keputusan spesifik untuk Mean Reversion
            decision = make_decision(symbol, OPEN_POSITIONS, price)
            
            if decision == "GO_LONG":
                open_position(symbol, "LONG", price)
            elif decision == "GO_SHORT":
                open_position(symbol, "SHORT", price)
            elif decision == "CLOSE_POSITION":
                close_position(symbol, price)
            
            time.sleep(5)

        print("\n--- Siklus selesai, menunggu 1 menit ---")
        save_live_data()
        time.sleep(60)

if __name__ == "__main__":
    try:
        # Impor dan jalankan konfigurasi API di awal
        from config import bybit_session, gemini_model
        run_trading_loop()
    except KeyboardInterrupt:
        print("\n\n🛑 Agent dihentikan oleh pengguna.")
        
        if SIMULATION_LOG:
            log_df = pd.DataFrame(SIMULATION_LOG)
            log_df.to_csv("trading_log.csv", index=False)
            print("✅ Log trading berhasil disimpan ke trading_log.csv")
            
        print(f"--- Saldo Margin Akhir: ${MARGIN_BALANCE:,.2f} ---")
    except Exception as e:
        print(f"\n\n💥 Terjadi error fatal: {e}")