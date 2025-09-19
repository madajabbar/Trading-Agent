# config.py
import os
from dotenv import load_dotenv
import google.generativeai as genai
from pybit.unified_trading import HTTP

# Muat environment variables dari file .env
load_dotenv()

# Ambil API keys dari environment
BYBIT_API_KEY = os.getenv("BYBIT_API_KEY")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Validasi apakah semua key ada
if not all([BYBIT_API_KEY, BYBIT_API_SECRET, GEMINI_API_KEY]):
    raise ValueError("Pastikan semua API key (BYBIT_API_KEY, BYBIT_API_SECRET, GEMINI_API_KEY) ada di file .env")

# Konfigurasi dan inisialisasi koneksi
try:
    print("🔧 Mengkonfigurasi koneksi API...")
    # Koneksi Bybit
    bybit_session = HTTP(
        testnet=False,
        api_key=BYBIT_API_KEY,
        api_secret=BYBIT_API_SECRET,
    )
    
    # Koneksi Gemini
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-1.5-flash-latest')
    print("✅ Koneksi API berhasil dikonfigurasi.")

except Exception as e:
    raise ConnectionError(f"Gagal mengkonfigurasi koneksi API: {e}")