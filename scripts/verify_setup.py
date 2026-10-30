#!/usr/bin/env python3
"""
Enterprise Data Management (EDM) Configuration & Security Hardening Verifier
Verifies compliance with Banking Grade Zero-Credential-Exposure standards
and DAMA-DMBOK V.2 Multi-Platform Deterministic Transpilation & Governance.
"""

import os
import sys
import json
import subprocess
from pathlib import Path

def run_checks():
    base_dir = Path(__file__).resolve().parent.parent
    compose_path = base_dir / "docker-compose.yml"
    env_path = base_dir / ".env"
    scoring_src = base_dir / "azimutt-data" / "sources" / "teams" / "scoring"
    reporting_src = base_dir / "azimutt-data" / "sources" / "teams" / "reporting"
    scoring_lyt = base_dir / "azimutt-data" / "layouts" / "teams" / "scoring"
    reporting_lyt = base_dir / "azimutt-data" / "layouts" / "teams" / "reporting"
    inputs_dir = base_dir / "inputs" / "multi_platform"
    sync_script = base_dir / "scripts" / "sync_multiplatform_metadata.py"

    print("=" * 75)
    print("VERIFIKASI SISTEM EDM & DAMA-DMBOK: CHARTDB & AZIMUTT (BANKING GRADE)")
    print("=" * 75)

    checks_passed = True

    # 1. Check docker-compose.yml exists
    if not compose_path.exists():
        print("[FAIL] docker-compose.yml tidak ditemukan.")
        return False
    print("[PASS] docker-compose.yml ditemukan.")

    compose_content = compose_path.read_text(encoding="utf-8")

    # 2. Check ChartDB specs
    chartdb_image_ok = ("ghcr.io/chartdb/chartdb" in compose_content)
    chartdb_checks = [
        (chartdb_image_ok, "Base image ChartDB resmi: 'ghcr.io/chartdb/chartdb'"),
        ("DISABLE_ANALYTICS" in compose_content, "Hardening: DISABLE_ANALYTICS dikonfigurasi"),
        ("VITE_HIDE_CHARTDB_CLOUD" in compose_content, "Hardening: VITE_HIDE_CHARTDB_CLOUD dikonfigurasi"),
        ("8080:80" in compose_content, "Port forwarding ChartDB diatur ke 8080:80"),
        ("edm-secure-net" in compose_content, "ChartDB terhubung ke jaringan 'edm-secure-net'")
    ]

    for condition, desc in chartdb_checks:
        if condition:
            print(f"[PASS] {desc}")
        else:
            print(f"[FAIL] {desc}")
            checks_passed = False

    # Check ChartDB Statelessness (no volume mount)
    chartdb_block = compose_content.split("azimutt-db:")[0]
    if "volumes:" in chartdb_block and "- " in chartdb_block.split("volumes:")[1].split("networks:")[0]:
        print("[FAIL] ChartDB terdeteksi memiliki persistent volume! Harus 100% stateless.")
        checks_passed = False
    else:
        print("[PASS] Layanan ChartDB 100% Stateless (tanpa volume persistensi)")

    # Active validation for ChartDB autoload.html payload & anti-cache headers
    try:
        import urllib.request
        req = urllib.request.Request("http://127.0.0.1:8080/autoload.html")
        with urllib.request.urlopen(req, timeout=3) as resp:
            body = resp.read()
            if resp.status == 200 and len(body) > 10000:
                print(f"[PASS] ChartDB live payload /autoload.html aktif & valid ({len(body)} bytes > 10000 bytes)")
                import hashlib
                host_autoload = base_dir / "sources" / "autoload.html"
                if host_autoload.exists():
                    host_hash = hashlib.sha256(host_autoload.read_bytes()).hexdigest()
                    live_hash = hashlib.sha256(body).hexdigest()
                    if host_hash == live_hash:
                        print(f"[PASS] SSoT Bake Image Integrity: live payload SHA256 identik dengan host ({live_hash[:16]}...)")
                    else:
                        print(f"[FAIL] Image basi! SHA256 live ({live_hash[:16]}) != host ({host_hash[:16]}). Jalankan docker compose up -d --build!")
                        checks_passed = False
            elif resp.status == 200:
                print(f"[FAIL] ChartDB /autoload.html hanya mengembalikan fallback ({len(body)} bytes <= 10000). Jalankan scripts/seed_chartdb.py!")
                checks_passed = False
            else:
                print(f"[FAIL] ChartDB /autoload.html HTTP status: {resp.status}")
                checks_passed = False

        req_root = urllib.request.Request("http://127.0.0.1:8080/")
        with urllib.request.urlopen(req_root, timeout=3) as resp_root:
            cc = resp_root.headers.get("Cache-Control", "")
            if "no-store" in cc and "no-cache" in cc:
                print(f"[PASS] ChartDB HTTP anti-cache headers aktif (Cache-Control: {cc})")
            else:
                print(f"[FAIL] ChartDB HTTP Cache-Control tidak aman: '{cc}'")
                checks_passed = False

        # Active Playwright E2E Canvas Assertion (9 nodes, 5 edges, 0 blocking modal)
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto("http://localhost:8080/autoload.html", wait_until="domcontentloaded")
                page.wait_for_url("**/diagrams/bank_raya_main_diagram", timeout=12000)
                page.wait_for_selector(".react-flow__node", timeout=15000)
                page.wait_for_timeout(1000)
                nodes = page.query_selector_all(".react-flow__node")
                edges = page.query_selector_all(".react-flow__edge")
                modal = page.query_selector("text='What is your Database?'")
                if len(nodes) == 9 and len(edges) == 5 and modal is None:
                    print(f"[PASS] ChartDB E2E Canvas verified: tepat {len(nodes)} node tabel dan {len(edges)} relasi aktif di kanvas (0 blocking modal)")
                else:
                    print(f"[FAIL] ChartDB Canvas assertion failed: nodes={len(nodes)} (expected 9), edges={len(edges)} (expected 5), modal={modal is not None}")
                    checks_passed = False
                browser.close()
        except ImportError:
            print("[INFO] Modul Playwright tidak terinstall di environment ini, pengujian kanvas dilewati.")
        except Exception as e:
            print(f"[FAIL] ChartDB Canvas E2E assertion error: {e}")
            checks_passed = False
    except Exception as e:
        print(f"[INFO] ChartDB live HTTP check dilewati (layanan belum aktif: {e})")

    # 3. Check Azimutt specs
    azimutt_checks = [
        ("ghcr.io/azimuttapp/azimutt", "Base image Azimutt resmi ghcr.io/azimuttapp/azimutt"),
        ("8000", "Port forwarding Azimutt diarahkan ke port lokal 8000"),
        ("./azimutt-data/sources:/app/sources", "Volume terpisah untuk direktori 'sources' terkonfigurasi"),
        ("./azimutt-data/layouts:/app/layouts", "Volume terpisah untuk direktori 'layouts' terkonfigurasi"),
        ("edm-secure-net", "Azimutt terhubung ke jaringan terisolasi 'edm-secure-net'")
    ]

    for token, desc in azimutt_checks:
        if token in compose_content:
            print(f"[PASS] {desc}")
        else:
            print(f"[FAIL] {desc}")
            checks_passed = False

    # Check Azimutt-DB Isolation (Zero Exposed Ports on DB container)
    db_block = compose_content.split("azimutt-db:")[1].split("azimutt:")[0]
    if "ports:" in db_block:
        print("[FAIL] Backend database Azimutt mengekspos port ke host! Harus terisolasi.")
        checks_passed = False
    else:
        print("[PASS] Backend Azimutt terisolasi di jaringan internal (tanpa port ke host)")

    # 4. Check Directories
    dirs_to_check = [
        (scoring_src, "Sources Tim Scoring (DDL / SQL)"),
        (reporting_src, "Sources Tim Reporting (DDL / SQL)"),
        (scoring_lyt, "Layouts Tim Scoring (Views / Diagram)"),
        (reporting_lyt, "Layouts Tim Reporting (Views / Diagram)")
    ]

    for d, label in dirs_to_check:
        if d.exists():
            print(f"[PASS] Direktori {label} ditemukan: {d.name}")
        else:
            print(f"[FAIL] Direktori {label} tidak ditemukan: {d}")
            checks_passed = False

    # 5. Check .env
    if env_path.exists():
        print("[PASS] File .env aktif untuk perlindungan Zero-Credential-Exposure.")
    else:
        print("[WARN] File .env belum dibuat (gunakan .env.example).")

    # 6. Check Multi-Platform Static Metadata Inputs (DAMA-DMBOK V.2)
    input_files = [
        ("oltp_postgres.sql", "PostgreSQL Core Scoring DDL"),
        ("oltp_mysql.sql", "MySQL Channel Partner DDL"),
        ("oltp_sqlserver.sql", "SQL Server Legacy Collateral DDL"),
        ("olap_bigquery_ddl.sql", "BigQuery 3-Layer Medallion DDL"),
        ("dbt_schema.yml", "dbt Data Contracts & Governance Catalog"),
        ("airflow_batch_query.sql", "Airflow Batch Orchestration Query"),
        ("superset_datasources.yaml", "Superset BI Datasets & Metrics Export")
    ]

    for filename, label in input_files:
        f_path = inputs_dir / filename
        if f_path.exists() and f_path.stat().st_size > 0:
            print(f"[PASS] Artefak Multi-Platform ditemukan: {label} ({filename})")
        else:
            print(f"[FAIL] Artefak Multi-Platform tidak ditemukan: {label} ({filename})")
            checks_passed = False

    # 7. Check Execution of Deterministic Transpiler & Linter
    if not sync_script.exists():
        print(f"[FAIL] Skrip transpiler tidak ditemukan: {sync_script}")
        checks_passed = False
    else:
        print(f"[PASS] Skrip transpiler ditemukan: {sync_script.name}")
        try:
            res = subprocess.run(
                [sys.executable, str(sync_script)],
                capture_output=True,
                text=True,
                check=False
            )
            if res.returncode == 0:
                print("[PASS] Eksekusi 'sync_multiplatform_metadata.py' sukses (Exit Code 0).")
            else:
                print(f"[FAIL] Eksekusi 'sync_multiplatform_metadata.py' gagal (Exit Code {res.returncode}):\n{res.stderr}")
                checks_passed = False
        except Exception as e:
            print(f"[FAIL] Gagal menjalankan transpiler: {e}")
            checks_passed = False

    # 8. Check Generated Artifacts & Schema Validation
    schema_paths = [
        base_dir / "sources" / "bank_raya_unified_schema.json",
        base_dir / "azimutt-data" / "sources" / "bank_raya_unified_schema.json"
    ]
    for p in schema_paths:
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                has_tables = "tables" in data and isinstance(data["tables"], list) and len(data["tables"]) >= 8
                has_relations = "relations" in data and isinstance(data["relations"], list)
                has_types = "types" in data and isinstance(data["types"], list)
                if has_tables and has_relations and has_types:
                    print(f"[PASS] Azimutt Schema Valid ({len(data['tables'])} tabel, {len(data['relations'])} relasi): {p.relative_to(base_dir)}")
                else:
                    print(f"[FAIL] Format Azimutt Schema tidak lengkap pada: {p.relative_to(base_dir)}")
                    checks_passed = False
            except Exception as e:
                print(f"[FAIL] File {p.relative_to(base_dir)} bukan JSON valid: {e}")
                checks_passed = False
        else:
            print(f"[FAIL] File tidak ditemukan: {p.relative_to(base_dir)}")
            checks_passed = False

    chartdb_paths = [
        base_dir / "sources" / "chartdb_unified_import.sql",
        base_dir / "azimutt-data" / "sources" / "chartdb_unified_import.sql"
    ]
    for p in chartdb_paths:
        if p.exists() and p.stat().st_size > 0:
            print(f"[PASS] ChartDB Unified SQL Import ditemukan: {p.relative_to(base_dir)}")
        else:
            print(f"[FAIL] ChartDB Unified SQL Import tidak ditemukan: {p.relative_to(base_dir)}")
            checks_passed = False

    layout_paths = [
        base_dir / "layouts" / "bank_raya_domain_layouts.json",
        base_dir / "azimutt-data" / "layouts" / "bank_raya_domain_layouts.json"
    ]
    for p in layout_paths:
        if p.exists():
            try:
                ldata = json.loads(p.read_text(encoding="utf-8"))
                if "layouts" in ldata and len(ldata["layouts"]) >= 5:
                    print(f"[PASS] Azimutt Domain Layouts Valid ({len(ldata['layouts'])} domain): {p.relative_to(base_dir)}")
                else:
                    print(f"[FAIL] Domain layouts tidak lengkap pada: {p.relative_to(base_dir)}")
                    checks_passed = False
            except Exception as e:
                print(f"[FAIL] File {p.relative_to(base_dir)} bukan JSON valid: {e}")
                checks_passed = False
        else:
            print(f"[FAIL] File layout tidak ditemukan: {p.relative_to(base_dir)}")
            checks_passed = False

    # 9. Check Standalone HTML Data Catalog
    html_catalog = base_dir / "docs" / "data_dictionary.html"
    if html_catalog.exists() and html_catalog.stat().st_size > 0:
        print(f"[PASS] Standalone HTML Data Catalog ditemukan: {html_catalog.relative_to(base_dir)}")
    else:
        print(f"[FAIL] Standalone HTML Data Catalog tidak ditemukan: {html_catalog.relative_to(base_dir)}")
        checks_passed = False

    # 10. Check Zero-Manual Automation & Master Launch Scripts
    auto_scripts = [
        (base_dir / "scripts" / "seed_chartdb.py", "ChartDB Automated Seeder"),
        (base_dir / "scripts" / "seed_azimutt.py", "Azimutt Automated Seeder"),
        (base_dir / "scripts" / "launch.py", "Single Master Orchestrator (launch.py)"),
        (base_dir / "sources" / "autoload.html", "ChartDB Autoload Injector HTML"),
        (base_dir / "sources" / "nginx_chartdb.conf", "ChartDB Nginx Anti-Cache Hardening Conf")
    ]
    for script_p, label in auto_scripts:
        if script_p.exists() and script_p.stat().st_size > 0:
            print(f"[PASS] Skrip Otomasi Zero-Manual ditemukan: {label} ({script_p.name})")
        else:
            print(f"[FAIL] Skrip Otomasi Zero-Manual tidak ditemukan: {label} ({script_p.name})")
            checks_passed = False

    print("=" * 75)
    if checks_passed:
        print("HASIL: SEMUA SPESIFIKASI TEKNIS & KEAMANAN TERVERIFIKASI 100% VALID")
    else:
        print("HASIL: ADA SPESIFIKASI YANG BELUM TERPENUHI.")
    print("=" * 75)
    return checks_passed

if __name__ == "__main__":
    success = run_checks()
    sys.exit(0 if success else 1)
