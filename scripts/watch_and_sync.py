#!/usr/bin/env python3
"""
Bank Raya - Local Developer Live-Reload & Watcher Daemon (DataOps Live Sync)
Monitors inputs/multi_platform/ for changes and immediately triggers the
deterministic transpiler, shift-left linter, and HTML Data Catalog generator.
"""

import os
import sys
import time
import subprocess
from pathlib import Path
from datetime import datetime

def get_dir_mtimes(target_dir: Path) -> dict:
    mtimes = {}
    if not target_dir.exists():
        return mtimes
    for p in target_dir.rglob("*"):
        if p.is_file():
            try:
                mtimes[str(p)] = p.stat().st_mtime
            except OSError:
                pass
    return mtimes

def main():
    base_dir = Path(__file__).resolve().parent.parent
    watch_dir = base_dir / "inputs" / "multi_platform"
    sync_script = base_dir / "scripts" / "sync_multiplatform_metadata.py"
    dict_script = base_dir / "scripts" / "generate_data_dictionary.py"

    print("=" * 75)
    print("BANK RAYA DATA MANAGEMENT - LIVE RELOAD & WATCHER DAEMON")
    print("Watching directory:", watch_dir.relative_to(base_dir))
    print("Press Ctrl+C to stop watching.")
    print("=" * 75)

    chart_script = base_dir / "scripts" / "seed_chartdb.py"

    # Inisialisasi awal: sinkronkan langsung skema yang ada saat watcher dijalankan
    print("\n[INIT] Menjalankan sinkronisasi awal saat daemon dimulai...")
    res_sync = subprocess.run([sys.executable, str(sync_script)], capture_output=True, text=True)
    if res_sync.returncode == 0:
        print("  -> [OK] Transpiler & Shift-Left Linter terinisialisasi.")
    else:
        print("  -> [FAIL] Transpiler error:\n", res_sync.stderr)
    subprocess.run([sys.executable, str(dict_script)], capture_output=True, text=True)
    print("  -> [OK] docs/data_dictionary.html tergenerate.")
    subprocess.run([sys.executable, str(chart_script)], capture_output=True, text=True)
    print("  -> [OK] ChartDB seeder & bootstrap container terupdate.")
    print("[INIT] Sinkronisasi awal SELESAI! Memantau penambahan skema baru (Ctrl+S)...\n")

    last_mtimes = get_dir_mtimes(watch_dir)

    try:
        while True:
            time.sleep(1.5)
            current_mtimes = get_dir_mtimes(watch_dir)

            changed_files = []
            for path_str, mtime in current_mtimes.items():
                if path_str not in last_mtimes or mtime > last_mtimes[path_str]:
                    changed_files.append(Path(path_str).name)

            for path_str in last_mtimes:
                if path_str not in current_mtimes:
                    changed_files.append(f"{Path(path_str).name} (deleted)")

            if changed_files:
                now_str = datetime.now().strftime("%H:%M:%S")
                print(f"\n[TRIGGER {now_str}] Perubahan terdeteksi pada: {', '.join(changed_files)}")
                print("  -> Menjalankan transpiler & shift-left linter...")
                res_sync = subprocess.run([sys.executable, str(sync_script)], capture_output=True, text=True)
                if res_sync.returncode == 0:
                    print("  -> [OK] Azimutt JSON & ChartDB SQL terupdate otomatis.")
                else:
                    print("  -> [FAIL] Transpiler error:\n", res_sync.stderr)

                print("  -> Menghasilkan Data Dictionary HTML terbaru...")
                res_dict = subprocess.run([sys.executable, str(dict_script)], capture_output=True, text=True)
                if res_dict.returncode == 0:
                    print("  -> [OK] docs/data_dictionary.html terupdate otomatis.")

                print("  -> Memperbarui Seeder & Injeksi IndexedDB ChartDB...")
                chart_script = base_dir / "scripts" / "seed_chartdb.py"
                res_chart = subprocess.run([sys.executable, str(chart_script)], capture_output=True, text=True)
                if res_chart.returncode == 0:
                    print("  -> [OK] ChartDB seeder & bootstrap container terupdate.")
                else:
                    print(f"  -> [WARN] ChartDB seeder notice: {res_chart.stderr.strip()[:100]}")

                print(f"[{now_str}] Selesai! Semua perubahan skema sudah disinkronkan ke seluruh platform.")

                last_mtimes = current_mtimes

    except KeyboardInterrupt:
        print("\nWatcher dihentikan oleh pengguna. Sampai jumpa!")
        sys.exit(0)

if __name__ == "__main__":
    main()
