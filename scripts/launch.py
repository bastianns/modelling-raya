#!/usr/bin/env python3
"""
Bank Raya - Enterprise Data Architecture & DataOps Master Orchestrator
Framework: DAMA-DMBOK V.2 | Zero-Credential-Exposure Architecture
Automates end-to-end multi-platform sync, seeding, validation, and dashboard launch.
Usage:
    python scripts/launch.py
    python scripts/launch.py --no-browser
"""

import os
import sys
import time
import shutil
import argparse
import subprocess
import webbrowser
from pathlib import Path

def find_docker_bin() -> str:
    """Find docker executable across system paths."""
    docker_in_path = shutil.which("docker")
    if docker_in_path:
        return docker_in_path
    common_paths = [
        Path(r"C:\Program Files\Docker\Docker\resources\bin\docker.exe"),
        Path(r"C:\Program Files\Docker\Docker\resources\docker.exe"),
        Path(os.environ.get("LOCALAPPDATA", "")) / "Docker" / "resources" / "bin" / "docker.exe"
    ]
    for p in common_paths:
        if p.exists():
            return str(p)
    return "docker"

def run_step(step_num: int, title: str, cmd_list: list, cwd: Path) -> bool:
    print(f"\n[{step_num}/6] {title}...")
    print(f"  CMD: {' '.join(str(c) for c in cmd_list)}")
    try:
        res = subprocess.run(
            cmd_list,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=False
        )
        if res.returncode == 0:
            print(f"  [PASS] {title} completed successfully.")
            return True
        else:
            print(f"  [FAIL] {title} exited with code {res.returncode}:")
            if res.stdout:
                print("  STDOUT:\n" + "\n".join("    " + line for line in res.stdout.strip().splitlines()[-10:]))
            if res.stderr:
                print("  STDERR:\n" + "\n".join("    " + line for line in res.stderr.strip().splitlines()[-10:]))
            return False
    except Exception as e:
        print(f"  [FAIL] Exception executing {title}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Bank Raya Enterprise Data Architecture Launcher")
    parser.add_argument("--no-browser", action="store_true", help="Do not launch web browsers after initialization (for CI/CD)")
    parser.add_argument("--skip-docker", action="store_true", help="Skip docker compose up --build check")
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent.parent
    py_exec = sys.executable
    docker_bin = find_docker_bin()

    print("=" * 80)
    print("BANK RAYA ENTERPRISE DATA ARCHITECTURE - SINGLE MASTER ORCHESTRATOR")
    print("Standard: DAMA-DMBOK V.2 | Zero-Credential-Exposure | SSoT Deduplication")
    print("=" * 80)

    # -------------------------------------------------------------------------
    # Step 1: Run Multi-Platform Transpiler & Shift-Left Linter
    # -------------------------------------------------------------------------
    step1_cmd = [py_exec, str(base_dir / "scripts" / "sync_multiplatform_metadata.py")]
    if not run_step(1, "Syncing Multi-Platform Metadata & Running Shift-Left Linter", step1_cmd, base_dir):
        print("\n[ERROR] Step 1 failed. Aborting launch.")
        return 1

    # -------------------------------------------------------------------------
    # Step 2: Generate ChartDB Autoload HTML (Pre-Bake)
    # -------------------------------------------------------------------------
    step2_cmd = [py_exec, str(base_dir / "scripts" / "seed_chartdb.py"), "--generate-only"]
    if not run_step(2, "Generating ChartDB Autoload Seeder Payload", step2_cmd, base_dir):
        print("\n[ERROR] Step 2 failed. Aborting launch.")
        return 1

    # -------------------------------------------------------------------------
    # Step 3: Build & Start Containers (SSoT Bake via Docker Compose)
    # -------------------------------------------------------------------------
    if not args.skip_docker:
        step3_cmd = [docker_bin, "compose", "up", "-d", "--build"]
        if not run_step(3, "Building & Starting Containers (docker compose up -d --build)", step3_cmd, base_dir):
            print("\n[ERROR] Step 3 failed. Aborting launch.")
            return 1
    else:
        print("\n[3/6] Skipping Docker compose build & start (--skip-docker).")

    # -------------------------------------------------------------------------
    # Step 4: Generate Interactive Standalone Data Catalog & Mermaid ERD
    # -------------------------------------------------------------------------
    step4_cmd = [py_exec, str(base_dir / "scripts" / "generate_data_dictionary.py")]
    if not run_step(4, "Generating Standalone Data Dictionary & ERD Catalog", step4_cmd, base_dir):
        print("\n[ERROR] Step 4 failed. Aborting launch.")
        return 1

    # -------------------------------------------------------------------------
    # Step 5: Run Azimutt Project Pre-Seeding (Database & Samples)
    # -------------------------------------------------------------------------
    step5_cmd = [py_exec, str(base_dir / "scripts" / "seed_azimutt.py")]
    if not run_step(5, "Pre-Seeding Azimutt Database & Domain Layouts", step5_cmd, base_dir):
        print("\n[ERROR] Step 5 failed. Aborting launch.")
        return 1

    # -------------------------------------------------------------------------
    # Step 6: Verify System Compliance (27+ Banking Grade Assertions)
    # -------------------------------------------------------------------------
    step6_cmd = [py_exec, str(base_dir / "scripts" / "verify_setup.py")]
    if not run_step(6, "Validating EDM Compliance & Security Assertions", step6_cmd, base_dir):
        print("\n[ERROR] Step 6 compliance check failed. Aborting launch.")
        return 1

    # -------------------------------------------------------------------------
    # Launch Web Browsers
    # -------------------------------------------------------------------------
    html_catalog_path = (base_dir / "docs" / "data_dictionary.html").resolve()
    chartdb_url = "http://localhost:8080"
    chartdb_autoload_url = "http://localhost:8080/autoload.html"
    azimutt_project_url = "http://localhost:8000/22222222-2222-4222-8222-222222222222/00000000-0000-4000-8000-000000000001"
    azimutt_login_url = "http://localhost:8000/login"

    print("\n" + "=" * 80)
    print("ALL DATA ARCHITECTURE SYSTEMS READY & SYNCHRONIZED!")
    print("=" * 80)
    print(f"1. Data Dictionary & Catalog:    {html_catalog_path.as_uri()}")
    print(f"2. ChartDB Canvas:               {chartdb_url}")
    print(f"   (Direct Autoload Seeder:       {chartdb_autoload_url})")
    print(f"3. Azimutt Project Portal:       {azimutt_login_url}")
    print(f"   -> Akun Admin / Owner:        bastiannatanaels@gmail.com")
    print(f"   (Private Project Canvas:      {azimutt_project_url})")
    print("=" * 80)

    if not args.no_browser:
        print("\n[INFO] Opening workspaces in your default browser...")
        try:
            webbrowser.open(html_catalog_path.as_uri())
            time.sleep(0.5)
            webbrowser.open(chartdb_autoload_url)
            time.sleep(0.5)
            webbrowser.open(azimutt_login_url)
            print("[PASS] Browsers launched successfully.")
        except Exception as e:
            print(f"[WARN] Could not automatically open browser: {e}")
            print("  Please open the URLs above manually.")
    else:
        print("\n[INFO] Headless mode enabled (--no-browser). Browser launch skipped.")

    print("\n[SUCCESS] Bank Raya Enterprise DataOps Pipeline executed with 0 errors (Exit 0).")
    return 0

if __name__ == "__main__":
    sys.exit(main())
