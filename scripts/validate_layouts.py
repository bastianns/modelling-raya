import json
from pathlib import Path

def validate_all():
    schema_path = Path("sources/bank_raya_unified_schema.json")
    azimutt_path = Path("sources/bank_raya.azimutt.json")
    domain_layouts_path = Path("layouts/bank_raya_domain_layouts.json")

    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    source_tables = {}
    for t in schema["tables"]:
        full_id = f"{t['schema']}.{t['name']}"
        source_tables[full_id] = {c["name"] for c in t["columns"]}

    print(f"=== Unified Schema Tables ({len(source_tables)} tables) ===")
    for t, cols in sorted(source_tables.items()):
        print(f"  {t}: {len(cols)} columns")

    # 1. Validate layouts in bank_raya.azimutt.json
    print("\n=== Validating sources/bank_raya.azimutt.json layouts ===")
    with open(azimutt_path, "r", encoding="utf-8") as f:
        azimutt_data = json.load(f)

    validate_layouts_dict(azimutt_data.get("layouts", {}), source_tables)

    # 2. Validate layouts in layouts/bank_raya_domain_layouts.json
    print("\n=== Validating layouts/bank_raya_domain_layouts.json ===")
    with open(domain_layouts_path, "r", encoding="utf-8") as f:
        domain_layouts = json.load(f)
    if "layouts" in domain_layouts and isinstance(domain_layouts["layouts"], dict):
        domain_layouts = domain_layouts["layouts"]

    validate_layouts_dict(domain_layouts, source_tables)

def validate_layouts_dict(layouts: dict, source_tables: dict):
    col_errors = []
    pos_errors = []

    for layout_name, layout in layouts.items():
        seen_positions = {}
        for tbl in layout.get("tables", []):
            tbl_id = tbl.get("id")
            cols = tbl.get("columns", [])
            # 1. Check table existence
            if tbl_id not in source_tables:
                col_errors.append(f"Layout '{layout_name}': Table '{tbl_id}' does not exist in schema")
            else:
                # 2. Check every column in layout exists in the table
                for c in cols:
                    if c not in source_tables[tbl_id]:
                        col_errors.append(f"Layout '{layout_name}': Column '{c}' does not exist in table '{tbl_id}'")
            # 3. Check position uniqueness
            pos = tbl.get("position", {})
            pos_tuple = (pos.get("left"), pos.get("top"))
            if pos_tuple in seen_positions:
                pos_errors.append(f"Layout '{layout_name}': Duplicate position {pos_tuple} for '{tbl_id}' and '{seen_positions[pos_tuple]}'")
            else:
                seen_positions[pos_tuple] = tbl_id

    print(f"  Total Layouts checked: {len(layouts)}")
    print(f"  Column Errors: {len(col_errors)}")
    for err in col_errors:
        print(f"    - {err}")
    print(f"  Position Duplicate Errors: {len(pos_errors)}")
    for err in pos_errors:
        print(f"    - {err}")

if __name__ == "__main__":
    validate_all()
