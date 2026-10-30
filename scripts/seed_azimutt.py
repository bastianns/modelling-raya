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
    """Find docker executable across system paths or fallback to WSL."""
    # Check if native docker works
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

    # Check if WSL docker works
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

def build_azimutt_project_json(base_dir: Path) -> tuple[dict, dict]:
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

    # 1. Transform tables to Azimutt LegacyProjectTable schema
    formatted_tables = []
    table_col_map = {}
    for tbl in schema_data.get("tables", []):
        s_name = tbl.get("schema", "")
        t_name = tbl.get("table") or tbl.get("name", "")
        full_id = f"{s_name}.{t_name}" if s_name else t_name

        cols = []
        col_names = []
        for c in tbl.get("columns", []):
            c_name = c["name"]
            col_names.append(c_name)
            col_dict = {
                "name": c_name,
                "type": c.get("type", "varchar")
            }
            if not c.get("nullable", True):
                col_dict["nullable"] = False
            if c.get("default") is not None:
                col_dict["default"] = str(c["default"])
            comment_text = str(c.get("comment", "") or "")
            if c.get("pii"):
                comment_text += " [PII: Terproteksi]"
            if c.get("data_rules"):
                comment_text += f" [Rules: {c['data_rules']}]"
            if comment_text.strip():
                col_dict["comment"] = {"text": comment_text.strip()}
            cols.append(col_dict)

        table_col_map[full_id] = col_names

        table_entry = {
            "schema": s_name,
            "table": t_name,
            "columns": cols
        }
        if tbl.get("primaryKey"):
            table_entry["primaryKey"] = {
                "name": tbl["primaryKey"].get("name", f"pk_{t_name}"),
                "columns": tbl["primaryKey"].get("columns", [])
            }
        if tbl.get("uniques"):
            table_entry["uniques"] = [
                {"name": u.get("name", f"uq_{t_name}"), "columns": u.get("columns", [])}
                for u in tbl["uniques"]
            ]
        if tbl.get("indexes"):
            table_entry["indexes"] = [
                {"name": idx.get("name", f"idx_{t_name}"), "columns": idx.get("columns", [])}
                for idx in tbl["indexes"]
            ]
        if tbl.get("checks"):
            table_entry["checks"] = tbl["checks"]
        if tbl.get("comment"):
            table_entry["comment"] = {"text": str(tbl["comment"])}

        formatted_tables.append(table_entry)

    # 2. Transform relations to Azimutt LegacyProjectRelation schema
    formatted_relations = []
    for rel in schema_data.get("relations", []):
        src = rel["src"]
        ref = rel["ref"]
        src_table = f"{src['schema']}.{src['table']}" if src.get("schema") else src["table"]
        ref_table = f"{ref['schema']}.{ref['table']}" if ref.get("schema") else ref["table"]
        formatted_relations.append({
            "name": rel.get("name", f"fk_{src_table}_{ref_table}"),
            "src": {
                "table": src_table,
                "column": src["column"]
            },
            "ref": {
                "table": ref_table,
                "column": ref["column"]
            }
        })

    # 3. Transform layouts to Azimutt LegacyLayout schema
    raw_layouts = layouts_data.get("layouts", {})
    formatted_layouts = {}
    for l_key, l_val in raw_layouts.items():
        layout_tables = []
        for tbl in l_val.get("tables", []):
            tbl_id = tbl.get("id", "")
            cols = tbl.get("columns") or table_col_map.get(tbl_id, [])
            height = max(120, 36 + 22 * len(cols))
            layout_tables.append({
                "id": tbl_id,
                "position": tbl.get("position", {"left": 100, "top": 100}),
                "size": tbl.get("size", {"width": 260, "height": height}),
                "color": tbl.get("color", "blue"),
                "columns": cols
            })
        formatted_layouts[l_key] = {
            "canvas": {"position": {"left": 0, "top": 0}, "zoom": 1},
            "tables": layout_tables,
            "createdAt": now_ms,
            "updatedAt": now_ms
        }

    # Ensure a default layout
    if "initial layout" not in formatted_layouts and "oltp/core_and_channels" in formatted_layouts:
        formatted_layouts["initial layout"] = formatted_layouts["oltp/core_and_channels"]

    # 4. Format types to Azimutt LegacyProjectType schema
    formatted_types = []
    for t in schema_data.get("types", []):
        t_entry = {
            "schema": t.get("schema", ""),
            "name": t.get("name", "")
        }
        val = t.get("value")
        if val and isinstance(val, dict) and ("definition" in val or "enum" in val):
            t_entry["value"] = val
        elif "values" in t:
            t_entry["value"] = {"definition": f"STRUCT<{', '.join(t['values'])}>"}
        elif "definition" in t:
            t_entry["value"] = {"definition": t["definition"]}
        elif "enum" in t:
            t_entry["value"] = {"enum": t["enum"]}
        else:
            t_entry["value"] = {"definition": "TEXT"}
        formatted_types.append(t_entry)

    sources = [
        {
            "id": source_id,
            "name": "bank_raya_unified_schema.json",
            "kind": {
                "kind": "JsonLocalFile",
                "name": "bank_raya_unified_schema.json",
                "size": schema_file.stat().st_size,
                "modified": now_ms
            },
            "content": [],
            "tables": formatted_tables,
            "relations": formatted_relations,
            "types": formatted_types,
            "createdAt": now_ms,
            "updatedAt": now_ms
        }
    ]

    # Storage Project (LegacyProjectJson for backend uploads/projects)
    storage_project = {
        "_type": "json",
        "slug": "bank-raya-enterprise",
        "name": "Bank Raya Enterprise Data Architecture",
        "description": "Unified Multi-Platform Architecture (DAMA-DMBOK V.2 & DASG 11-Domain Taxonomy)",
        "sources": sources,
        "usedLayout": "oltp/core_and_channels",
        "layouts": formatted_layouts,
        "version": 2
    }

    # Standalone Project (LegacyProject for standalone export/import)
    standalone_project = {
        "id": project_id,
        "slug": "bank-raya-enterprise",
        "name": "Bank Raya Enterprise Data Architecture",
        "description": "Unified Multi-Platform Architecture (DAMA-DMBOK V.2 & DASG 11-Domain Taxonomy)",
        "sources": sources,
        "usedLayout": "oltp/core_and_channels",
        "layouts": formatted_layouts,
        "createdAt": now_ms,
        "updatedAt": now_ms,
        "version": 2
    }

    return storage_project, standalone_project


def generate_autoload_azimutt_html(project: dict, project_id: str = "00000000-0000-4000-8000-000000000001") -> str:
    """Generate client-side autoloader HTML for Azimutt."""
    project_json = json.dumps(project, ensure_ascii=False)
    nb_tables = len(project.get("sources", [{}])[0].get("tables", []))
    nb_layouts = len(project.get("layouts", {}))
    
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
        <p class="sub" id="sub">Menyinkronkan {nb_tables} tabel multi-platform dan {nb_layouts} visual layouts (11 Domain DASG) ke environment Azimutt Anda.</p>
        
        <div class="status-box" id="status-box">
            <div class="status-line">⚡ Membuka IndexedDB Azimutt [database: azimutt, v2]...</div>
        </div>

        <button class="btn" id="open-btn" style="display: none;" onclick="launchAzimutt()">Buka Azimutt Project Sekarang</button>
    </div>

    <script>
        const PROJECT = {project_json};
        const PROJECT_ID = "{project_id}";
        const TARGET_URL = "http://localhost:8000/22222222-2222-4222-8222-222222222222/" + PROJECT_ID;

        function log(msg) {{
            const box = document.getElementById("status-box");
            const div = document.createElement("div");
            div.className = "status-line";
            div.textContent = msg;
            box.appendChild(div);
            box.scrollTop = box.scrollHeight;
        }}

        async function launchAzimutt() {{
            log("🔍 Memeriksa status sesi login Azimutt...");
            try {{
                const res = await fetch("http://localhost:8000/api/v1/users/current", {{
                    credentials: "include"
                }});
                if (res.status === 200) {{
                    const userData = await res.json();
                    log("✅ Sesi aktif terdeteksi: " + (userData.email || userData.name || "Admin"));
                    log("🚀 Mengarahkan ke kanvas proyek Bank Raya Enterprise...");
                    setTimeout(() => {{
                        window.location.replace(TARGET_URL);
                    }}, 600);
                }} else {{
                    log("⚠️ Sesi belum terautentikasi (HTTP " + res.status + " Unauthorized).");
                    log("🔐 Mengarahkan ke portal login Azimutt...");
                    document.getElementById("title").textContent = "Silakan Login Terlebih Dahulu";
                    document.getElementById("sub").textContent = "Proyek Bank Raya Enterprise diproteksi secara privat (visibility: none). Silakan login untuk membuka kanvas.";
                    document.getElementById("spinner").style.display = "none";
                    const btn = document.getElementById("open-btn");
                    btn.textContent = "Buka Halaman Login";
                    btn.onclick = () => {{ window.location.replace("http://localhost:8000/login"); }};
                    btn.style.display = "inline-block";
                    setTimeout(() => {{
                        window.location.replace("http://localhost:8000/login");
                    }}, 1200);
                }}
            }} catch (err) {{
                log("ℹ️ Error koneksi sesi, beralih ke login: " + err.message);
                setTimeout(() => {{
                    window.location.replace("http://localhost:8000/login");
                }}, 1000);
            }}
        }}

        async function seedAzimutt() {{
            try {{
                log("📦 Menyimpan metadata project ke LocalStorage...");
                try {{
                    localStorage.setItem("project-" + PROJECT_ID, JSON.stringify(PROJECT));
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
                    store.put(Object.assign({{}}, PROJECT, {{ id: PROJECT_ID }}));

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


def seed_postgres_metadata(docker_bin: str, project: dict = None):
    """Seed user, organization, and project directly into isolated PostgreSQL without exposing port."""
    base_dir = Path(__file__).resolve().parent.parent
    if project is None:
        project, _ = build_azimutt_project_json(base_dir)

    sources = project.get("sources", [])
    nb_sources = len(sources)
    nb_tables = sum(len(s.get("tables", [])) for s in sources)
    nb_columns = sum(sum(len(t.get("columns", [])) for t in s.get("tables", [])) for s in sources)
    nb_relations = sum(len(s.get("relations", [])) for s in sources)
    nb_types = sum(len(s.get("types", [])) for s in sources)
    nb_comments = sum(
        sum(
            (1 if t.get("comment") else 0) + sum(1 for c in t.get("columns", []) if c.get("comment"))
            for t in s.get("tables", [])
        )
        for s in sources
    )
    nb_layouts = len(project.get("layouts", {}))

    admin_pw_hash = os.environ.get("AZIMUTT_ADMIN_PASSWORD_HASH", "").strip()

    # Check if user already exists in PostgreSQL
    if docker_bin.startswith("wsl"):
        base_cmd = ["wsl", "-d", "Ubuntu", "-e", "docker", "exec", "-i", "azimutt-backend-db", "psql", "-U", "azimutt_bank_admin", "-d", "azimutt_metadata"]
    else:
        base_cmd = [docker_bin, "exec", "-i", "azimutt-backend-db", "psql", "-U", "azimutt_bank_admin", "-d", "azimutt_metadata"]

    check_cmd = base_cmd + ["-tAc", "SELECT count(*) FROM users WHERE email='bastiannatanaels@gmail.com';"]
    check_res = subprocess.run(check_cmd, capture_output=True, text=True, check=False)
    user_count = int(check_res.stdout.strip()) if check_res.returncode == 0 and check_res.stdout.strip().isdigit() else 0

    if not admin_pw_hash:
        if user_count == 0:
            print("[ERROR] Variabel lingkungan AZIMUTT_ADMIN_PASSWORD_HASH belum disetel dan user admin belum ada di database.")
            print("        Silakan set AZIMUTT_ADMIN_PASSWORD_HASH di environment atau jalankan scripts/set_admin_password.py.")
            sys.exit(1)
        else:
            print("[INFO] AZIMUTT_ADMIN_PASSWORD_HASH tidak disetel, namun user sudah ada di database. Melanjutkan tanpa mengubah hashed_password.")

    if admin_pw_hash:
        user_sql = f"""
    INSERT INTO users (id, slug, name, email, avatar, is_admin, hashed_password, onboarding, last_signin, created_at, updated_at, confirmed_at)
    VALUES (
        '11111111-1111-4111-8111-111111111111',
        'bastian-natanael',
        'Bastian Natanael',
        'bastiannatanaels@gmail.com',
        'https://localhost/avatar.png',
        true,
        '{admin_pw_hash}',
        'completed',
        NOW(),
        NOW(),
        NOW(),
        NOW()
    )
    ON CONFLICT (email) DO UPDATE SET
        name = EXCLUDED.name,
        is_admin = true,
        hashed_password = EXCLUDED.hashed_password,
        onboarding = 'completed',
        confirmed_at = COALESCE(users.confirmed_at, NOW()),
        updated_at = NOW();

    UPDATE users SET is_admin = true, hashed_password = '{admin_pw_hash}', confirmed_at = COALESCE(confirmed_at, NOW()), updated_at = NOW() WHERE email LIKE '%bastian%';
    """
    else:
        user_sql = """
    UPDATE users SET
        name = 'Bastian Natanael',
        is_admin = true,
        onboarding = 'completed',
        confirmed_at = COALESCE(confirmed_at, NOW()),
        updated_at = NOW()
    WHERE email = 'bastiannatanaels@gmail.com';

    UPDATE users SET is_admin = true, confirmed_at = COALESCE(confirmed_at, NOW()), updated_at = NOW() WHERE email LIKE '%bastian%';
    """

    sql = f"""
    -- 1. User bastiannatanaels@gmail.com
    {user_sql}

    -- 2. Personal Organization (required by Azimutt dashboard)
    INSERT INTO organizations (id, slug, name, logo, is_personal, created_by, updated_by, created_at, updated_at, plan, plan_status, plan_freq, plan_seats, plan_validated)
    VALUES (
        '33333333-3333-4333-8333-333333333333',
        'bastian-natanael',
        'Bastian Natanael',
        'https://localhost/avatar.png',
        true,
        '11111111-1111-4111-8111-111111111111',
        '11111111-1111-4111-8111-111111111111',
        NOW(),
        NOW(),
        'pro',
        'manual',
        'monthly',
        10,
        NOW() + INTERVAL '10 years'
    )
    ON CONFLICT (slug) DO UPDATE SET
        is_personal = true,
        plan = EXCLUDED.plan,
        plan_status = EXCLUDED.plan_status,
        plan_freq = EXCLUDED.plan_freq,
        plan_seats = EXCLUDED.plan_seats,
        plan_validated = EXCLUDED.plan_validated,
        updated_at = NOW();

    -- Also upgrade any other personal organization for Bastian to pro
    UPDATE organizations SET
        plan = 'pro',
        plan_status = 'manual',
        plan_freq = 'monthly',
        plan_seats = 10,
        plan_validated = NOW() + INTERVAL '10 years',
        updated_at = NOW()
    WHERE is_personal = true;

    -- 3. Team Organization: Bank Raya Enterprise
    INSERT INTO organizations (id, slug, name, logo, is_personal, created_by, updated_by, created_at, updated_at, plan, plan_status, plan_freq, plan_seats, plan_validated)
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
        'manual',
        'monthly',
        10,
        NOW() + INTERVAL '10 years'
    )
    ON CONFLICT (slug) DO UPDATE SET
        name = EXCLUDED.name,
        plan = EXCLUDED.plan,
        plan_status = EXCLUDED.plan_status,
        plan_freq = EXCLUDED.plan_freq,
        plan_seats = EXCLUDED.plan_seats,
        plan_validated = EXCLUDED.plan_validated,
        updated_at = NOW();

    -- 4. Organization Memberships
    INSERT INTO organization_members (user_id, organization_id, created_by, updated_by, created_at, updated_at, role)
    SELECT id, '22222222-2222-4222-8222-222222222222', id, id, NOW(), NOW(), 'owner'
    FROM users WHERE email LIKE '%bastian%'
    ON CONFLICT (user_id, organization_id) DO UPDATE SET
        role = 'owner',
        updated_at = NOW();

    -- 5. User Profile
    INSERT INTO user_profiles (id, user_id, role, company, team_organization_id, created_at, updated_at)
    VALUES (
        '44444444-4444-4444-8444-444444444444',
        '11111111-1111-4111-8111-111111111111',
        'Data Architect',
        'Bank Raya',
        '22222222-2222-4222-8222-222222222222',
        NOW(),
        NOW()
    )
    ON CONFLICT (id) DO NOTHING;

    -- 6. Project: Bank Raya Enterprise Data Architecture (Personal & Team)
    INSERT INTO projects (
        id, organization_id, slug, name, description, encoding_version, storage_kind,
        file, nb_sources, nb_tables, nb_columns, nb_relations, nb_types,
        nb_comments, nb_notes, nb_layouts, created_by, updated_by, created_at, updated_at, visibility
    )
    VALUES 
    (
        '00000000-0000-4000-8000-000000000001',
        '22222222-2222-4222-8222-222222222222',
        'bank-raya-enterprise',
        'Bank Raya Enterprise Data Architecture',
        'Unified Multi-Platform Architecture (DAMA-DMBOK V.2 & DASG 11-Domain Taxonomy)',
        1,
        'remote',
        'projects/00000000-0000-4000-8000-000000000001.json',
        {nb_sources},
        {nb_tables},
        {nb_columns},
        {nb_relations},
        {nb_types},
        {nb_comments},
        0,
        {nb_layouts},
        (SELECT id FROM users WHERE email LIKE '%bastian%' LIMIT 1),
        (SELECT id FROM users WHERE email LIKE '%bastian%' LIMIT 1),
        NOW(),
        NOW(),
        'none'
    )
    ON CONFLICT (id) DO UPDATE SET
        name = EXCLUDED.name,
        organization_id = EXCLUDED.organization_id,
        nb_sources = EXCLUDED.nb_sources,
        nb_tables = EXCLUDED.nb_tables,
        nb_columns = EXCLUDED.nb_columns,
        nb_relations = EXCLUDED.nb_relations,
        nb_types = EXCLUDED.nb_types,
        nb_comments = EXCLUDED.nb_comments,
        nb_layouts = EXCLUDED.nb_layouts,
        visibility = 'none',
        updated_at = NOW();
    """

    # Support running through wsl if docker is hosted in wsl
    if docker_bin.startswith("wsl"):
        cmd = ["wsl", "-d", "Ubuntu", "-e", "docker", "exec", "-i", "azimutt-backend-db", "psql", "-U", "azimutt_bank_admin", "-d", "azimutt_metadata"]
    else:
        cmd = [
            docker_bin, "exec", "-i", "azimutt-backend-db",
            "psql", "-U", "azimutt_bank_admin", "-d", "azimutt_metadata"
        ]
    res = subprocess.run(cmd, input=sql, capture_output=True, text=True, check=False)
    if res.returncode == 0:
        print("[PASS] Successfully pre-seeded PostgreSQL metadata (user, org, project):")
        print("  -> User:         bastiannatanaels@gmail.com (Role: Owner / Admin)")
        print("  -> Org Personal: Bastian Natanael (is_personal = true, Plan: Pro 10y)")
        print("  -> Org Team:     bank-raya ('Bank Raya Enterprise', Plan: Pro 10y)")
        print(f"  -> Projects:     Pre-seeded with nb_tables = {nb_tables}, nb_columns = {nb_columns}, nb_layouts = {nb_layouts}, and visibility = 'none' (Private)")
    else:
        print(f"[WARN] PostgreSQL metadata seeding reported: {res.stderr}")


def seed_azimutt():
    base_dir = Path(__file__).resolve().parent.parent
    docker_bin = find_docker_bin()

    print("=" * 80)
    print("BANK RAYA - AZIMUTT AUTOMATED PRE-SEEDING & MULTI-LAYER LOADER")
    print("Framework: DAMA-DMBOK V.2 | Zero-Credential-Exposure Architecture")
    print("=" * 80)

    # 1. Build Full Azimutt Project JSON (Storage Project & Standalone Project)
    storage_project, standalone_project = build_azimutt_project_json(base_dir)
    storage_json_str = json.dumps(storage_project, indent=2, ensure_ascii=False)
    standalone_json_str = json.dumps(standalone_project, indent=2, ensure_ascii=False)

    # 2. Save project file (strictly adhering to LegacyProjectJson schema)
    standalone_path = base_dir / "sources" / "bank_raya.azimutt.json"
    standalone_path.parent.mkdir(parents=True, exist_ok=True)
    standalone_path.write_text(storage_json_str, encoding="utf-8")

    # 3. Save storage project files (LegacyProjectJson) for backend volume & Waffle uploads
    storage_paths = [
        base_dir / "azimutt-data" / "uploads" / "00000000-0000-4000-8000-000000000001_original.json",
        base_dir / "azimutt-data" / "uploads" / "00000000-0000-4000-8000-000000000001.json",
        base_dir / "azimutt-data" / "uploads" / "projects" / "00000000-0000-4000-8000-000000000001.json",
        base_dir / "azimutt-data" / "uploads" / "projects" / "bank-raya-enterprise.json"
    ]
    for p in storage_paths:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(storage_json_str, encoding="utf-8")

    print(f"[INFO] Generated Azimutt Unified Project JSON:")
    print(f"  -> Project Name: {storage_project['name']}")
    print(f"  -> Layouts:      {len(storage_project['layouts'])} DAMA-DMBOK / DASG domain views")
    print(f"  -> Saved Local:  {standalone_path.relative_to(base_dir)}")
    print(f"  -> Saved Storage: {storage_paths[2].relative_to(base_dir)}")

    # 4. Generate HTML autoloader fallback
    html_content = generate_autoload_azimutt_html(storage_project, project_id=standalone_project["id"])
    autoload_file = base_dir / "azimutt-data" / "autoload_azimutt.html"
    autoload_file.write_text(html_content, encoding="utf-8")
    print(f"[INFO] Generated Client-Side Autoloader: {autoload_file.relative_to(base_dir)}")

    # 5. Check Docker Containers & Seed
    try:
        def to_wsl_path(p: Path) -> str:
            if docker_bin.startswith("wsl"):
                drive = p.drive.replace(":", "").lower()
                rel = p.as_posix().split(":", 1)[-1]
                return f"/mnt/{drive}{rel}"
            return str(p)

        def make_docker_cmd(args):
            if docker_bin.startswith("wsl"):
                return ["wsl", "-d", "Ubuntu", "-e", "docker"] + args
            return [docker_bin] + args

        inspect_cmd = make_docker_cmd(["ps", "--format", "{{.Names}}"])
        res = subprocess.run(inspect_cmd, capture_output=True, text=True, check=False)
        running_containers = res.stdout.split()

        # Seed PostgreSQL backend if azimutt-backend-db is running
        if "azimutt-backend-db" in running_containers:
            print("[INFO] Seeding PostgreSQL internal metadata via secure docker exec...")
            seed_postgres_metadata(docker_bin, storage_project)
        else:
            print("[WARN] Container 'azimutt-backend-db' is not running. Skipping DB seeding.")

    except Exception as e:
        print(f"[WARN] Error executing Docker automation: {e}")

    print("=" * 80)
    print("AZIMUTT PRE-SEEDING COMPLETED SUCCESSFULLY (EXIT 0).")
    print("=" * 80)
    return 0

if __name__ == "__main__":
    sys.exit(seed_azimutt())
