#!/usr/bin/env python3
"""
Bank Raya - Generic Change Request Loader & SSoT Schema Compiler
Standard: DAMA-DMBOK V.2 | DASG 11-Domain Taxonomy | Zero-Credential-Exposure

Satu fungsi `compile_schema()` dipakai oleh SEMUA konsumen (transpiler, ChartDB seeder,
katalog data dictionary, Azimutt seeder, verify_setup, dan test suite).

Fitur & Aturan:
1. Validasi ketat manifest di changes/ sebelum kompilasi (domain, owners, change_type, duplikasi, relasi).
2. Penolakan file .draft.yaml sebelum docker build.
3. Idempoten untuk add_columns; deteksi konflik tipe -> FAIL.
4. Layout otomatis dan deterministik: kolom per domain, baris per tabel, tinggi dihitung dari jumlah kolom.
   Posisi 9 tabel baseline dimuat dari config/layout_overrides.yaml.
5. Lint domain terhadap config/domains.yaml.
6. Warning penamaan BigQuery (SUBDOMAIN__KONTEKS).
"""

import sys
import os
import re
import json
import copy
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

# Pastikan scripts/ dapat mengimpor sync_multiplatform_metadata
SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from sync_multiplatform_metadata import MultiPlatformMetadataParser, AzimuttTranspiler


def load_yaml_file(path: Path) -> dict:
    """Load YAML file with fallback if pyyaml is missing."""
    if not path.exists():
        return {}
    content = path.read_text(encoding="utf-8")
    if yaml is not None:
        return yaml.safe_load(content) or {}
    # Simple fallback parser for basic YAML if pyyaml not installed
    import json
    try:
        return json.loads(content)
    except Exception:
        return {}


def get_domains_config(base_dir: Path) -> dict:
    """Memuat konfigurasi 11 domain DASG dari config/domains.yaml."""
    domains_file = base_dir / "config" / "domains.yaml"
    data = load_yaml_file(domains_file)
    return data.get("domains", {})


def get_layout_overrides(base_dir: Path) -> dict:
    """Memuat koordinat override visual kanvas dari config/layout_overrides.yaml."""
    overrides_file = base_dir / "config" / "layout_overrides.yaml"
    data = load_yaml_file(overrides_file)
    return data.get("overrides", {})


def validate_manifest(manifest: dict, file_name: str, domains_config: dict, strict: bool = True):
    """Validasi semantik manifest perubahan dan proteksi kebocoran IP."""
    # 0. Proteksi Zero-Credential-Exposure: Tolak IP literal (misal: 172.18.99.10)
    manifest_str = json.dumps(manifest)
    ip_pattern = re.compile(r'\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3})\b')
    ip_match = ip_pattern.search(manifest_str)
    if ip_match:
        raise ValueError(
            f"[SECURITY FAIL] Alamat IP internal literal '{ip_match.group(0)}' terdeteksi pada manifest {file_name}. "
            f"Hanya alias/hostname simbolis (misal: 'oltp_host') yang diizinkan untuk mencegah paparan credential/infrastruktur."
        )

    # 1. Cek change_type (hanya new_table dan add_columns)
    chg_type = manifest.get("change_type")
    valid_change_types = ["new_table", "add_columns"]
    if chg_type not in valid_change_types:
        raise ValueError(
            f"[FAIL] Jenis perubahan '{chg_type}' tidak didukung pada file {file_name}. "
            f"Pilihan sah: {valid_change_types}"
        )

    # 2. Cek domain
    domain = manifest.get("domain")
    if not domain or domain.upper() not in domains_config:
        raise ValueError(
            f"[FAIL] Domain '{domain}' pada file {file_name} tidak valid / tidak dikenal. "
            f"Daftar domain sah dari config/domains.yaml: {list(domains_config.keys())}"
        )

    # 3. Cek strict mode: owner, ticket, domain wajib diisi
    if strict:
        ticket = manifest.get("ticket")
        if not ticket or not str(ticket).strip():
            raise ValueError(
                f"[FAIL] Nomor tiket Jira wajib diisi (--strict aktif) pada manifest {file_name}"
            )
        owners = manifest.get("owners") or {}
        if not owners.get("data_owner") or not str(owners.get("data_owner")).strip():
            raise ValueError(
                f"[FAIL] Data owner wajib diisi (--strict aktif) pada manifest {file_name}"
            )

    # 4. Cek keberadaan tabel / kolom
    tables = manifest.get("tables")
    if not tables:
        # Top-level single table format
        if "table_name" in manifest:
            tables = [manifest]
        else:
            raise ValueError(f"[FAIL] Manifest {file_name} tidak memuat definisi tabel atau 'table_name'")

    for t in tables:
        t_name = t.get("table_name") or t.get("name")
        if not t_name:
            raise ValueError(f"[FAIL] Definisi tabel tanpa nama pada manifest {file_name}")
        cols = t.get("columns", [])
        if chg_type in ["new_table", "add_columns"] and not cols:
            raise ValueError(f"[FAIL] Tabel '{t_name}' pada manifest {file_name} tidak memiliki daftar kolom")


def compute_table_dimensions(num_columns: int) -> tuple[int, int]:
    """Menghitung dimensi kotak tabel pada kanvas (width, height) secara deterministik."""
    width = 280
    header_height = 60
    row_height = 28
    footer_padding = 40
    height = header_height + (row_height * num_columns) + footer_padding
    return width, height


def compute_layout(tables: list, domains_config: dict, layout_overrides: dict) -> dict:
    """
    Menghitung posisi visual (x, y, color) tiap tabel tanpa tumpang tindih.
    9 tabel baseline memakai koordinat presisi dari config/layout_overrides.yaml.
    Tabel baru diatur kolom per domain dengan baris proporsional tinggi kolom.
    """
    layout_map = {}
    domain_columns = {}  # domain -> current_y
    domain_col_index = {}  # domain -> col_idx

    # Kumpulkan domain dari tabel yang tidak di-override
    unassigned_col_idx = 0
    START_X = 1360
    COL_WIDTH = 380
    VERTICAL_GAP = 60

    for tbl in tables:
        schema = tbl["schema"]
        name = tbl["name"]
        fqn = f"{schema}.{name}"

        if fqn in layout_overrides:
            ov = layout_overrides[fqn]
            layout_map[fqn] = {
                "x": ov["x"],
                "y": ov["y"],
                "color": ov["color"]
            }
        else:
            domain = tbl.get("domain", "UNASSIGNED").upper()
            if domain not in domain_col_index:
                domain_col_index[domain] = unassigned_col_idx
                domain_columns[domain] = 60
                unassigned_col_idx += 1

            col_x = START_X + (domain_col_index[domain] * COL_WIDTH)
            curr_y = domain_columns[domain]

            num_cols = len(tbl.get("columns", []))
            _, h = compute_table_dimensions(num_cols)

            domain_color = domains_config.get(domain, {}).get("color", "#0284c7")

            layout_map[fqn] = {
                "x": col_x,
                "y": curr_y,
                "color": domain_color
            }

            # Geser Y untuk tabel berikutnya dalam domain yang sama
            domain_columns[domain] = curr_y + h + VERTICAL_GAP

    # Verifikasi tumpang tindih (Overlap Assertion)
    boxes = []
    for tbl in tables:
        fqn = f"{tbl['schema']}.{tbl['name']}"
        pos = layout_map[fqn]
        num_cols = len(tbl.get("columns", []))
        w, h = compute_table_dimensions(num_cols)
        boxes.append({
            "fqn": fqn,
            "x1": pos["x"],
            "y1": pos["y"],
            "x2": pos["x"] + w,
            "y2": pos["y"] + h
        })

    overlaps = []
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            b1 = boxes[i]
            b2 = boxes[j]
            # Bounding box intersection check
            if not (b1["x2"] <= b2["x1"] or b2["x2"] <= b1["x1"] or
                    b1["y2"] <= b2["y1"] or b2["y2"] <= b1["y1"]):
                overlaps.append((b1["fqn"], b2["fqn"]))

    if overlaps:
        raise ValueError(f"[FAIL] Tumpang tindih kanvas terdeteksi antara tabel: {overlaps}")

    return layout_map


def lint_bigquery_naming(tables: list):
    """
    Aturan penamaan BigQuery (SUBDOMAIN__KONTEKS vs tanpa awalan subdomain):
    WARN saja, tidak ada error, sampai DASG memutuskan standar final.
    """
    for tbl in tables:
        platform = tbl.get("platform", "")
        schema = tbl.get("schema", "")
        name = tbl.get("name", "")

        is_bq = "BigQuery" in platform or schema in ["dataraw", "datastaging", "datamart"]
        if is_bq:
            if "__" not in name:
                print(
                    f"  [WARN] BigQuery naming audit: Tabel '{schema}.{name}' tidak menggunakan "
                    f"awalan 'SUBDOMAIN__KONTEKS'. Menunggu keputusan formal DASG."
                )


def compile_schema(
    base_dir: Path = None,
    changes_dir: str = "changes",
    strict: bool = True,
    write_files: bool = True
) -> dict:
    """
    Fungsi Utama Single-Source-of-Truth Kompilasi Skema Bank Raya.
    Memvalidasi dan menggabungkan manifest perubahan ke atas skema baseline.
    """
    if base_dir is None:
        base_dir = BASE_DIR

    changes_path = base_dir / changes_dir
    domains_config = get_domains_config(base_dir)
    layout_overrides = get_layout_overrides(base_dir)

    # 1. Cek keberadaan file .draft.yaml di direktori changes (Kecuali _source)
    if changes_path.exists():
        draft_files = [f for f in changes_path.iterdir() if f.name.endswith(".draft.yaml") or f.name.endswith(".draft.yml")]
        if draft_files:
            raise ValueError(
                f"[FAIL] File draft terdeteksi pada changes/: {[df.name for df in draft_files]}. "
                f"Selesaikan TODO dan ubah ekstensi menjadi .yaml sebelum menjalankan pipeline!"
            )

    # 2. Parse Baseline dari inputs/multi_platform/
    parser = MultiPlatformMetadataParser(base_dir)
    parser.parse_all()

    baseline_tables = copy.deepcopy(parser.tables)
    baseline_relations = copy.deepcopy(parser.relations)

    # 3. Baca dan gabungkan manifest yang valid dari changes/
    manifest_files = []
    if changes_path.exists():
        for f in sorted(changes_path.iterdir()):
            if f.is_file() and (f.suffix in [".yaml", ".yml"]) and not f.name.endswith(".draft.yaml") and not f.name.endswith(".draft.yml"):
                manifest_files.append(f)

    if manifest_files:
        print(f"[INFO] Memproses {len(manifest_files)} change request manifest dari {changes_dir}/...")

    for mf in manifest_files:
        # Cek alamat IP literal pada teks manifest (Zero-Credential & Security Policy)
        raw_text = mf.read_text(encoding="utf-8")
        ip_matches = re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", raw_text)
        if ip_matches:
            raise ValueError(
                f"[SECURITY FAIL] Alamat IP literal '{ip_matches[0]}' terdeteksi pada manifest {mf.name}. "
                f"Hanya alias logis (misal: 'core_db_primary') yang diperbolehkan!"
            )

        mdata = load_yaml_file(mf)
        validate_manifest(mdata, mf.name, domains_config, strict=strict)

        chg_type = mdata.get("change_type")
        domain = mdata.get("domain", "UNASSIGNED").upper()
        subdomain = mdata.get("subdomain", "")
        ticket = mdata.get("ticket", "")
        platform = mdata.get("target_platform", "Relational")

        tables_data = mdata.get("tables") or [mdata]
        for tbl_in in tables_data:
            schema = tbl_in.get("schema", "dbo").lower()
            t_name = (tbl_in.get("table_name") or tbl_in.get("name")).lower()
            key = (schema, t_name)

            if chg_type == "new_table":
                # Validasi duplikasi dengan isi berbeda
                if key in parser.tables:
                    existing = parser.tables[key]
                    existing_col_types = {c["name"].lower(): c["type"].lower() for c in existing["columns"]}
                    new_col_types = {c["name"].lower(): c["type"].lower() for c in tbl_in.get("columns", [])}
                    if existing_col_types != new_col_types:
                        raise ValueError(
                            f"[FAIL] Tabel duplikat terdeteksi dengan definisi berbeda: '{schema}.{t_name}' pada {mf.name}"
                        )
                    # Jika identik -> idempoten, lanjutkan
                else:
                    # Daftarkan tabel baru
                    parsed_columns = []
                    for c in tbl_in.get("columns", []):
                        parsed_columns.append({
                            "name": c["name"],
                            "type": c["type"],
                            "nullable": c.get("nullable", True) if c.get("nullable") is not None else True,
                            "default": c.get("default"),
                            "comment": c.get("comment", ""),
                            "pii": c.get("pii", False),
                            "data_rules": c.get("data_rules", "")
                        })

                    pk_def = None
                    pk_cols = tbl_in.get("primary_key")
                    if pk_cols:
                        if isinstance(pk_cols, str):
                            pk_cols = [pk_cols]
                        pk_def = {"name": f"pk_{t_name}", "columns": pk_cols}

                    table_obj = {
                        "schema": schema,
                        "name": t_name,
                        "platform": platform,
                        "domain": domain,
                        "subdomain": subdomain,
                        "ticket": ticket,
                        "columns": parsed_columns,
                        "primaryKey": pk_def,
                        "uniques": tbl_in.get("uniques", []),
                        "indexes": tbl_in.get("indexes", []),
                        "checks": [],
                        "comment": tbl_in.get("table_description") or tbl_in.get("comment", "")
                    }
                    parser.register_or_merge_table(schema, t_name, table_obj, f"CR:{mf.stem}")

            elif chg_type == "add_columns":
                if key not in parser.tables:
                    raise ValueError(
                        f"[FAIL] Tabel target '{schema}.{t_name}' untuk add_columns tidak ditemukan pada manifest {mf.name}"
                    )
                existing = parser.tables[key]
                existing_cols_map = {c["name"].lower(): c for c in existing["columns"]}

                for col in tbl_in.get("columns", []):
                    c_name_lower = col["name"].lower()
                    if c_name_lower in existing_cols_map:
                        ext_col = existing_cols_map[c_name_lower]
                        # Cek konflik tipe
                        if ext_col["type"].lower() != col["type"].lower():
                            raise ValueError(
                                f"[FAIL] Konflik tipe kolom '{col['name']}' pada tabel '{schema}.{t_name}': "
                                f"eksisting '{ext_col['type']}' vs baru '{col['type']}'"
                            )
                        # Tipe sama -> idempoten, jangan lakukan duplikasi
                    else:
                        existing["columns"].append({
                            "name": col["name"],
                            "type": col["type"],
                            "nullable": col.get("nullable", True) if col.get("nullable") is not None else True,
                            "default": col.get("default"),
                            "comment": col.get("comment", ""),
                            "pii": col.get("pii", False),
                            "data_rules": col.get("data_rules", "")
                        })

            # Proses relasi jika didefinisikan pada manifest
            for rel in tbl_in.get("relations", []):
                rel_name = rel.get("name") or f"fk_{t_name}_{rel.get('src_column')}"
                src_col = rel.get("src_column") or rel.get("src", {}).get("column")
                ref_sch = (rel.get("ref_schema") or rel.get("ref", {}).get("schema") or schema).lower()
                ref_tbl = (rel.get("ref_table") or rel.get("ref", {}).get("table")).lower()
                ref_col = rel.get("ref_column") or rel.get("ref", {}).get("column")

                # Validasi kolom sumber
                src_tbl_obj = parser.tables.get(key)
                if not any(c["name"].lower() == src_col.lower() for c in src_tbl_obj.get("columns", [])):
                    raise ValueError(
                        f"[FAIL] Relasi '{rel_name}' mereferensikan kolom sumber yang tidak ada: {schema}.{t_name}({src_col})"
                    )

                # Validasi tabel referensi
                ref_tbl_key = (ref_sch, ref_tbl)
                if ref_tbl_key not in parser.tables:
                    # Target tabel tidak dikenal sama sekali -> WARN unresolved_relations
                    print(
                        f"  [WARN] unresolved_relations: Target tabel '{ref_sch}.{ref_tbl}' tidak dikenal sama sekali. "
                        f"Relasi '{rel_name}' diabaikan dari kanvas visual dan tidak ada tabel palsu dibuat."
                    )
                    continue

                ref_tbl_obj = parser.tables[ref_tbl_key]
                if not any(c["name"].lower() == ref_col.lower() for c in ref_tbl_obj.get("columns", [])):
                    raise ValueError(
                        f"[FAIL] Relasi '{rel_name}' mereferensikan kolom target yang tidak ada pada tabel yang terdaftar '{ref_sch}.{ref_tbl}': "
                        f"kolom '{ref_col}' tidak ditemukan"
                    )

                parser.add_relation({
                    "name": rel_name,
                    "src": {"schema": schema, "table": t_name, "column": src_col},
                    "ref": {"schema": ref_sch, "table": ref_tbl, "column": ref_col}
                })

    # 4. Generate JSON Exporter
    exporter = AzimuttTranspiler(parser, base_dir)
    schema_dict = exporter.generate_azimutt_schema()

    # 5. Hitung Visual Layout Kanvas
    layout_map = compute_layout(schema_dict["tables"], domains_config, layout_overrides)
    schema_dict["layout_map"] = layout_map

    # 6. Audit Linter BigQuery Naming
    lint_bigquery_naming(schema_dict["tables"])

    # 7. Tulis File Sinkronisasi jika write_files=True
    if write_files:
        sources_dir = base_dir / "sources"
        azimutt_sources_dir = base_dir / "azimutt-data" / "sources"
        layouts_dir = base_dir / "layouts"
        azimutt_layouts_dir = base_dir / "azimutt-data" / "layouts"

        for d in [sources_dir, azimutt_sources_dir, layouts_dir, azimutt_layouts_dir]:
            d.mkdir(parents=True, exist_ok=True)

        # Unified Schema JSON
        schema_json_str = json.dumps(
            {"tables": schema_dict["tables"], "relations": schema_dict["relations"], "types": schema_dict.get("types", [])},
            indent=2,
            ensure_ascii=False
        )
        (sources_dir / "bank_raya_unified_schema.json").write_text(schema_json_str, encoding="utf-8")
        (azimutt_sources_dir / "bank_raya_unified_schema.json").write_text(schema_json_str, encoding="utf-8")

        # Unified SQL Import
        sql_content = exporter.generate_chartdb_sql()
        (sources_dir / "chartdb_unified_import.sql").write_text(sql_content, encoding="utf-8")
        (azimutt_sources_dir / "chartdb_unified_import.sql").write_text(sql_content, encoding="utf-8")

        # Domain Layouts
        layouts_dict = exporter.generate_domain_layouts()
        layouts_json_str = json.dumps(layouts_dict, indent=2, ensure_ascii=False)
        (layouts_dir / "bank_raya_domain_layouts.json").write_text(layouts_json_str, encoding="utf-8")
        (azimutt_layouts_dir / "bank_raya_domain_layouts.json").write_text(layouts_json_str, encoding="utf-8")

    return schema_dict


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Bank Raya Change Request Compiler & SSoT Validator")
    parser.add_argument("--no-strict", action="store_true", help="Nonaktifkan validasi strict (melonggarkan)")
    parser.add_argument("--validate-only", action="store_true", help="Hanya validasi tanpa menulis file")
    args = parser.parse_args()

    strict_flag = not args.no_strict
    validate_only = args.validate_only

    print("================================================================================")
    print("BANK RAYA - CHANGE REQUEST COMPILER & SSoT VALIDATOR")
    print("================================================================================")
    try:
        compiled = compile_schema(BASE_DIR, strict=strict_flag, write_files=not validate_only)
        nb_tables = len(compiled["tables"])
        nb_relations = len(compiled["relations"])
        print(f"[PASS] Kompilasi skema berhasil: {nb_tables} tabel, {nb_relations} relasi.")
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERROR] Kompilasi skema gagal:\n  {e}\n")
        sys.exit(1)
