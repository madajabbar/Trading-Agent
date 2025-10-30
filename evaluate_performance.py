# evaluate_performance.py
import pandas as pd
import os
from typing import Optional

LOG_FILE = "trade_log.csv"

def evaluate_trading_performance():
    if not os.path.exists(LOG_FILE):
        print(f"❌ File {LOG_FILE} tidak ditemukan.")
        return

    try:
        df = pd.read_csv(LOG_FILE)
    except Exception as e:
        print(f"❌ Gagal membaca {LOG_FILE}: {e}")
        return

    if df.empty:
        print("ℹ️ Tidak ada data trading untuk dievaluasi.")
        return

    # Pastikan kolom 'pnl' ada dan numerik
    if 'pnl' not in df.columns:
        print("❌ Kolom 'pnl' tidak ditemukan di log.")
        return

    df['pnl'] = pd.to_numeric(df['pnl'], errors='coerce')
    df = df.dropna(subset=['pnl'])

    if df.empty:
        print("ℹ️ Tidak ada data PnL yang valid.")
        return

    total_trades = len(df)
    winning_trades = df[df['pnl'] > 0]
    losing_trades = df[df['pnl'] <= 0]

    win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
    total_pnl = df['pnl'].sum()
    avg_pnl = df['pnl'].mean()
    avg_win = winning_trades['pnl'].mean() if not winning_trades.empty else 0
    avg_loss = losing_trades['pnl'].mean() if not losing_trades.empty else 0
    max_win = df['pnl'].max()
    max_loss = df['pnl'].min()

    # Hitung Profit Factor (opsional tapi penting)
    gross_profit = winning_trades['pnl'].sum() if not winning_trades.empty else 0
    gross_loss = abs(losing_trades['pnl'].sum()) if not losing_trades.empty else 0.001  # hindari div by zero
    profit_factor = gross_profit / gross_loss

    # Tampilkan hasil
    print("=" * 60)
    print("📊 EVALUASI KINERJA TRADING (DRY RUN)")
    print("=" * 60)
    print(f"📈 Total Trade          : {total_trades}")
    print(f"✅ Win Rate             : {win_rate:.2%}")
    print(f"💰 Total PnL            : ${total_pnl:.4f}")
    print(f"📊 Rata-rata PnL        : ${avg_pnl:.4f}")
    print(f"🟢 Rata-rata Profit     : ${avg_win:.4f}")
    print(f"🔴 Rata-rata Rugi       : ${avg_loss:.4f}")
    print(f"🔝 Max Profit           : ${max_win:.4f}")
    print(f"🔻 Max Rugi             : ${max_loss:.4f}")
    print(f"⚙️ Profit Factor        : {profit_factor:.2f}")
    print("-" * 60)

    # Rekomendasi berdasarkan data
    if win_rate < 0.45:
        print("⚠️  REKOMENDASI: Win rate terlalu rendah (<45%).")
        print("   → Strategi saat ini TIDAK LAYAK untuk live trading.")
        print("   → Saran: Ganti ke strategi berbasis tren + volume (lihat versi baru strategy.py).")
    elif avg_pnl < 0:
        print("⚠️  REKOMENDASI: Rata-rata PnL negatif.")
        print("   → Meski win rate tinggi, rugi per trade terlalu besar.")
        print("   → Perbesar rasio TP:SL (minimal 3:1).")
    elif profit_factor < 1.2:
        print("⚠️  REKOMENDASI: Profit Factor < 1.2 → sistem belum stabil.")
        print("   → Kumpulkan lebih banyak data (>50 trade) sebelum keputusan akhir.")
    else:
        print("✅ REKOMENDASI: Performa MENJANJIKAN!")
        print("   → Pertimbangkan uji coba lebih lama atau live trading kecil-kecilan.")

    print("=" * 60)

if __name__ == "__main__":
    evaluate_trading_performance()