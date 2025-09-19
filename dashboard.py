import streamlit as st
import pandas as pd
import json
import time
from api_clients import get_latest_price

# --- Konfigurasi Halaman ---
st.set_page_config(
    page_title="Dashboard Agent Trading",
    page_icon="🤖",
    layout="wide"
)

def load_data():
    """Memuat data status terakhir dari file JSON."""
    try:
        with open("live_data.json", "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "margin_balance": 10000,
            "open_positions": {},
            "simulation_log": [],
            "last_update": "N/A"
        }

# --- Judul Dashboard ---
st.title("🤖 Live Dashboard Agent Trading")

# --- Kontainer Utama ---
placeholder = st.empty()

while True:
    data = load_data()
    margin_balance = data.get("margin_balance", 10000)
    open_positions_data = data.get("open_positions", {})
    
    # --- PERUBAHAN DI SINI: Pastikan log dibaca dengan benar ---
    simulation_log_data = data.get("simulation_log", [])
    simulation_log = pd.DataFrame(simulation_log_data)
    
    realized_pnl = 0
    if not simulation_log.empty and 'pnl' in simulation_log.columns:
        realized_pnl = simulation_log[simulation_log['action'] == 'CLOSE']['pnl'].sum()

    total_unrealized_pnl = 0
    positions_list = []
    for symbol, pos_data in open_positions_data.items():
        current_price = get_latest_price(symbol)
        if current_price:
            pnl = (current_price - pos_data['entry_price']) * pos_data['size'] if pos_data['side'] == 'LONG' else (pos_data['entry_price'] - current_price) * pos_data['size']
            total_unrealized_pnl += pnl
            pos_data['unrealized_pnl'] = f"${pnl:,.2f}"
            pos_data['current_price'] = f"${current_price:,.4f}"
        else:
            pos_data['unrealized_pnl'] = "N/A"
            pos_data['current_price'] = "N/A"
        
        pos_data['symbol'] = symbol
        positions_list.append(pos_data)

    with placeholder.container():
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Saldo Margin Saat Ini", f"${margin_balance:,.2f}")
        col2.metric("Total PnL Terealisasi", f"${realized_pnl:,.2f}")
        col3.metric("Posisi Terbuka", len(open_positions_data))
        col4.metric("Total Unrealized PnL", f"${total_unrealized_pnl:,.2f}")
        
        st.markdown("---")

        st.subheader("Posisi Terbuka (Real-time)")
        if not positions_list:
            st.info("Tidak ada posisi yang sedang terbuka.")
        else:
            positions_df = pd.DataFrame(positions_list)
            display_cols = ['symbol', 'side', 'entry_price', 'current_price', 'size', 'margin', 'unrealized_pnl', 'trailing_stop_price']
            st.dataframe(positions_df[display_cols], use_container_width=True)

        # --- BAGIAN UNTUK MENAMPILKAN TRADING LOG ---
        st.subheader("Log Riwayat Trading")
        if simulation_log.empty:
            st.info("Log trading masih kosong.")
        else:
            # Tampilkan log dari yang terbaru ke yang terlama
            st.dataframe(simulation_log.iloc[::-1], use_container_width=True)
            
        st.caption(f"Terakhir diperbarui oleh agent: {data.get('last_update')}")

    time.sleep(5)