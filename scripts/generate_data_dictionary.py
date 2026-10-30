#!/usr/bin/env python3
"""
Bank Raya - Enterprise Data Catalog & Dictionary HTML Generator
Generates a standalone, interactive, offline-ready HTML Data Catalog for auditors,
management, and cross-functional teams (DAMA-DMBOK V.2 & DASG 11-Domain Governance).
"""

import sys
import json
import re
from pathlib import Path
from datetime import datetime

try:
    import yaml
except ImportError:
    yaml = None

def generate_html_catalog():
    base_dir = Path(__file__).resolve().parent.parent
    schema_path = base_dir / "sources" / "bank_raya_unified_schema.json"
    dbt_path = base_dir / "inputs" / "multi_platform" / "dbt_schema.yml"
    docs_dir = base_dir / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    out_file = docs_dir / "data_dictionary.html"

    if not schema_path.exists():
        print(f"[ERROR] Unified schema not found at {schema_path}")
        return False

    with open(schema_path, "r", encoding="utf-8") as f:
        schema_data = json.load(f)

    dasg_domains = []
    if dbt_path.exists() and yaml:
        with open(dbt_path, "r", encoding="utf-8") as f:
            dbt_data = yaml.safe_load(f)
            dasg_domains = dbt_data.get("dasg_domains", [])

    # Load dynamic domains from config/domains.yaml
    domains_file = base_dir / "config" / "domains.yaml"
    domains_config = {}
    if domains_file.exists() and yaml:
        with open(domains_file, "r", encoding="utf-8") as f:
            domains_config = yaml.safe_load(f).get("domains", {})

    domain_buttons_list = ['<button class="dasg-btn active" onclick="filterByDASG(\'all\', this)">Semua Domain</button>']
    for d_key, d_info in domains_config.items():
        d_name = d_info.get("name", d_key)
        domain_buttons_list.append(f'<button class="dasg-btn" onclick="filterByDASG(\'{d_key.lower()}\', this)">{d_name}</button>')
    domain_buttons_str = "\n            ".join(domain_buttons_list)

    tables = schema_data.get("tables", [])
    relations = schema_data.get("relations", [])
    types = schema_data.get("types", [])

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Build Mermaid diagram string
    mermaid_lines = ["erDiagram"]
    for t in tables:
        t_id = f"{t['schema']}_{t['table']}"
        for col in t.get("columns", []):
            c_name = col["name"]
            c_type = col["type"].replace(" ", "_").replace("(", "_").replace(")", "_").replace("<", "_").replace(">", "_").replace(",", "_")
            mermaid_lines.append(f"    {t_id} {{\n        {c_type} {c_name}\n    }}")

    for rel in relations:
        src_id = f"{rel['src']['schema']}_{rel['src']['table']}"
        ref_id = f"{rel['ref']['schema']}_{rel['ref']['table']}"
        mermaid_lines.append(f'    {src_id} }}o--|| {ref_id} : "{rel["name"]}"')

    mermaid_diagram = "\n".join(mermaid_lines)

    # HTML template
    html_content = f"""<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bank Raya - Enterprise Data Dictionary & Catalog (DASG 11-Domain)</title>
    <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
    <style>
        :root {{
            --primary: #0052cc;
            --secondary: #172b4d;
            --accent: #0065ff;
            --bg: #f4f5f7;
            --surface: #ffffff;
            --border: #dfe1e6;
            --text: #172b4d;
            --muted: #6b778c;
            --success: #36b37e;
            --warning: #ffab00;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.5;
            padding: 24px;
        }}
        .header {{
            background: linear-gradient(135deg, #0747a6, #0052cc);
            color: white;
            padding: 28px;
            border-radius: 12px;
            margin-bottom: 24px;
            box-shadow: 0 4px 12px rgba(0,82,204,0.15);
        }}
        .header h1 {{ font-size: 26px; margin-bottom: 6px; font-weight: 700; }}
        .header p {{ font-size: 14px; opacity: 0.9; }}
        .meta-badges {{ display: flex; gap: 10px; margin-top: 14px; flex-wrap: wrap; }}
        .badge {{
            background: rgba(255,255,255,0.2);
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
        }}
        .dasg-bar {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 16px;
            margin-bottom: 20px;
        }}
        .dasg-header {{
            font-size: 13px;
            font-weight: 700;
            color: var(--muted);
            text-transform: uppercase;
            margin-bottom: 10px;
        }}
        .dasg-buttons {{
            display: flex;
            gap: 6px;
            flex-wrap: wrap;
        }}
        .dasg-btn {{
            padding: 5px 12px;
            border-radius: 6px;
            border: 1px solid var(--border);
            background: #fafbfc;
            color: var(--secondary);
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }}
        .dasg-btn:hover {{ background: #ebecf0; }}
        .dasg-btn.active {{ background: var(--primary); color: white; border-color: var(--primary); }}
        .search-bar {{
            margin-bottom: 24px;
            display: flex;
            gap: 12px;
        }}
        .search-bar input {{
            flex: 1;
            padding: 12px 16px;
            border: 1px solid var(--border);
            border-radius: 8px;
            font-size: 15px;
            outline: none;
            background: var(--surface);
        }}
        .search-bar input:focus {{ border-color: var(--primary); box-shadow: 0 0 0 2px rgba(0,82,204,0.2); }}
        .tabs {{
            display: flex;
            gap: 8px;
            margin-bottom: 20px;
            border-bottom: 2px solid var(--border);
            padding-bottom: 8px;
        }}
        .tab-btn {{
            padding: 8px 16px;
            background: none;
            border: none;
            font-weight: 600;
            color: var(--muted);
            cursor: pointer;
            border-radius: 6px;
        }}
        .tab-btn.active {{ background: var(--primary); color: white; }}
        .table-card {{
            background: var(--surface);
            border-radius: 10px;
            border: 1px solid var(--border);
            margin-bottom: 24px;
            overflow: hidden;
            box-shadow: 0 2px 6px rgba(0,0,0,0.03);
        }}
        .table-header {{
            background: #fafbfc;
            padding: 16px 20px;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .table-title {{ font-size: 17px; font-weight: 700; color: var(--secondary); }}
        .table-desc {{ font-size: 13px; color: var(--muted); margin-top: 4px; }}
        .badge-group {{ display: flex; gap: 8px; align-items: center; }}
        .table-badge {{
            background: #ebecf0;
            color: var(--secondary);
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
        }}
        .dasg-badge {{
            background: #e6effc;
            color: var(--primary);
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 600;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}
        th, td {{
            padding: 10px 16px;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }}
        th {{ background: #fafbfc; font-weight: 600; color: var(--muted); }}
        tr:hover td {{ background: #f8f9fa; }}
        .type-pill {{
            background: #e6effc;
            color: var(--primary);
            padding: 2px 6px;
            border-radius: 4px;
            font-family: monospace;
            font-size: 12px;
            font-weight: 600;
        }}
        .pk-icon {{ color: #ffab00; font-weight: bold; margin-right: 4px; }}
        .diagram-container {{
            background: var(--surface);
            padding: 24px;
            border-radius: 10px;
            border: 1px solid var(--border);
            margin-bottom: 24px;
            text-align: center;
        }}
        .linter-box {{
            background: #fff8e6;
            border-left: 4px solid var(--warning);
            padding: 16px;
            border-radius: 6px;
            margin-bottom: 24px;
            font-size: 13px;
        }}
        .linter-title {{ font-weight: 700; margin-bottom: 6px; color: #8f6b00; }}
    </style>
</head>
<body>

    <div class="header">
        <h1>🏛️ Bank Raya Enterprise Data Catalog & Dictionary</h1>
        <p>Framework: DAMA-DMBOK V.2 & Bank Raya DASG Architecture</p>
        <div class="meta-badges">
            <span class="badge">Generated: {now_str}</span>
            <span class="badge">Total Tabel: {len(tables)}</span>
            <span class="badge">Total Relasi: {len(relations)}</span>
            <span class="badge">Arsitektur Domain: {len(domains_config)} Domain</span>
        </div>
    </div>

    <div class="linter-box">
        <div class="linter-title">🛡️ Shift-Left Linter & Governance Integrity Summary:</div>
        <div>• <b>Enterprise Governance:</b> Sinkronisasi multi-platform metadata otomatis dengan validasi DAMA-DMBOK V.2.</div>
        <div>• <b>Zero-Manual Automation:</b> Skema terpadu dikompilasi secara deterministik untuk ChartDB, Azimutt, dan Data Catalog.</div>
    </div>

    <div class="dasg-bar">
        <div class="dasg-header">Bank Raya DASG Domain Filter:</div>
        <div class="dasg-buttons">
            {domain_buttons_str}
        </div>
    </div>

    <div class="search-bar">
        <input type="text" id="searchInput" placeholder="Cari nama tabel, kolom, tipe data, atau deskripsi bisnis..." onkeyup="filterCatalog()">
    </div>

    <div class="tabs">
        <button class="tab-btn active" onclick="switchTab('dictionary')">📖 Kamus Data Lengkap (Data Dictionary)</button>
        <button class="tab-btn" onclick="switchTab('erd')">📊 Visualisasi ERD (Mermaid)</button>
    </div>

    <div id="erdView" class="diagram-container" style="display: none;">
        <h3 style="margin-bottom: 16px; color: var(--secondary);">Unified Entity-Relationship Diagram</h3>
        <pre class="mermaid">
{mermaid_diagram}
        </pre>
    </div>

    <div id="dictionaryView">
"""

    for tbl in tables:
        schema = tbl.get("schema", "default")
        table_name = tbl.get("table", tbl.get("name", ""))
        comment = tbl.get("comment", "-")
        pk_cols = tbl.get("primaryKey", {}).get("columns", []) if tbl.get("primaryKey") else []

        # Extract DASG domain from table or comment
        domain_val = tbl.get("domain")
        if domain_val:
            dasg_domain = domain_val.lower()
            dasg_subdomain = tbl.get("subdomain", "general").lower()
        else:
            dasg_match = re.search(r"DASG:\s*(domain_\d+|[A-Za-z0-9_]+)/([^\s\|\]]+)", comment)
            dasg_domain = dasg_match.group(1).lower() if dasg_match else "unassigned"
            dasg_subdomain = dasg_match.group(2).lower() if dasg_match else "general"

        html_content += f"""
        <div class="table-card" data-table="{schema}.{table_name}" data-domain="{dasg_domain}" data-subdomain="{dasg_subdomain}">
            <div class="table-header">
                <div>
                    <div class="table-title">{schema}.{table_name}</div>
                    <div class="table-desc">{comment}</div>
                </div>
                <div class="badge-group">
                    <span class="dasg-badge">DASG: {dasg_domain} / {dasg_subdomain}</span>
                    <span class="table-badge">{schema}</span>
                </div>
            </div>
            <table>
                <thead>
                    <tr>
                        <th style="width: 25%;">Nama Kolom</th>
                        <th style="width: 20%;">Tipe Data</th>
                        <th style="width: 15%;">Atribut</th>
                        <th style="width: 40%;">Deskripsi Bisnis / Metrik</th>
                    </tr>
                </thead>
                <tbody>
        """

        for col in tbl.get("columns", []):
            c_name = col.get("name")
            c_type = col.get("type")
            is_pk = c_name in pk_cols
            is_pii = col.get("pii", False)
            rules_str = col.get("data_rules", "")
            nullable_str = "NULL" if col.get("nullable", True) else "NOT NULL"
            c_comment = col.get("comment") or "-"

            pk_badge = '<span class="pk-icon" title="Primary Key">🔑 PK</span> ' if is_pk else ''
            pii_badge = '<span class="pk-icon" style="color: #e11d48; margin-left: 6px;" title="Data Terproteksi PII">🔒 PII</span> ' if is_pii else ''
            rules_info = f'<br><small style="color: #d97706;"><b>Rules:</b> {rules_str}</small>' if rules_str else ''

            html_content += f"""
                    <tr>
                        <td><strong>{pk_badge}{pii_badge}{c_name}</strong></td>
                        <td><span class="type-pill">{c_type}</span></td>
                        <td><small style="color: var(--muted);">{nullable_str}</small></td>
                        <td>{c_comment}{rules_info}</td>
                    </tr>
            """

        html_content += """
                </tbody>
            </table>
        </div>
        """

    html_content += """
    </div>

    <script>
        mermaid.initialize({ startOnLoad: true, theme: 'neutral' });

        let currentDomain = 'all';

        function switchTab(tab) {
            document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
            if (tab === 'dictionary') {
                document.getElementById('dictionaryView').style.display = 'block';
                document.getElementById('erdView').style.display = 'none';
                event.target.classList.add('active');
            } else {
                document.getElementById('dictionaryView').style.display = 'none';
                document.getElementById('erdView').style.display = 'block';
                event.target.classList.add('active');
            }
        }

        function filterByDASG(domain, btn) {
            currentDomain = domain;
            document.querySelectorAll('.dasg-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            filterCatalog();
        }

        function filterCatalog() {
            const query = document.getElementById('searchInput').value.toLowerCase();
            const cards = document.querySelectorAll('.table-card');

            cards.forEach(card => {
                const text = card.innerText.toLowerCase();
                const cardDomain = card.getAttribute('data-domain');

                const matchesQuery = text.includes(query);
                const matchesDomain = (currentDomain === 'all' || cardDomain.includes(currentDomain) || currentDomain.includes(cardDomain));

                if (matchesQuery && matchesDomain) {
                    card.style.display = 'block';
                } else {
                    card.style.display = 'none';
                }
            });
        }
    </script>
</body>
</html>
"""

    out_file.write_text(html_content, encoding="utf-8")
    print(f"[PASS] Standalone HTML Data Catalog generated: {out_file.relative_to(base_dir)}")
    return True

if __name__ == "__main__":
    generate_html_catalog()
