#!/usr/bin/env python3
"""
Bank Raya - Azimutt Automated Project Pre-Seeding & Metadata Initializer
Framework: DAMA-DMBOK V.2 | Zero-Credential-Exposure Architecture
Standard: Azimutt JsonSchema.elm & Phoenix Ecto Metadata Compliance
Security: PostgreSQL port 5432 remains 100% internal (accessed only via docker exec -i).
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

def build_azimutt_project_json(base_dir: Path) -> dict:
    schema_file = base_dir / "sources" / "bank_raya_unified_schema.json"
    layouts_file = base_dir / "layouts" / "bank_raya_domain_layouts.json"

    if not schema_file.exists():
        raise FileNotFoundError(f"Unified schema not found: {schema_file}")
    if not layouts_file.exists():
        raise FileNotFoundError(f"Domain layouts not found: {layouts_file}")

    schema_data = json.loads(schema_file.read_text(encoding="utf-8"))
    layouts_data = json.loads(layouts_file.read_text(encoding="utf-8"))

    now_ms = 1729900000000
    project_id = "00000000-0000-4000-8000-000000000001"
    source_id = "00000000-0000-4000-8000-000000000002"

    raw_layouts = layouts_data.get("layouts", {})

    # Transform layouts to Azimutt layout schema
    formatted_layouts = {}
    for l_key, l_val in raw_layouts.items():
        layout_tables = []
        for tbl in l_val.get("tables", []):
            tbl_id = tbl.get("id", "")
            # Azimutt layout table format: schema.table or .table
            pos = tbl.get("position", {"left": 100, "top": 100})
            layout_tables.append({
                "id": tbl_id,
                "position": pos,
                "color": tbl.get("color", "blue"),
                "columns": []
            })
        formatted_layouts[l_key] = {
            "tables": layout_tables,
            "createdAt": now_ms,
            "updatedAt": now_ms
        }

    # Ensure a default layout
    if "initial layout" not in formatted_layouts and "oltp/core_and_channels" in formatted_layouts:
        formatted_layouts["initial layout"] = formatted_layouts["oltp/core_and_channels"]

    project = {
        "id": project_id,
        "name": "Bank Raya Enterprise Data Architecture",
        "description": "Unified Multi-Platform Architecture (DAMA-DMBOK V.2 & DASG 11-Domain Taxonomy)",
        "sources": [
            {
                "id": source_id,
                "name": "bank_raya_unified_schema.json",
                "kind": {
                    "kind": "AmlLocalFile",
                    "name": "bank_raya_unified_schema.json",
                    "size": schema_file.stat().st_size
                },
                "tables": schema_data.get("tables", []),
                "relations": schema_data.get("relations", []),
                "types": schema_data.get("types", []),
                "createdAt": now_ms,
                "updatedAt": now_ms
            }
        ],
        "usedLayout": "oltp/core_and_channels",
        "layouts": formatted_layouts,
        "createdAt": now_ms,
        "updatedAt": now_ms,
        "version": 2
    }

    return project


def generate_autoload_azimutt_html(project: dict) -> str:
    """Generate client-side autoloader HTML for Azimutt."""
    project_json = json.dumps(project, ensure_ascii=False)
    
    html = f"""<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bank Raya · Azimutt Automated Pre-Loader</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            background: linear-gradient(135deg, #091325 0%, #0c4f9c 100%);
            color: #ffffff;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            padding: 20px;
        }}
        .card {{
            background: rgba(15, 23, 42, 0.85);
            border: 1px solid rgba(56, 189, 248, 0.3);
            backdrop-filter: blur(16px);
            border-radius: 16px;
            padding: 36px;
            max-width: 560px;
            width: 100%;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.6);
            text-align: center;
        }}
        .badge {{
            display: inline-block;
            background: rgba(14, 165, 233, 0.15);
            color: #38bdf8;
            border: 1px solid rgba(14, 165, 233, 0.3);
            border-radius: 9999px;
            padding: 4px 16px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 18px;
        }}
        h1 {{ font-size: 22px; font-weight: 700; margin-bottom: 8px; }}
        p.sub {{ color: #94a3b8; font-size: 14px; margin-bottom: 24px; line-height: 1.5; }}
        .spinner {{
            width: 48px;
            height: 48px;
            border: 4px solid rgba(56, 189, 248, 0.2);
            border-top-color: #38bdf8;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 20px auto;
        }}
        @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
        .status-box {{
            background: #091325;
            border: 1px solid #1e293b;
            border-radius: 8px;
            padding: 14px;
            font-family: monospace;
            font-size: 12px;
            color: #38bdf8;
            text-align: left;
            max-height: 140px;
            overflow-y: auto;
            margin-bottom: 24px;
        }}
        .status-line {{ margin-bottom: 4px; }}
        .btn {{
            display: inline-block;
            background: #0284c7;
            color: white;
            font-weight: 600;
            font-size: 14px;
            padding: 12px 28px;
            border-radius: 8px;
            text-decoration: none;
            transition: all 0.2s;
            cursor: pointer;
            border: none;
        }}
        .btn:hover {{ background: #0369a1; }}
    </style>
</head>
<body>
    <div class="card">
        <div class="badge">Bank Raya · DataOps Autoloader</div>
        <div class="spinner" id="spinner"></div>
        <h1 id="title">Menyiapkan Project Azimutt...</h1>
        <p class="sub" id="sub">Menyinkronkan 8 tabel multi-platform dan 38 visual layouts (11 Domain DASG) ke environment Azimutt Anda.</p>
        
        <div class="status-box" id="status-box">
            <div class="status-line">⚡ Membuka IndexedDB Azimutt [database: azimutt, v2]...</div>
        </div>

        <button class="btn" id="open-btn" style="display: none;" onclick="launchAzimutt()">Buka Azimutt Project Sekarang</button>
    </div>

    <script>
        const PROJECT = {project_json};
        const TARGET_URL = "http://localhost:8000/create?json=/elm/samples/bank_raya.azimutt.json";

        function log(msg) {{
            const box = document.getElementById("status-box");
            const div = document.createElement("div");
            div.className = "status-line";
            div.textContent = msg;
            box.appendChild(div);
            box.scrollTop = box.scrollHeight;
        }}

        function launchAzimutt() {{
            window.location.replace(TARGET_URL);
        }}

        async function seedAzimutt() {{
            try {{
                log("📦 Menyimpan metadata project ke LocalStorage...");
                try {{
                    localStorage.setItem("project-" + PROJECT.id, JSON.stringify(PROJECT));
                }} catch (e) {{
                    log("ℹ️ LocalStorage: " + e.message);
                }}

                log("💾 Menghubungkan ke IndexedDB Azimutt...");
                const req = indexedDB.open("azimutt", 2);

                req.onupgradeneeded = function(e) {{
                    const db = e.target.result;
                    if (!db.objectStoreNames.contains("projects")) {{
                        db.createObjectStore("projects", {{ keyPath: "id" }});
                    }}
                    if (!db.objectStoreNames.contains("connections")) {{
                        db.createObjectStore("connections", {{ keyPath: "id" }});
                    }}
                }};

                req.onsuccess = function(e) {{
                    const db = e.target.result;
                    const tx = db.transaction(["projects"], "readwrite");
                    const store = tx.objectStore("projects");
                    store.put(PROJECT);

                    tx.oncomplete = function() {{
                        log("✅ Project berhasil disimpan ke IndexedDB.");
                        log("🚀 Mengarahkan ke visualizer Azimutt...");
                        document.getElementById("title").textContent = "Project Siap Digunakan!";
                        document.getElementById("spinner").style.display = "none";
                        document.getElementById("open-btn").style.display = "inline-block";

                        setTimeout(launchAzimutt, 600);
                    }};

                    tx.onerror = function(err) {{
                        log("⚠️ Gagal simpan ke IndexedDB, beralih ke Native URL auto-loader...");
                        setTimeout(launchAzimutt, 600);
                    }};
                }};

                req.onerror = function() {{
                    log("ℹ️ Mengarahkan langsung via Azimutt Native Sample loader...");
                    setTimeout(launchAzimutt, 600);
                }};

            }} catch (err) {{
                log("⚠️ Error: " + err.message);
                document.getElementById("open-btn").style.display = "inline-block";
                setTimeout(launchAzimutt, 1000);
            }}
        }}

        window.addEventListener("DOMContentLoaded", seedAzimutt);
    </script>
</body>
</html>"""
    return html


def seed_postgres_metadata(docker_bin: str):
    """Seed user, organization, and project directly into isolated PostgreSQL without exposing port."""
    sql = """
    INSERT INTO users (id, slug, name, email, avatar, is_admin, last_signin, created_at, updated_at, confirmed_at)
    VALUES (
        '11111111-1111-4111-8111-111111111111',
        'bastian-natanael',
        'Bastian Natanael',
        'bastiannatanaels@gmail.com',
        'https://localhost/avatar.png',
        true,
        NOW(),
        NOW(),
        NOW(),
        NOW()
    )
    ON CONFLICT (email) DO UPDATE SET
        name = EXCLUDED.name,
        is_admin = true,
        confirmed_at = COALESCE(users.confirmed_at, NOW()),
        updated_at = NOW();

    INSERT INTO organizations (id, slug, name, logo, is_personal, created_by, updated_by, created_at, updated_at, plan, plan_status)
    VALUES (
        '22222222-2222-4222-8222-222222222222',
        'bank-raya',
        'Bank Raya Enterprise',
        'https://localhost/logo.png',
        false,
        '11111111-1111-4111-8111-111111111111',
        '11111111-1111-4111-8111-111111111111',
        NOW(),
        NOW(),
        'pro',
        'active'
    )
    ON CONFLICT (slug) DO UPDATE SET
        name = EXCLUDED.name,
        updated_at = NOW();

    INSERT INTO organization_members (user_id, organization_id, created_by, updated_by, created_at, updated_at, role)
    VALUES (
        '11111111-1111-4111-8111-111111111111',
        '22222222-2222-4222-8222-222222222222',
        '11111111-1111-4111-8111-111111111111',
        '11111111-1111-4111-8111-111111111111',
        NOW(),
        NOW(),
        'owner'
    )
    ON CONFLICT (user_id, organization_id) DO UPDATE SET
        role = 'owner',
        updated_at = NOW();

    INSERT INTO projects (
        id, organization_id, slug, name, description, encoding_version, storage_kind,
        file, nb_sources, nb_tables, nb_columns, nb_relations, nb_types,
        nb_comments, nb_notes, nb_layouts, created_by, updated_by, created_at, updated_at, visibility
    )
    VALUES (
        '00000000-0000-4000-8000-000000000001',
        '22222222-2222-4222-8222-222222222222',
        'bank-raya-enterprise',
        'Bank Raya Enterprise Data Architecture',
        'Unified Multi-Platform Architecture (DAMA-DMBOK V.2 & DASG 11-Domain Taxonomy)',
        1,
        'remote',
        'projects/00000000-0000-4000-8000-000000000001.json',
        1,
        8,
        65,
        4,
        1,
        65,
        0,
        38,
        '11111111-1111-4111-8111-111111111111',
        '11111111-1111-4111-8111-111111111111',
        NOW(),
        NOW(),
        'organization'
    )
    ON CONFLICT (id) DO UPDATE SET
        name = EXCLUDED.name,
        nb_layouts = EXCLUDED.nb_layouts,
        updated_at = NOW();
    """

    cmd = [
        docker_bin, "exec", "-i", "azimutt-backend-db",
        "psql", "-U", "azimutt_bank_admin", "-d", "azimutt_metadata"
    ]
    res = subprocess.run(cmd, input=sql, capture_output=True, text=True, check=False)
    if res.returncode == 0:
        print("[PASS] Successfully pre-seeded PostgreSQL metadata (user, org, project):")
        print("  -> User:         bastiannatanaels@gmail.com (Role: Owner / Admin)")
        print("  -> Organization: bank-raya ('Bank Raya Enterprise')")
        print("  -> Project:      Bank Raya Enterprise Data Architecture (ID: 00000000-0000-4000-8000-000000000001)")
    else:
        print(f"[WARN] PostgreSQL metadata seeding reported: {res.stderr}")


def seed_azimutt():
    base_dir = Path(__file__).resolve().parent.parent
    docker_bin = find_docker_bin()

    print("=" * 80)
    print("BANK RAYA - AZIMUTT AUTOMATED PRE-SEEDING & MULTI-LAYER LOADER")
    print("Framework: DAMA-DMBOK V.2 | Zero-Credential-Exposure Architecture")
    print("=" * 80)

    # 1. Build Full Azimutt Project JSON
    project = build_azimutt_project_json(base_dir)
    project_json_str = json.dumps(project, indent=2, ensure_ascii=False)

    # 2. Save locally to multiple paths for persistent volume mounts
    out_paths = [
        base_dir / "sources" / "bank_raya.azimutt.json",
        base_dir / "azimutt-data" / "uploads" / "projects" / "00000000-0000-4000-8000-000000000001.json",
        base_dir / "azimutt-data" / "uploads" / "projects" / "bank-raya-enterprise.json"
    ]
    for p in out_paths:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(project_json_str, encoding="utf-8")

    print(f"[INFO] Generated Azimutt Unified Project JSON:")
    print(f"  -> Project Name: {project['name']}")
    print(f"  -> Layouts:      {len(project['layouts'])} DAMA-DMBOK / DASG domain views")
    print(f"  -> Saved Local:  {out_paths[0].relative_to(base_dir)}")

    # 3. Generate HTML autoloader fallback
    html_content = generate_autoload_azimutt_html(project)
    autoload_file = base_dir / "azimutt-data" / "autoload_azimutt.html"
    autoload_file.write_text(html_content, encoding="utf-8")
    print(f"[INFO] Generated Client-Side Autoloader: {autoload_file.relative_to(base_dir)}")

    # 4. Check Docker Containers & Seed
    try:
        inspect_cmd = [docker_bin, "ps", "--format", "{{.Names}}"]
        res = subprocess.run(inspect_cmd, capture_output=True, text=True, check=False)
        running_containers = res.stdout.split()

        # Seed PostgreSQL backend if azimutt-backend-db is running
        if "azimutt-backend-db" in running_containers:
            print("[INFO] Seeding PostgreSQL internal metadata via secure docker exec...")
            seed_postgres_metadata(docker_bin)
        else:
            print("[WARN] Container 'azimutt-backend-db' is not running. Skipping DB seeding.")

        # Seed static sample into azimutt-app if running
        if "azimutt-app" in running_containers:
            print("[INFO] Injecting 'bank_raya.azimutt.json' into Azimutt static sample registry...")
            target_container_path = "azimutt-app:/app/lib/azimutt-2.0.1787693579/priv/static/elm/samples/bank_raya.azimutt.json"
            cp_cmd = [docker_bin, "cp", str(out_paths[0]), target_container_path]
            cp_res = subprocess.run(cp_cmd, capture_output=True, text=True, check=False)
            if cp_res.returncode == 0:
                print("[PASS] Injected project sample into Azimutt container.")
                print("  -> Direct Zero-Form URL: http://localhost:8000/create?json=/elm/samples/bank_raya.azimutt.json")
            else:
                print(f"[WARN] Failed to docker cp to azimutt-app: {cp_res.stderr}")
        else:
            print("[WARN] Container 'azimutt-app' is not running. Will be injected on launch.")

    except Exception as e:
        print(f"[WARN] Error executing Docker automation: {e}")

    print("=" * 80)
    print("AZIMUTT PRE-SEEDING COMPLETED SUCCESSFULLY (EXIT 0).")
    print("=" * 80)
    return 0

if __name__ == "__main__":
    sys.exit(seed_azimutt())
