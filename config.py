#config.py
import os
import json
from typing import Dict, Any

from dotenv import load_dotenv
from pybit.unified_trading import HTTP

def load_settings(file_path: str = "settings.json") -> Dict[str, Any]:
    """Memuat, memvalidasi, dan mengembalikan pengaturan dari file JSON."""
    print(f"⚙️ Memuat pengaturan dari {file_path}...")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File pengaturan '{file_path}' tidak ditemukan.")
    
    try:
        with open(file_path, "r") as f:
            settings = json.load(f)
        print("✅ Pengaturan berhasil dimuat.")
        return settings
    except json.JSONDecodeError:
        raise ValueError(f"File '{file_path}' tidak dalam format JSON yang valid.")

def initialize_bybit_client(api_keys: Dict[str, str]) -> HTTP:
    """Menginisialisasi dan mengembalikan klien API untuk Bybit."""
    print("🔧 Mengkonfigurasi koneksi Bybit...")
    try:
        bybit_client = HTTP(
            testnet=False,  # Ganti ke True jika ingin kembali ke simulasi testnet
            api_key=api_keys['bybit_key'],
            api_secret=api_keys['bybit_secret'],
        )
        print("✅ Koneksi Bybit berhasil dikonfigurasi.")
        return bybit_client
    except Exception as e:
        raise ConnectionError(f"Gagal menginisialisasi klien Bybit: {e}")

# --- EKSEKUSI UTAMA ---
load_dotenv()

API_KEYS = {
    "bybit_key": os.getenv("BYBIT_API_KEY"),
    "bybit_secret": os.getenv("BYBIT_API_SECRET"),
}

if not all(API_KEYS.values()):
    raise ValueError("Pastikan BYBIT_API_KEY dan BYBIT_API_SECRET ada di file .env")

SETTINGS = load_settings()
bybit_session = initialize_bybit_client(API_KEYS)