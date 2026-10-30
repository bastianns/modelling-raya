#!/usr/bin/env python3
"""
Bank Raya - Change Request Document Importer (Conservative Markdown Parser)
Standard: DAMA-DMBOK V.2 & DASG Governance Policy

Membaca dokumen template "Data Modeling" (markdown) menjadi <nama>.draft.yaml.
Aturan Konservatif:
1. Baris pecah (sel pertama kosong, kelanjutan deskripsi/rules) digabung dengan menandai '# TODO(review)'.
2. PK, Domain, Subdomain, Owner, Relasi -> null / empty dengan penanda '# TODO(review)'.
3. Relasi TIDAK diambil dari teks ERD hasil ekstraksi gambar (harus eksplisit dari DASG).
4. Keluar dengan kode != 0 jika --check-todos dijalankan dan masih ada TODO.
"""

import sys
import re
from pathlib import Path


def clean_cell(cell: str) -> str:
    """Bersihkan tag html dan whitespace berlebih dari sel tabel markdown."""
    c = cell.strip()
    c = c.replace("<br>", " ").replace("<br/>", " ").replace("<br />", " ")
    c = re.sub(r"\s+", " ", c)
    return c.strip()


def parse_data_modeling_md(file_path: Path):
    """Parse Data Modeling.md secara konservatif."""
    content = file_path.read_text(encoding="utf-8")
    lines = content.splitlines()

    tables = []
    current_table = None
    in_columns_table = False
    columns = []

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Deteksi metadata tabel
        if line.startswith("|**Table Name**|"):
            parts = [clean_cell(p) for p in line.split("|")[1:-1]]
            tbl_name = parts[1] if len(parts) > 1 else ""
            if current_table:
                current_table["columns"] = columns
                tables.append(current_table)
                columns = []
            current_table = {
                "table_name": tbl_name,
                "schema": "dbo",
                "database": "AGROBANKCORESYSTEM",
                "version": "1.0",
                "change_type": "new_table",
                "description": "",
                "columns": []
            }
            i += 1
            continue

        if current_table:
            if line.startswith("|**Schema Database**|"):
                parts = [clean_cell(p) for p in line.split("|")[1:-1]]
                current_table["schema"] = parts[1] if len(parts) > 1 else "dbo"
            elif line.startswith("|**Nama Database**|"):
                parts = [clean_cell(p) for p in line.split("|")[1:-1]]
                current_table["database"] = parts[1] if len(parts) > 1 else "AGROBANKCORESYSTEM"
            elif line.startswith("|**Version**|"):
                parts = [clean_cell(p) for p in line.split("|")[1:-1]]
                current_table["version"] = parts[1] if len(parts) > 1 else "1.0"
            elif line.startswith("|**Jenis Perubahan**|"):
                parts = [clean_cell(p) for p in line.split("|")[1:-1]]
                val = parts[1].lower() if len(parts) > 1 else "new table"
                if "add column" in val:
                    current_table["change_type"] = "add_columns"
                else:
                    current_table["change_type"] = "new_table"
            elif line.startswith("|**Table Description**|"):
                parts = [clean_cell(p) for p in line.split("|")[1:-1]]
                desc_text = " ".join(parts[1:])
                desc_text = desc_text.replace("**Deta**", "").replace("**il Kolom**", "").replace("**", "")
                desc_text = desc_text.replace("dengan in formasi", "dengan informasi")
                desc_text = re.sub(r"\s+", " ", desc_text).strip()
                current_table["description"] = desc_text

            # Deteksi header kolom
            if line.startswith("|**Nama Kolom**|"):
                in_columns_table = True
                i += 1
                continue

            if in_columns_table:
                # Jika baris separator markdown atau kosong
                if line.startswith("|---") or not line.startswith("|"):
                    i += 1
                    continue

                # Cek jika berganti section atau metadata tabel berikutnya
                if line.startswith("|**IP Database**|") or line.startswith("# **1.b.") or line.startswith("<!--"):
                    in_columns_table = False
                    i += 1
                    continue

                raw_cells = line.split("|")[1:-1]
                cells = [clean_cell(c) for c in raw_cells]

                # Cek baris pecah (sel pertama kosong)
                if len(cells) > 0 and not cells[0]:
                    # Baris pecah! Cari teks di sel berikutnya
                    stitched_text = " ".join([c for c in cells if c])
                    if columns:
                        # Gabungkan ke kolom sebelumnya jika sesuai
                        prev_col = columns[-1]
                        prev_col["data_rules"] = (prev_col["data_rules"] + " " + stitched_text).strip()
                        prev_col["stitched"] = True
                    else:
                        # Teks sebelum kolom pertama muncul
                        pass
                    i += 1
                    continue

                # Baris kolom normal
                col_name = cells[0] if len(cells) > 0 else ""
                col_desc = cells[1] if len(cells) > 1 else ""
                col_type = cells[2] if len(cells) > 2 else "varchar(50)"
                pii_raw = cells[3].lower() if len(cells) > 3 else "no"
                col_rules = cells[4] if len(cells) > 4 else ""

                # Cek apakah baris berikutnya adalah kelanjutan sel yang pecah
                stitched_flag = False
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if next_line.startswith("|") and not next_line.startswith("|---"):
                        next_cells = [clean_cell(c) for c in next_line.split("|")[1:-1]]
                        if len(next_cells) > 0 and not next_cells[0]:
                            # Baris berikutnya adalah kelanjutan!
                            extra_rules = " ".join([c for c in next_cells if c])
                            col_rules = (col_rules + " " + extra_rules).strip()
                            stitched_flag = True
                            i += 1  # Lewati baris kelanjutan

                is_pii = "yes" in pii_raw

                columns.append({
                    "name": col_name,
                    "type": col_type if col_type else "varchar(50)",
                    "description": col_desc,
                    "pii": is_pii,
                    "data_rules": col_rules,
                    "stitched": stitched_flag
                })

        i += 1

    if current_table:
        current_table["columns"] = columns
        tables.append(current_table)

    return tables


def emit_draft_yaml(table_dict: dict, out_file: Path):
    """Tulis manifest draft YAML dengan penanda TODO(review)."""
    t_name = table_dict["table_name"]
    chg_type = table_dict["change_type"]
    schema = table_dict["schema"]

    yaml_lines = [
        f"# ==============================================================================",
        f"# Bank Raya - Change Request Draft Manifest",
        f"# File: {out_file.name}",
        f"# Generated by: scripts/import_change_doc.py (Conservative Importer)",
        f"# STATUS: DRAFT (Memerlukan Konfirmasi & Review DASG)",
        f"# ==============================================================================",
        f"",
        f"ticket: null  # TODO(review): Masukkan nomor tiket Jira (misal: EDM-4012)",
        f"change_type: {chg_type}",
        f"target_platform: SQL Server (Legacy Core OLTP)  # Sesuai AGROBANKCORESYSTEM",
        f"schema: {schema.lower()}",
        f"table_name: {t_name.lower()}",
        f"version: \"{table_dict['version']}\"",
        f"table_description: \"{table_dict['description']}\"",
        f"",
        f"# --- GOVERNANCE & DOMAIN CLASSIFICATION ---",
        f"domain: null  # TODO(review): Tentukan domain DASG (contoh: LENDING, CORE_BANKING, SUPPORT_DATA)",
        f"subdomain: null  # TODO(review): Tentukan sub-domain DASG yang sah",
        f"",
        f"owners:  # TODO(review): Tentukan data owner, steward, dan custodian sesuai tiket Jira",
        f"  data_owner: null",
        f"  data_steward: null",
        f"  data_custodian: null",
        f"",
        f"# --- PRIMARY KEY & CONSTRAINTS ---",
        f"primary_key: null  # TODO(review): Tentukan Primary Key (misal: ['ACCOUNTNUMBER', 'SEQNUM'])",
        f"uniques: []",
        f"",
        f"# --- COLUMNS ---",
        f"columns:"
    ]

    for c in table_dict["columns"]:
        col_name = c["name"]
        col_type = c["type"]
        is_pii = "true" if c["pii"] else "false"
        desc = c["description"].replace('"', '\\"')
        rules = c["data_rules"].replace('"', '\\"')

        yaml_lines.append(f"  - name: {col_name}")
        yaml_lines.append(f"    type: {col_type}")
        yaml_lines.append(f"    nullable: null  # TODO(review): Tentukan apakah kolom ini nullable (true/false)")
        yaml_lines.append(f"    pii: {is_pii}")
        if desc:
            yaml_lines.append(f"    comment: \"{desc}\"")
        if rules:
            yaml_lines.append(f"    data_rules: \"{rules}\"")
        if c.get("stitched"):
            yaml_lines.append(f"    # TODO(review): Baris kolom ini digabungkan secara otomatis dari sel terpisah pada dokumen sumber")

    yaml_lines.extend([
        f"",
        f"# --- RELATIONS ---",
        f"# CATATAN DAMA-DMBOK: Relasi TIDAK diambil dari teks hasil ekstraksi gambar ERD.",
        f"# Relasi harus didefinisikan secara eksplisit oleh Data Architect / DASG.",
        f"relations: []  # TODO(review): Definisikan relasi formal jika ada (misal: ke ABCS_M_LNSCHD / ABCS_M_LNMAST)",
        f""
    ])

    out_file.write_text("\n".join(yaml_lines), encoding="utf-8")
    print(f"[GENERATED] Draft manifest disimpan ke: {out_file}")


def check_todos_in_dir(changes_dir: Path) -> int:
    """Cek apakah masih ada file .draft.yaml atau komentar TODO(review) yang belum diselesaikan."""
    draft_files = list(changes_dir.glob("*.draft.yaml")) + list(changes_dir.glob("*.draft.yml"))
    if draft_files:
        print(f"[FAIL] Ditemukan {len(draft_files)} file draft manifest yang belum di-finalize:")
        for df in draft_files:
            print(f"  - {df.name}")
        return 1

    todo_count = 0
    for yf in list(changes_dir.glob("*.yaml")) + list(changes_dir.glob("*.yml")):
        content = yf.read_text(encoding="utf-8")
        matches = re.findall(r"TODO\(review\)", content)
        if matches:
            print(f"[FAIL] File '{yf.name}' masih mengandung {len(matches)} penanda TODO(review).")
            todo_count += len(matches)

    if todo_count > 0:
        print(f"[FAIL] Total {todo_count} TODO(review) belum diselesaikan. Perubahan belum dapat diproses.")
        return 1

    print("[PASS] Tidak ada file .draft dan tidak ada TODO(review) yang tersisa.")
    return 0


def main():
    base_dir = Path(__file__).resolve().parent.parent
    source_file = base_dir / "changes" / "_source" / "Data Modeling.md"
    changes_dir = base_dir / "changes"
    changes_dir.mkdir(exist_ok=True)

    if "--check-todos" in sys.argv:
        exit_code = check_todos_in_dir(changes_dir)
        sys.exit(exit_code)

    if not source_file.exists():
        print(f"[ERROR] Dokumen sumber tidak ditemukan: {source_file}")
        sys.exit(1)

    print("================================================================================")
    print("BANK RAYA - CONSERVATIVE CHANGE REQUEST IMPORTER")
    print("================================================================================")
    print(f"Membaca dokumen: {source_file}")

    tables = parse_data_modeling_md(source_file)
    print(f"Ditemukan {len(tables)} definisi tabel pada dokumen.")

    for tbl in tables:
        t_name = tbl["table_name"]
        draft_file = changes_dir / f"{t_name}.draft.yaml"
        emit_draft_yaml(tbl, draft_file)

    print("\n[INFO] Validasi TODO pada direktori changes/:")
    todo_check = check_todos_in_dir(changes_dir)
    print("================================================================================")
    print(f"STATUS SELESAI IMPOR DOKUMEN: Exit Code {todo_check} (Sesuai spesifikasi, draft memerlukan konfirmasi).")
    print("================================================================================")
    sys.exit(todo_check)


if __name__ == "__main__":
    main()
