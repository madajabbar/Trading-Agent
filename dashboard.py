#dashboard.py
import streamlit as st
import pandas as pd
import json
import time
import os
from typing import Dict, Any, Tuple, List

# Impor fungsi yang relevan
from api_clients import get_latest_price

# --- Konstanta & Konfigurasi ---
STATUS_FILE = "status.json"
POSITIONS_FILE = "positions.csv"
LOG_FILE = "trade_log.csv"
REFRESH_INTERVAL_SECONDS = 5

st.set_page_config(page_title="Dashboard Agent Trading", page_icon="🤖", layout="wide")

@st.cache_data(ttl=REFRESH_INTERVAL_SECONDS)
def load_data_from_local_files() -> Tuple[float, Dict[str, Any], pd.DataFrame]:
    """
    Memuat semua data dari file CSV dan JSON lokal.
    Menggunakan cache Streamlit untuk efisiensi.
    """
    margin_balance = 0.0
    open_positions = {}
    log_df = pd.DataFrame()

    # Muat saldo
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE, "r") as f:
                margin_balance = json.load(f).get("margin_balance", 0.0)
        except Exception as e:
            st.warning(f"Gagal memuat {STATUS_FILE}: {e}")
    
    # Muat posisi
    if os.path.exists(POSITIONS_FILE):
        try:
            pos_df = pd.read_csv(POSITIONS_FILE)
            open_positions = {row['symbol']: row.to_dict() for _, row in pos_df.iterrows()}
        except pd.errors.EmptyDataError:
            # File kosong, ini normal jika tidak ada posisi
            pass
        except Exception as e:
            st.warning(f"Gagal memuat {POSITIONS_FILE}: {e}")
    
    # Muat log
    if os.path.exists(LOG_FILE):
        try:
            log_df = pd.read_csv(LOG_FILE)
        except pd.errors.EmptyDataError:
            pass
        except Exception as e:
            st.warning(f"Gagal memuat {LOG_FILE}: {e}")
            
    return margin_balance, open_positions, log_df

def calculate_metrics(margin_balance: float, open_positions: Dict[str, Any], log_df: pd.DataFrame) -> Tuple[Dict[str, Any], pd.DataFrame]:
    """Menghitung semua metrik KPI dan menyiapkan DataFrame posisi untuk ditampilkan."""
    # 1. Hitung PnL Terealisasi
    realized_pnl = 0.0
    if not log_df.empty and 'pnl' in log_df.columns:
        log_df['pnl'] = pd.to_numeric(log_df['pnl'], errors='coerce').fillna(0)
        realized_pnl = log_df[log_df['action'] == 'CLOSE']['pnl'].sum()

    # 2. Hitung PnL Tidak Terealisasi dan siapkan data posisi
    total_unrealized_pnl = 0.0
    positions_list = []
    for symbol, pos_data in open_positions.items():
        current_price = get_latest_price(symbol)
        display_data = pos_data.copy()
        
        if current_price:
            pnl = (current_price - pos_data['entry_price']) * pos_data['size'] if pos_data['side'] == 'LONG' else (pos_data['entry_price'] - current_price) * pos_data['size']
            total_unrealized_pnl += pnl
            display_data['current_price'] = current_price
            display_data['unrealized_pnl'] = pnl
        else:
            display_data['current_price'] = "N/A"
            display_data['unrealized_pnl'] = 0.0
        
        positions_list.append(display_data)
    
    positions_df = pd.DataFrame(positions_list)

    metrics = {
        "margin_balance": margin_balance,
        "realized_pnl": realized_pnl,
        "num_open_positions": len(open_positions),
        "total_unrealized_pnl": total_unrealized_pnl
    }
    
    return metrics, positions_df

def display_dashboard(metrics: Dict[str, Any], positions_df: pd.DataFrame, log_df: pd.DataFrame):
    """Menampilkan semua elemen UI Streamlit."""
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Saldo Margin Saat Ini", f"${metrics['margin_balance']:,.2f}")
    col2.metric("Total PnL Terealisasi", f"${metrics['realized_pnl']:,.2f}")
    col3.metric("Posisi Terbuka", metrics['num_open_positions'])
    col4.metric("Total Unrealized PnL", f"${metrics['total_unrealized_pnl']:,.2f}")
    
    st.markdown("---")

    st.subheader("Posisi Terbuka (Real-time)")
    if positions_df.empty:
        st.info("Tidak ada posisi yang sedang terbuka.")
    else:
        positions_df['unrealized_pnl_display'] = positions_df['unrealized_pnl'].apply(lambda x: f"${x:,.2f}")
        
        # Tampilkan kolom secara dinamis agar tidak error jika ada yang hilang
        base_cols = ['symbol', 'side', 'entry_price', 'current_price', 'margin', 'unrealized_pnl_display']
        optional_cols = ['stop_loss_price', 'take_profit_price']
        
        display_cols = base_cols + [col for col in optional_cols if col in positions_df.columns]
        st.dataframe(positions_df[display_cols], use_container_width=True)

    st.subheader("Log Riwayat Trading")
    if log_df.empty:
        st.info("Log trading masih kosong.")
    else:
        # Urutkan berdasarkan timestamp untuk tampilan yang benar
        log_df['timestamp'] = pd.to_datetime(log_df['timestamp'])
        st.dataframe(log_df.sort_values(by='timestamp', ascending=False), use_container_width=True)
        
    st.caption(f"Dashboard diperbarui setiap {REFRESH_INTERVAL_SECONDS} detik.")

def main():
    """Fungsi utama untuk menjalankan loop dashboard."""
    st.title("🤖 Live Dashboard Agent Trading (Lokal)")
    placeholder = st.empty()

    while True:
        with placeholder.container():
            margin_balance, open_positions, log_df = load_data_from_local_files()
            metrics, positions_df = calculate_metrics(margin_balance, open_positions, log_df)
            display_dashboard(metrics, positions_df, log_df)
        
        time.sleep(REFRESH_INTERVAL_SECONDS)

if __name__ == "__main__":
    main()