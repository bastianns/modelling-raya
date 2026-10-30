#!/usr/bin/env python3
"""
Bank Raya - ChartDB Automated Pre-Loader & IndexedDB Seeder
Framework: DAMA-DMBOK V.2 | Zero-Credential-Exposure Architecture
Standard: W3C IndexedDB Same-Origin Policy & Dexie.js Schema V13 (IDB Version 130) Compliance
Policy: 100% Stateless container via pre-built thin image (SSoT Bake).

NOTE P2: IndexedDB bersifat per-origin!
Pastikan selalu mengakses http://localhost:8080 (bukan 127.0.0.1:8080), karena origin
berbeda memiliki database IndexedDB terpisah.
"""

import os
import sys
import json
import shutil
import hashlib
import argparse
import subprocess
import urllib.request
from pathlib import Path

DIAGRAM_ID = "bank_raya_main_diagram"

EXACT_TYPE_MAPPING = {
    "uuid": "uuid",
    "varchar": "varchar",
    "nvarchar": "varchar",
    "string": "varchar",
    "text": "varchar",
    "char": "char",
    "int": "integer",
    "int2": "integer",
    "int4": "integer",
    "integer": "integer",
    "serial": "integer",
    "bigint": "bigint",
    "int64": "bigint",
    "int8": "bigint",
    "numeric": "numeric",
    "decimal": "numeric",
    "float": "numeric",
    "double": "numeric",
    "timestamp": "timestamp",
    "timestamptz": "timestamp",
    "datetime": "timestamp",
    "datetime2": "timestamp",
    "date": "timestamp",
    "boolean": "boolean",
    "bool": "boolean",
    "bit": "bit",
    "json": "json",
    "jsonb": "json",
}

def map_column_type(raw_type: str) -> dict:
    clean = raw_type.lower().split("(")[0].split()[0].strip()
    norm_id = EXACT_TYPE_MAPPING.get(clean, clean)
    return {"id": norm_id, "name": raw_type}

def find_docker_bin() -> str:
    """Find docker executable across system paths or fallback to WSL."""
    try:
        check = subprocess.run(["docker", "ps"], capture_output=True, text=True, check=False)
        if check.returncode == 0:
            return "docker"
    except Exception:
        pass

    docker_in_path = shutil.which("docker")
    if docker_in_path:
        try:
            check = subprocess.run([docker_in_path, "ps"], capture_output=True, text=True, check=False)
            if check.returncode == 0:
                return docker_in_path
        except Exception:
            pass

    try:
        check = subprocess.run(["wsl", "-d", "Ubuntu", "-e", "docker", "ps"], capture_output=True, text=True, check=False)
        if check.returncode == 0:
            return "wsl -d Ubuntu -e docker"
    except Exception:
        pass

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

    created_timestamp_num = 1730246400000

    diagram = {
        "id": DIAGRAM_ID,
        "name": "Bank Raya Unified ERD (DAMA-DMBOK 11-Domain)",
        "databaseType": "postgresql",
        "databaseEdition": None
    }

    # Grid coordinates and domain colors for tables (3-column layout)
    coords_and_colors = {
        ("scoring", "scorecard_rules"): (60, 60, "#4f46e5"),
        ("scoring", "credit_applications"): (60, 440, "#2563eb"),
        ("scoring", "fraud_audit_events"): (60, 880, "#1d4ed8"),
        ("channel", "loan_disbursements"): (60, 1260, "#d97706"),
        ("legacy", "collateral_registers"): (480, 60, "#dc2626"),
        ("dataraw", "raw_applications"): (480, 480, "#475569"),
        ("datastaging", "stg_applications"): (480, 860, "#0d9488"),
        ("datamart", "fct_credit_scoring"): (920, 200, "#059669"),
        ("datamart", "rpt_slik_ojk"): (920, 640, "#7c3aed"),
    }

    db_tables = []
    unmapped_count = 0
    for tbl_idx, tbl in enumerate(schema_data.get("tables", [])):
        s_name = tbl["schema"]
        t_name = tbl["name"]
        key = (s_name, t_name)
        if key in coords_and_colors:
            x, y, color = coords_and_colors[key]
        else:
            col = unmapped_count // 3
            row = unmapped_count % 3
            x = 1360 + (col * 400)
            y = 60 + (row * 380)
            color = "#0284c7"
            unmapped_count += 1

        table_id = f"tbl_{s_name}_{t_name}"

        pk_cols = tbl.get("primaryKey", {}).get("columns", []) if tbl.get("primaryKey") else []
        unique_cols = set()
        for u in tbl.get("uniques", []):
            for uc in u.get("columns", []):
                unique_cols.add(uc)

        fields = []
        for col in tbl.get("columns", []):
            c_name = col["name"]
            field_id = f"f_{s_name}_{t_name}_{c_name}"

            fields.append({
                "id": field_id,
                "name": c_name,
                "type": map_column_type(col["type"]),
                "primaryKey": c_name in pk_cols,
                "unique": c_name in unique_cols,
                "nullable": col.get("nullable", True),
                "comment": col.get("comment", ""),
                "createdAt": created_timestamp_num
            })

        indexes = []
        if pk_cols:
            indexes.append({
                "id": f"idx_pk_{s_name}_{t_name}",
                "name": "PRIMARY",
                "unique": True,
                "isPrimaryKey": True,
                "fieldIds": [f"f_{s_name}_{t_name}_{c}" for c in pk_cols],
                "createdAt": created_timestamp_num
            })
        for u in tbl.get("uniques", []):
            indexes.append({
                "id": f"idx_u_{s_name}_{t_name}_{u.get('name', 'unique')}",
                "name": u.get("name", "unique"),
                "unique": True,
                "isPrimaryKey": False,
                "fieldIds": [f"f_{s_name}_{t_name}_{c}" for c in u.get("columns", [])],
                "createdAt": created_timestamp_num
            })
        for idx in tbl.get("indexes", []):
            indexes.append({
                "id": f"idx_{s_name}_{t_name}_{idx.get('name', 'index')}",
                "name": idx.get("name", "index"),
                "unique": idx.get("unique", False),
                "isPrimaryKey": False,
                "fieldIds": [f"f_{s_name}_{t_name}_{c}" for c in idx.get("columns", [])],
                "createdAt": created_timestamp_num
            })

        db_tables.append({
            "id": table_id,
            "diagramId": DIAGRAM_ID,
            "name": t_name,
            "schema": s_name,
            "x": x,
            "y": y,
            "order": tbl_idx,
            "fields": fields,
            "indexes": indexes,
            "color": color,
            "comment": tbl.get("comment", ""),
            "isView": False,
            "isMaterializedView": False,
            "createdAt": created_timestamp_num
        })

    db_relationships = []
    for rel in schema_data.get("relations", []):
        src = rel["src"]
        ref = rel["ref"]
        rel_id = f"rel_{rel['name']}"
        db_relationships.append({
            "id": rel_id,
            "diagramId": DIAGRAM_ID,
            "name": rel["name"],
            "sourceSchema": src["schema"],
            "targetSchema": ref["schema"],
            "sourceTableId": f"tbl_{src['schema']}_{src['table']}",
            "targetTableId": f"tbl_{ref['schema']}_{ref['table']}",
            "sourceFieldId": f"f_{src['schema']}_{src['table']}_{src['column']}",
            "targetFieldId": f"f_{ref['schema']}_{ref['table']}_{ref['column']}",
            "sourceCardinality": "many",
            "targetCardinality": "one",
            "createdAt": created_timestamp_num
        })

    config = {
        "id": 1,
        "defaultDiagramId": DIAGRAM_ID
    }

    all_table_ids = [t["id"] for t in db_tables]
    all_schemas = sorted(list(set(t["schema"] for t in db_tables)))

    diagram_filters = {
        "diagramId": DIAGRAM_ID,
        "tableIds": all_table_ids,
        "schemasIds": all_schemas
    }

    return {
        "diagram": diagram,
        "db_tables": db_tables,
        "db_relationships": db_relationships,
        "config": config,
        "diagram_filters": diagram_filters,
        "sql_ddl": sql_ddl
    }

def generate_autoload_html(payload: dict) -> str:
    """Generate standalone autoload.html that writes to ChartDB Dexie IndexedDB (v130) and redirects."""
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
            margin: 4px;
        }}
        .btn:hover {{ background: #1d4ed8; }}
        .btn-repair {{
            background: #d97706;
        }}
        .btn-repair:hover {{
            background: #b45309;
        }}
    </style>
</head>
<body>
    <div class="card">
        <div class="badge">Bank Raya · DataOps Autoloader</div>
        <div class="spinner" id="spinner"></div>
        <h1 id="title">Menginjeksi ERD ke ChartDB...</h1>
        <p class="sub" id="sub">Menyuntikkan model data 11 Domain DASG ke IndexedDB lokal browser Anda secara instan tanpa perlu copas SQL manual.</p>
        
        <div class="status-box" id="status-box">
            <div class="status-line">⚡ Menghubungkan ke IndexedDB [ChartDB, v130]...</div>
        </div>

        <button class="btn btn-repair" id="repair-btn" style="display: none;" onclick="repairAndReseed()">Perbaiki & Sinkronkan Skema</button>
        <button class="btn" id="open-btn" style="display: none;" onclick="window.location.replace('/diagrams/{DIAGRAM_ID}')">Buka ChartDB Sekarang</button>
    </div>

    <script>
        const PAYLOAD = {payload_json};
        const TARGET_DIAGRAM_ID = "{DIAGRAM_ID}";

        const STORES_SPEC = {{
            diagrams: "++id, name, databaseType, databaseEdition, createdAt, updatedAt",
            db_tables: "++id, diagramId, name, schema, x, y, fields, indexes, color, createdAt, width, comment, isView, isMaterializedView, order",
            db_relationships: "++id, diagramId, name, sourceSchema, sourceTableId, targetSchema, targetTableId, sourceFieldId, targetFieldId, type, createdAt",
            db_dependencies: "++id, diagramId, schema, tableId, dependentSchema, dependentTableId, createdAt",
            areas: "++id, diagramId, name, x, y, width, height, color",
            db_custom_types: "++id, diagramId, schema, type, kind, values, fields",
            config: "++id, defaultDiagramId",
            diagram_filters: "diagramId, tableIds, schemasIds",
            notes: "++id, diagramId, content, x, y, width, height, color"
        }};

        function log(msg) {{
            const box = document.getElementById("status-box");
            const div = document.createElement("div");
            div.className = "status-line";
            div.textContent = msg;
            box.appendChild(div);
            box.scrollTop = box.scrollHeight;
        }}

        function checkFingerprint(db) {{
            for (const name of Object.keys(STORES_SPEC)) {{
                if (!db.objectStoreNames.contains(name)) return false;
            }}
            try {{
                const tx = db.transaction(["db_tables", "diagram_filters"], "readonly");
                const tableStore = tx.objectStore("db_tables");
                if (!tableStore.indexNames.contains("order")) return false;
                const filterStore = tx.objectStore("diagram_filters");
                if (filterStore.keyPath !== "diagramId") return false;
            }} catch (e) {{
                return false;
            }}
            return true;
        }}

        function createStores(db) {{
            for (const [storeName, specStr] of Object.entries(STORES_SPEC)) {{
                const tokens = specStr.split(",").map(t => t.trim()).filter(Boolean);
                const pkToken = tokens[0];
                const autoIncrement = pkToken.startsWith("++");
                const keyPath = autoIncrement ? pkToken.substring(2) : pkToken;
                const indexTokens = tokens.slice(1);

                let store;
                if (!db.objectStoreNames.contains(storeName)) {{
                    store = db.createObjectStore(storeName, {{ keyPath, autoIncrement }});
                }} else {{
                    continue;
                }}
                for (const idx of indexTokens) {{
                    if (!store.indexNames.contains(idx)) {{
                        store.createIndex(idx, idx, {{ unique: false }});
                    }}
                }}
            }}
        }}

        async function backupNonRayaData(db) {{
            return new Promise((resolve) => {{
                try {{
                    const storeNames = Array.from(db.objectStoreNames);
                    const tx = db.transaction(storeNames, "readonly");
                    const backup = {{}};
                    let pending = storeNames.length;
                    if (pending === 0) return resolve({{}});
                    for (const name of storeNames) {{
                        const req = tx.objectStore(name).getAll();
                        req.onsuccess = () => {{
                            backup[name] = (req.result || []).filter(item => {{
                                if (name === "diagrams") return item.id !== TARGET_DIAGRAM_ID && item.id !== 1 && item.id !== "1";
                                if (name === "db_tables" || name === "db_relationships") return item.diagramId !== TARGET_DIAGRAM_ID && item.diagramId !== 1 && item.diagramId !== "1";
                                if (name === "diagram_filters") return item.diagramId !== TARGET_DIAGRAM_ID;
                                return true;
                            }});
                            pending--;
                            if (pending === 0) resolve(backup);
                        }};
                        req.onerror = () => {{
                            pending--;
                            if (pending === 0) resolve(backup);
                        }};
                    }}
                }} catch (e) {{
                    resolve({{}});
                }}
            }});
        }}

        async function restoreBackupData(db, backup) {{
            if (!backup || Object.keys(backup).length === 0) return;
            const names = Object.keys(backup).filter(n => db.objectStoreNames.contains(n) && backup[n].length > 0);
            if (names.length === 0) return;
            return new Promise((resolve) => {{
                const tx = db.transaction(names, "readwrite");
                for (const n of names) {{
                    const s = tx.objectStore(n);
                    for (const item of backup[n]) {{
                        s.put(item);
                    }}
                }}
                tx.oncomplete = () => resolve();
                tx.onerror = () => resolve();
            }});
        }}

        async function repairAndReseed() {{
            log("🔧 Memulai proses perbaikan & rekonsiliasi skema IndexedDB...");
            document.getElementById("spinner").style.display = "block";
            document.getElementById("repair-btn").style.display = "none";
            document.getElementById("open-btn").style.display = "none";

            // Backup existing non-seed data if possible
            let backup = {{}};
            try {{
                const openReq = indexedDB.open("ChartDB");
                await new Promise((res) => {{
                    openReq.onsuccess = async (e) => {{
                        const db = e.target.result;
                        backup = await backupNonRayaData(db);
                        db.close();
                        res();
                    }};
                    openReq.onerror = () => res();
                }});
            }} catch (e) {{}}

            log("🗑️ Menghapus database lama dengan skema tidak kompatibel...");
            const delReq = indexedDB.deleteDatabase("ChartDB");
            delReq.onblocked = function() {{
                log("⚠️ Database terblokir oleh tab ChartDB lain. Menutup koneksi...");
            }};
            delReq.onerror = function(err) {{
                log("❌ Gagal mereset database: " + err);
                document.getElementById("spinner").style.display = "none";
                document.getElementById("repair-btn").style.display = "inline-block";
            }};
            delReq.onsuccess = function() {{
                log("✨ Database lama berhasil dibersihkan. Menginisialisasi skema baru...");
                seedChartDB(true, backup);
            }};
        }}

        async function seedChartDB(forceWrite = false, backup = null) {{
            try {{
                log("📦 Menyalin DDL SQL ke Clipboard sistem...");
                if (navigator.clipboard && navigator.clipboard.writeText) {{
                    await navigator.clipboard.writeText(PAYLOAD.sql_ddl).catch(() => {{}});
                }}

                log("💾 Menginisialisasi Dexie IndexedDB (v130)...");
                const req = indexedDB.open("ChartDB", 130);

                req.onblocked = function(e) {{
                    log("⚠️ Database terblokir! Tutup tab ChartDB lain lalu muat ulang halaman ini.");
                    document.getElementById("title").textContent = "Database Terblokir";
                    document.getElementById("sub").textContent = "Tutup tab ChartDB lain yang sedang terbuka, lalu muat ulang halaman ini.";
                    document.getElementById("spinner").style.display = "none";
                    document.getElementById("open-btn").style.display = "inline-block";
                }};

                req.onupgradeneeded = function(e) {{
                    const db = e.target.result;
                    createStores(db);
                }};

                req.onsuccess = async function(e) {{
                    const db = e.target.result;

                    // Validasi kompatibilitas skema
                    if (!forceWrite && !checkFingerprint(db)) {{
                        db.close();
                        log("⚠️ Struktur database IndexedDB lama tidak kompatibel (skema beracun).");
                        document.getElementById("title").textContent = "Perlu Perbaikan Skema";
                        document.getElementById("sub").textContent = "Ditemukan struktur database lama yang tidak sesuai standar ChartDB v130. Silakan klik tombol di bawah untuk menyinkronkan skema.";
                        document.getElementById("spinner").style.display = "none";
                        document.getElementById("repair-btn").style.display = "inline-block";
                        return;
                    }}

                    if (backup) {{
                        await restoreBackupData(db, backup);
                    }}

                    const tx = db.transaction(["diagrams", "db_tables", "db_relationships", "config", "diagram_filters"], "readwrite");
                    const diagStore = tx.objectStore("diagrams");
                    const tableStore = tx.objectStore("db_tables");
                    const relStore = tx.objectStore("db_relationships");
                    const confStore = tx.objectStore("config");
                    const filterStore = tx.objectStore("diagram_filters");

                    // Bersihkan record diagram lama secara sekuensial sebelum menulis record baru
                    const clearOld = (store, isDiag) => new Promise((res) => {{
                        const curReq = store.openCursor();
                        curReq.onsuccess = function(ev) {{
                            const cursor = ev.target.result;
                            if (cursor) {{
                                const val = cursor.value;
                                const matchId = isDiag 
                                    ? (val.id === TARGET_DIAGRAM_ID || val.id === 1 || val.id === "1" || typeof val.id === "number") 
                                    : (val.diagramId === TARGET_DIAGRAM_ID || val.diagramId === 1 || val.diagramId === "1" || typeof val.diagramId === "number");
                                if (matchId) {{
                                    cursor.delete();
                                }}
                                cursor.continue();
                            }} else {{
                                res();
                            }}
                        }};
                        curReq.onerror = () => res();
                    }});

                    await Promise.all([
                        clearOld(diagStore, true),
                        clearOld(tableStore, false),
                        clearOld(relStore, false)
                    ]);

                    // Buat Date native asli di JS
                    const diagData = Object.assign({{}}, PAYLOAD.diagram, {{
                        createdAt: new Date(),
                        updatedAt: new Date()
                    }});
                    diagStore.put(diagData);

                    for (const tbl of PAYLOAD.db_tables) {{
                        tableStore.put(tbl);
                    }}

                    for (const rel of PAYLOAD.db_relationships) {{
                        relStore.put(rel);
                    }}

                    confStore.put(PAYLOAD.config);
                    filterStore.put(PAYLOAD.diagram_filters);

                    tx.oncomplete = function() {{
                        log("✅ Selesai! Berhasil menginjeksi " + PAYLOAD.db_tables.length + " tabel dan " + PAYLOAD.db_relationships.length + " relasi.");
                        log("🚀 Mengarahkan ke kanvas ChartDB...");
                        document.getElementById("title").textContent = "Injeksi Berhasil!";
                        document.getElementById("spinner").style.display = "none";
                        document.getElementById("open-btn").style.display = "inline-block";

                        setTimeout(() => {{
                            window.location.replace('/diagrams/' + TARGET_DIAGRAM_ID);
                        }}, 400);
                    }};

                    tx.onerror = function(err) {{
                        log("❌ Gagal menyimpan transaksi: " + err.target.error);
                        document.getElementById("spinner").style.display = "none";
                        document.getElementById("open-btn").style.display = "inline-block";
                    }};
                }};

                req.onerror = function(err) {{
                    const error = err.target.error;
                    if (error && error.name === "VersionError") {{
                        log("❌ VersionError: " + error.message + " (Versi IndexedDB tidak kompatibel)");
                    }} else {{
                        log("❌ Gagal membuka IndexedDB: " + (error ? error.message : err));
                    }}
                    document.getElementById("spinner").style.display = "none";
                    document.getElementById("open-btn").style.display = "inline-block";
                }};

            }} catch (err) {{
                log("⚠️ Terjadi error: " + err.message);
                document.getElementById("spinner").style.display = "none";
                document.getElementById("open-btn").style.display = "inline-block";
            }}
        }}

        window.addEventListener("DOMContentLoaded", () => seedChartDB(false, null));
    </script>
</body>
</html>"""
    return html

def calculate_file_hash(path: Path) -> str:
    """Calculate sha256 checksum of a local file."""
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()

def seed_chartdb(generate_only: bool = False, hot_patch: bool = False, check_only: bool = False) -> int:
    base_dir = Path(__file__).resolve().parent.parent
    docker_bin = find_docker_bin()

    print("=" * 80)
    print("BANK RAYA - CHARTDB AUTOMATED PRE-LOADER & INDEXEDDB SEEDER")
    print("Standard: W3C IndexedDB Same-Origin Policy & Dexie.js Schema V13 (IDB v130)")
    print("Policy: 100% Stateless container via pre-built thin image (SSoT Bake)")
    print("=" * 80)

    # 1. Build Payload from Multiplatform Metadata
    payload = build_chartdb_payload(base_dir)
    print(f"[INFO] Prepared ChartDB Diagram Payload:")
    print(f"  -> Diagram ID:    {payload['diagram']['id']}")
    print(f"  -> Diagram Name:  {payload['diagram']['name']}")
    print(f"  -> Tables:        {len(payload['db_tables'])} tables mapped to visual grid coordinates")
    print(f"  -> Relationships: {len(payload['db_relationships'])} cross-platform FK relations")

    # 2. Generate autoload.html
    html_content = generate_autoload_html(payload)
    out_html = base_dir / "sources" / "autoload.html"
    out_html.write_text(html_content, encoding="utf-8")
    local_hash = calculate_file_hash(out_html)
    print(f"[INFO] Generated Autoload HTML: {out_html.relative_to(base_dir)} (SHA256: {local_hash[:16]}...)")

    if generate_only:
        print("[PASS] Generation completed (--generate-only). Exiting.")
        return 0

    def make_docker_cmd(args):
        if docker_bin.startswith("wsl"):
            return ["wsl", "-d", "Ubuntu", "-e", "docker"] + args
        return [docker_bin] + args

    inspect_cmd = make_docker_cmd(["ps", "--filter", "name=chartdb-app", "--format", "{{.Names}}"])
    res = subprocess.run(inspect_cmd, capture_output=True, text=True, check=False)
    if "chartdb-app" not in res.stdout:
        print("[FAIL] Container 'chartdb-app' is not running. Start container first with docker compose up -d.")
        return 1

    # Dev hot-patch mode
    if hot_patch:
        print("[WARN] Menggunakan --hot-patch (runtime docker cp). SSoT gambar container tidak terjaga! Hanya untuk dev.")
        def to_wsl_path(p: Path) -> str:
            if docker_bin.startswith("wsl"):
                drive = p.drive.replace(":", "").lower()
                rel = p.as_posix().split(":", 1)[-1]
                return f"/mnt/{drive}{rel}"
            return str(p)

        cp_res = subprocess.run(make_docker_cmd(["cp", to_wsl_path(out_html), "chartdb-app:/usr/share/nginx/html/autoload.html"]),
                                capture_output=True, text=True, check=False)
        if cp_res.returncode != 0:
            print(f"[FAIL] docker cp autoload.html failed: {cp_res.stderr.strip()}")
            return 1
        print("[PASS] Hot-patch applied to running container.")
        return 0

    # SSoT Bake integrity check: compare SHA256 between host and container
    chk_res = subprocess.run(make_docker_cmd(["exec", "chartdb-app", "sha256sum", "/usr/share/nginx/html/autoload.html"]),
                             capture_output=True, text=True, check=False)
    container_hash = chk_res.stdout.split()[0] if (chk_res.returncode == 0 and chk_res.stdout) else None

    if container_hash != local_hash:
        print(f"[FAIL] Image basi! Jalankan docker compose up -d --build")
        print(f"  -> Host SHA256:      {local_hash}")
        print(f"  -> Container SHA256: {container_hash}")
        return 1

    print(f"[PASS] Image integritas valid (SHA256 host == container: {local_hash[:16]}...).")
    return 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ChartDB Seeder")
    parser.add_argument("--generate-only", action="store_true", help="Only generate sources/autoload.html without checking container")
    parser.add_argument("--hot-patch", action="store_true", help="[DEV ONLY] Hot-patch running container using docker cp (violates SSoT bake)")
    parser.add_argument("--check-only", action="store_true", help="Verify SHA256 integrity only")
    args = parser.parse_args()
    sys.exit(seed_chartdb(generate_only=args.generate_only, hot_patch=args.hot_patch, check_only=args.check_only))
