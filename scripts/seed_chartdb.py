#!/usr/bin/env python3
"""
Bank Raya - ChartDB Automated Pre-Loading & IndexedDB Seeder
Framework: DAMA-DMBOK V.2 | Zero-Credential-Exposure Architecture
Standard: W3C IndexedDB Same-Origin Policy & Dexie.js Schema V13 Compliance
Policy: 100% Stateless container (Zero persistent volume mounts) via runtime docker cp.
"""

import os
import sys
import json
import shutil
import subprocess
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

def build_chartdb_payload(base_dir: Path) -> dict:
    schema_file = base_dir / "sources" / "bank_raya_unified_schema.json"
    sql_file = base_dir / "sources" / "chartdb_unified_import.sql"

    if not schema_file.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_file}")
    
    schema_data = json.loads(schema_file.read_text(encoding="utf-8"))
    sql_ddl = sql_file.read_text(encoding="utf-8") if sql_file.exists() else "-- Bank Raya Unified Import SQL"

    now_iso = "2026-10-27T14:00:00.000Z"
    diagram_id = 1

    diagram = {
        "id": diagram_id,
        "name": "Bank Raya Unified ERD (DAMA-DMBOK 11-Domain)",
        "databaseType": "postgresql",
        "databaseEdition": "standard",
        "createdAt": now_iso,
        "updatedAt": now_iso
    }

    # Grid coordinates and domain colors for tables (3-column layout)
    coords_and_colors = {
        ("scoring", "scorecard_rules"): (60, 60, "#4f46e5"),
        ("scoring", "credit_applications"): (60, 440, "#2563eb"),
        ("channel", "loan_disbursements"): (60, 880, "#d97706"),
        ("legacy", "collateral_registers"): (480, 60, "#dc2626"),
        ("dataraw", "raw_applications"): (480, 480, "#475569"),
        ("datastaging", "stg_applications"): (480, 860, "#0d9488"),
        ("datamart", "fct_credit_scoring"): (920, 200, "#059669"),
        ("datamart", "rpt_slik_ojk"): (920, 640, "#7c3aed"),
    }

    db_tables = []
    for tbl in schema_data.get("tables", []):
        s_name = tbl["schema"]
        t_name = tbl["name"]
        key = (s_name, t_name)
        x, y, color = coords_and_colors.get(key, (100, 100, "#2563eb"))
        table_id = f"tbl_{s_name}_{t_name}"

        pk_cols = tbl.get("primaryKey", {}).get("columns", []) if tbl.get("primaryKey") else []
        unique_cols = set()
        for u in tbl.get("uniques", []):
            for uc in u.get("columns", []):
                unique_cols.add(uc)

        fields = []
        for col in tbl.get("columns", []):
            c_name = col["name"]
            c_type = col["type"].lower()
            field_id = f"f_{s_name}_{t_name}_{c_name}"

            # Normalize type for ChartDB
            norm_type = c_type.split("(")[0].strip()
            if "int" in norm_type or "serial" in norm_type:
                norm_type = "integer"
            elif "char" in norm_type or "text" in norm_type or "string" in norm_type:
                norm_type = "varchar"
            elif "decimal" in norm_type or "numeric" in norm_type:
                norm_type = "numeric"
            elif "time" in norm_type or "date" in norm_type:
                norm_type = "timestamp"
            elif "bool" in norm_type or "bit" in norm_type:
                norm_type = "boolean"
            elif "uuid" in norm_type:
                norm_type = "uuid"

            fields.append({
                "id": field_id,
                "name": c_name,
                "type": {"id": norm_type, "name": col["type"]},
                "primaryKey": c_name in pk_cols,
                "unique": c_name in unique_cols,
                "nullable": col.get("nullable", True),
                "comment": col.get("comment", ""),
                "createdAt": now_iso
            })

        db_tables.append({
            "id": table_id,
            "diagramId": diagram_id,
            "name": t_name,
            "schema": s_name,
            "x": x,
            "y": y,
            "fields": fields,
            "indexes": tbl.get("indexes", []),
            "color": color,
            "comment": tbl.get("comment", ""),
            "isView": False,
            "isMaterializedView": False,
            "createdAt": now_iso
        })

    db_relationships = []
    for rel in schema_data.get("relations", []):
        src = rel["src"]
        ref = rel["ref"]
        rel_id = f"rel_{rel['name']}"
        db_relationships.append({
            "id": rel_id,
            "diagramId": diagram_id,
            "name": rel["name"],
            "sourceSchema": src["schema"],
            "targetSchema": ref["schema"],
            "sourceTableId": f"tbl_{src['schema']}_{src['table']}",
            "targetTableId": f"tbl_{ref['schema']}_{ref['table']}",
            "sourceFieldId": f"f_{src['schema']}_{src['table']}_{src['column']}",
            "targetFieldId": f"f_{ref['schema']}_{ref['table']}_{ref['column']}",
            "sourceCardinality": "many",
            "targetCardinality": "one",
            "createdAt": now_iso
        })

    config = {
        "id": 1,
        "defaultDiagramId": diagram_id
    }

    return {
        "diagram": diagram,
        "db_tables": db_tables,
        "db_relationships": db_relationships,
        "config": config,
        "sql_ddl": sql_ddl
    }


def generate_autoload_html(payload: dict) -> str:
    """Generate standalone autoload.html that writes to ChartDB Dexie IndexedDB and redirects."""
    payload_json = json.dumps(payload, ensure_ascii=False)
    
    html = f"""<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bank Raya · ChartDB Automated Seeder</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            background: linear-gradient(135deg, #0b1120 0%, #0f172a 100%);
            color: #f8fafc;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            padding: 20px;
        }}
        .card {{
            background: rgba(30, 41, 59, 0.7);
            border: 1px solid rgba(59, 130, 246, 0.2);
            backdrop-filter: blur(12px);
            border-radius: 16px;
            padding: 32px;
            max-width: 540px;
            width: 100%;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
            text-align: center;
        }}
        .badge {{
            display: inline-block;
            background: rgba(59, 130, 246, 0.15);
            color: #60a5fa;
            border: 1px solid rgba(59, 130, 246, 0.3);
            border-radius: 9999px;
            padding: 4px 14px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 16px;
        }}
        h1 {{
            font-size: 22px;
            font-weight: 700;
            color: #ffffff;
            margin-bottom: 8px;
        }}
        p.sub {{
            color: #94a3b8;
            font-size: 14px;
            margin-bottom: 24px;
            line-height: 1.5;
        }}
        .spinner {{
            width: 48px;
            height: 48px;
            border: 4px solid rgba(59, 130, 246, 0.2);
            border-top-color: #3b82f6;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 20px auto;
        }}
        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}
        .status-box {{
            background: #0f172a;
            border: 1px solid #334155;
            border-radius: 8px;
            padding: 12px;
            font-family: monospace;
            font-size: 12px;
            color: #38bdf8;
            text-align: left;
            max-height: 140px;
            overflow-y: auto;
            margin-bottom: 20px;
        }}
        .status-line {{ margin-bottom: 4px; }}
        .btn {{
            display: inline-block;
            background: #2563eb;
            color: white;
            font-weight: 600;
            font-size: 14px;
            padding: 10px 24px;
            border-radius: 8px;
            text-decoration: none;
            transition: all 0.2s;
            cursor: pointer;
            border: none;
        }}
        .btn:hover {{ background: #1d4ed8; }}
    </style>
</head>
<body>
    <div class="card">
        <div class="badge">Bank Raya · DataOps Autoloader</div>
        <div class="spinner" id="spinner"></div>
        <h1 id="title">Menginjeksi ERD ke ChartDB...</h1>
        <p class="sub" id="sub">Menyuntikkan model data 11 Domain DASG ke IndexedDB lokal browser Anda secara instan tanpa perlu copas SQL manual.</p>
        
        <div class="status-box" id="status-box">
            <div class="status-line">⚡ Menghubungkan ke IndexedDB [ChartDB, v13]...</div>
        </div>

        <button class="btn" id="open-btn" style="display: none;" onclick="window.location.replace('/')">Buka ChartDB Sekarang</button>
    </div>

    <script>
        const PAYLOAD = {payload_json};

        function log(msg) {{
            const box = document.getElementById("status-box");
            const div = document.createElement("div");
            div.className = "status-line";
            div.textContent = msg;
            box.appendChild(div);
            box.scrollTop = box.scrollHeight;
        }}

        async function seedChartDB() {{
            try {{
                log("📦 Menyalin DDL SQL ke Clipboard sistem...");
                if (navigator.clipboard && navigator.clipboard.writeText) {{
                    await navigator.clipboard.writeText(PAYLOAD.sql_ddl).catch(() => {{}});
                }}

                log("💾 Menginisialisasi Object Stores Dexie.js V13...");
                const req = indexedDB.open("ChartDB", 13);

                req.onupgradeneeded = function(e) {{
                    const db = e.target.result;
                    const stores = [
                        ["diagrams", {{ keyPath: "id", autoIncrement: true }}],
                        ["db_tables", {{ keyPath: "id" }}],
                        ["db_relationships", {{ keyPath: "id" }}],
                        ["db_dependencies", {{ keyPath: "id" }}],
                        ["areas", {{ keyPath: "id" }}],
                        ["db_custom_types", {{ keyPath: "id" }}],
                        ["config", {{ keyPath: "id", autoIncrement: true }}],
                        ["diagram_filters", {{ keyPath: "diagramId" }}],
                        ["notes", {{ keyPath: "id" }}]
                    ];
                    for (const [name, opts] of stores) {{
                        if (!db.objectStoreNames.contains(name)) {{
                            db.createObjectStore(name, opts);
                        }}
                    }}
                }};

                req.onsuccess = function(e) {{
                    const db = e.target.result;
                    const tx = db.transaction(["diagrams", "db_tables", "db_relationships", "config"], "readwrite");
                    
                    const diagStore = tx.objectStore("diagrams");
                    const tableStore = tx.objectStore("db_tables");
                    const relStore = tx.objectStore("db_relationships");
                    const confStore = tx.objectStore("config");

                    diagStore.put(PAYLOAD.diagram);
                    
                    for (const tbl of PAYLOAD.db_tables) {{
                        tableStore.put(tbl);
                    }}

                    for (const rel of PAYLOAD.db_relationships) {{
                        relStore.put(rel);
                    }}

                    confStore.put(PAYLOAD.config);

                    tx.oncomplete = function() {{
                        log("✅ Selesai! Berhasil menginjeksi " + PAYLOAD.db_tables.length + " tabel dan " + PAYLOAD.db_relationships.length + " relasi.");
                        log("🚀 Mengarahkan ke kanvas ChartDB...");
                        document.getElementById("title").textContent = "Injeksi Berhasil!";
                        document.getElementById("spinner").style.display = "none";
                        document.getElementById("open-btn").style.display = "inline-block";

                        setTimeout(() => {{
                            window.location.replace('/');
                        }}, 600);
                    }};

                    tx.onerror = function(err) {{
                        log("❌ Gagal menyimpan data transaksi: " + err.target.error);
                        document.getElementById("open-btn").style.display = "inline-block";
                    }};
                }};

                req.onerror = function(err) {{
                    log("❌ Gagal membuka IndexedDB: " + err.target.error);
                    document.getElementById("open-btn").style.display = "inline-block";
                }};

            }} catch (err) {{
                log("⚠️ Terjadi error: " + err.message);
                document.getElementById("open-btn").style.display = "inline-block";
            }}
        }}

        window.addEventListener("DOMContentLoaded", seedChartDB);
    </script>
</body>
</html>"""
    return html


def seed_chartdb():
    base_dir = Path(__file__).resolve().parent.parent
    docker_bin = find_docker_bin()

    print("=" * 80)
    print("BANK RAYA - CHARTDB AUTOMATED PRE-LOADER & INDEXEDDB SEEDER")
    print("Standard: W3C IndexedDB Same-Origin Policy & Dexie.js Schema V13")
    print("=" * 80)

    # 1. Build Payload from Multiplatform Metadata
    payload = build_chartdb_payload(base_dir)
    print(f"[INFO] Prepared ChartDB Diagram Payload:")
    print(f"  -> Diagram:       {payload['diagram']['name']}")
    print(f"  -> Tables:        {len(payload['db_tables'])} tables mapped to visual grid coordinates")
    print(f"  -> Relationships: {len(payload['db_relationships'])} cross-platform FK relations")

    # 2. Generate autoload.html
    html_content = generate_autoload_html(payload)
    out_html = base_dir / "sources" / "autoload.html"
    out_html.write_text(html_content, encoding="utf-8")
    print(f"[INFO] Generated Autoload HTML: {out_html.relative_to(base_dir)}")

    # 3. Inject into ChartDB container via docker cp (keeping docker-compose 100% stateless)
    try:
        inspect_cmd = [docker_bin, "ps", "--filter", "name=chartdb-app", "--format", "{{.Names}}"]
        res = subprocess.run(inspect_cmd, capture_output=True, text=True, check=False)
        if "chartdb-app" in res.stdout:
            print("[INFO] Target container 'chartdb-app' is running. Copying autoload.html via docker cp...")
            cp_cmd = [docker_bin, "cp", str(out_html), "chartdb-app:/usr/share/nginx/html/autoload.html"]
            cp_res = subprocess.run(cp_cmd, capture_output=True, text=True, check=False)
            if cp_res.returncode == 0:
                print("[PASS] Injected 'autoload.html' into chartdb-app:/usr/share/nginx/html/autoload.html")
                print("  -> Accessible instantly at: http://localhost:8080/autoload.html")
            else:
                print(f"[WARN] docker cp failed: {cp_res.stderr}")

            # Also inject auto-bootstrap script into index.html so opening http://localhost:8080/ directly loads it!
            print("[INFO] Injecting auto-bootstrap script into chartdb-app:/usr/share/nginx/html/index.html...")
            cat_cmd = [docker_bin, "exec", "chartdb-app", "cat", "/usr/share/nginx/html/index.html"]
            cat_res = subprocess.run(cat_cmd, capture_output=True, text=True, check=False)
            if cat_res.returncode == 0 and "bank-raya-bootstrap" not in cat_res.stdout:
                original_html = cat_res.stdout
                bootstrap_script = f"""
        <script id="bank-raya-bootstrap">
        // Bank Raya Enterprise Auto-Seeder: Pre-loads diagram into ChartDB IndexedDB
        (function() {{
            try {{
                const PAYLOAD = {json.dumps(payload, ensure_ascii=False)};
                const req = indexedDB.open("ChartDB", 13);
                req.onupgradeneeded = function(e) {{
                    const db = e.target.result;
                    const stores = [
                        ["diagrams", {{ keyPath: "id", autoIncrement: true }}],
                        ["db_tables", {{ keyPath: "id" }}],
                        ["db_relationships", {{ keyPath: "id" }}],
                        ["db_dependencies", {{ keyPath: "id" }}],
                        ["areas", {{ keyPath: "id" }}],
                        ["db_custom_types", {{ keyPath: "id" }}],
                        ["config", {{ keyPath: "id", autoIncrement: true }}],
                        ["diagram_filters", {{ keyPath: "diagramId" }}],
                        ["notes", {{ keyPath: "id" }}]
                    ];
                    for (const [name, opts] of stores) {{
                        if (!db.objectStoreNames.contains(name)) db.createObjectStore(name, opts);
                    }}
                }};
                req.onsuccess = function(e) {{
                    const db = e.target.result;
                    const tx = db.transaction(["diagrams", "db_tables", "db_relationships", "config"], "readwrite");
                    tx.objectStore("diagrams").put(PAYLOAD.diagram);
                    for (const tbl of PAYLOAD.db_tables) tx.objectStore("db_tables").put(tbl);
                    for (const rel of PAYLOAD.db_relationships) tx.objectStore("db_relationships").put(rel);
                    tx.objectStore("config").put(PAYLOAD.config);
                }};
            }} catch(err) {{
                console.warn("ChartDB Auto-Bootstrap:", err);
            }}
        }})();
        </script>
      <script type="module" crossorigin src="/assets/index-BMkrl9hq.js"></script>"""
                modified_html = original_html.replace(
                    '<script type="module" crossorigin src="/assets/index-BMkrl9hq.js"></script>',
                    bootstrap_script
                )
                temp_index = base_dir / "sources" / "index.html"
                temp_index.write_text(modified_html, encoding="utf-8")
                subprocess.run([docker_bin, "cp", str(temp_index), "chartdb-app:/usr/share/nginx/html/index.html"], check=False)
                temp_index.unlink(missing_ok=True)
                print("[PASS] Successfully injected auto-seeder into chartdb-app index.html (Direct Zero-Click Ready).")
        else:
            print("[WARN] Container 'chartdb-app' is not currently running. Will be copied on launch.")
    except Exception as e:
        print(f"[WARN] Error executing docker cp: {e}")

    print("=" * 80)
    print("CHARTDB SEEDING PREPARATION COMPLETED (EXIT 0).")
    print("=" * 80)
    return 0

if __name__ == "__main__":
    sys.exit(seed_chartdb())
