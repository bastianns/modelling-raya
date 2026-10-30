#!/usr/bin/env python3
"""
Bank Raya - ChartDB UI Automated Synchronizer via Playwright
Framework: DAMA-DMBOK V.2 | Zero-Credential-Exposure Architecture
Loads sources/chartdb_unified_import.sql into ChartDB using the official web UI.
"""

import os
import re
import sys
import time
import json
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

DEFAULT_DIAGRAM_NAME = "Bank Raya Unified ERD (DAMA-DMBOK 11-Domain)"

def parse_sql_expectations(sql_path: Path) -> dict:
    """Dynamically parses expected tables and foreign key relationships from SQL DDL."""
    if not sql_path.exists():
        raise FileNotFoundError(f"SQL file not found: {sql_path}")
    sql_text = sql_path.read_text(encoding="utf-8")

    # Match CREATE TABLE statements
    table_matches = re.findall(
        r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z0-9_."]+)',
        sql_text,
        re.IGNORECASE
    )
    # Match REFERENCES foreign key statements
    fk_matches = re.findall(
        r'REFERENCES\s+([a-zA-Z0-9_."]+)\s*\([^)]+\)',
        sql_text,
        re.IGNORECASE
    )

    clean_tables = [t.strip('`"[]') for t in table_matches]
    clean_fks = [f.strip('`"[]') for f in fk_matches]
    return {
        "tables_count": len(clean_tables),
        "relationships_count": len(clean_fks),
        "table_names": clean_tables,
        "fk_references": clean_fks
    }

def run_sync(
    chartdb_url: str = "http://127.0.0.1:8080",
    sql_path: Path = None,
    headless: bool = False,
    user_data_dir: Path = None,
    screenshot_dir: Path = None,
    keep_open: bool = False
) -> dict:
    base_dir = Path(__file__).resolve().parent.parent
    if sql_path is None:
        sql_path = base_dir / "sources" / "chartdb_unified_import.sql"

    # 1. Parse expectations dynamically from SQL source
    expectations = parse_sql_expectations(sql_path)
    exp_tables_count = expectations["tables_count"]
    exp_fks_count = expectations["relationships_count"]
    sql_content = sql_path.read_text(encoding="utf-8")

    # 2. Setup persistent user data dir outside repo
    if user_data_dir is None:
        user_data_dir = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "chartdb_playwright_profile"
    user_data_dir.mkdir(parents=True, exist_ok=True)

    # 3. Setup screenshots dir outside repo
    if screenshot_dir is None:
        screenshot_dir = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "chartdb_screenshots"
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    passed_checks = 0
    failed_checks = 0

    print("=" * 80)
    print("BANK RAYA - CHARTDB PLAYWRIGHT UI SYNCHRONIZER")
    print(f"Target URL:         {chartdb_url}")
    print(f"SQL Source:         {sql_path.name}")
    print(f"Dynamic Expected:   {exp_tables_count} tables, {exp_fks_count} relationships (parsed dynamically from SQL)")
    print(f"Browser Mode:       {'Headless' if headless else 'Headed (Visible GUI)'}")
    print(f"Profile Path:       {user_data_dir}")
    print(f"Screenshot Dir:     {screenshot_dir}")
    print("=" * 80)

    with sync_playwright() as p:
        # Launch persistent browser context
        context = p.chromium.launch_persistent_context(
            str(user_data_dir),
            headless=headless,
            viewport={"width": 1440, "height": 900},
            permissions=["clipboard-read", "clipboard-write"]
        )
        page = context.pages[0] if context.pages else context.new_page()

        print("\n[STEP 1/6] Navigating to ChartDB...")
        page.goto(chartdb_url, wait_until="networkidle")
        time.sleep(2)

        # Step 2: Idempotency deduplication check in IndexedDB
        print(f"[STEP 2/6] Checking and cleaning previous diagram instances ('{DEFAULT_DIAGRAM_NAME}')...")
        dedup_info = page.evaluate("""async (targetName) => {
            return new Promise((resolve) => {
                const req = indexedDB.open("ChartDB");
                req.onsuccess = (e) => {
                    const db = e.target.result;
                    if (!db.objectStoreNames.contains("diagrams")) return resolve({ cleaned: 0, count: 0 });
                    const storeNames = ["diagrams", "db_tables", "db_relationships"];
                    if (db.objectStoreNames.contains("config")) storeNames.push("config");
                    const tx = db.transaction(storeNames, "readwrite");
                    const diagStore = tx.objectStore("diagrams");
                    const tableStore = tx.objectStore("db_tables");
                    const relStore = tx.objectStore("db_relationships");
                    const confStore = db.objectStoreNames.contains("config") ? tx.objectStore("config") : null;

                    diagStore.getAll().onsuccess = (ev) => {
                        const diagrams = ev.target.result || [];
                        const targets = diagrams.filter(d => d.name === targetName || d.name === "SQL Import (postgresql)");
                        const idsToRemove = targets.length > 0 ? targets.map(t => t.id) : diagrams.map(d => d.id);
                        if (idsToRemove.length === 0) return resolve({ cleaned: 0, count: diagrams.length, removed_ids: [] });

                        tableStore.getAll().onsuccess = (tev) => {
                            (tev.target.result || []).forEach(t => {
                                if (idsToRemove.includes(t.diagramId)) tableStore.delete(t.id);
                            });
                        };
                        relStore.getAll().onsuccess = (rev) => {
                            (rev.target.result || []).forEach(r => {
                                if (idsToRemove.includes(r.diagramId)) relStore.delete(r.id);
                            });
                        };
                        idsToRemove.forEach(id => diagStore.delete(id));
                        if (confStore) {
                            confStore.clear();
                        }
                    };
                    tx.oncomplete = () => resolve({ cleaned: 1, success: true });
                    tx.onerror = (err) => resolve({ cleaned: 0, error: String(err) });
                };
                req.onerror = (err) => resolve({ cleaned: 0, error: String(err) });
            });
        }""", DEFAULT_DIAGRAM_NAME)
        print(f"  Dedup execution result: {dedup_info}")

        # Re-navigate so clean state is active
        page.goto(chartdb_url, wait_until="networkidle")
        time.sleep(2)

        ss_step1 = screenshot_dir / "step1_initial_loaded.png"
        page.screenshot(path=str(ss_step1))
        print(f"  [SCREENSHOT] Initial view: {ss_step1}")

        # Step 3: Select PostgreSQL
        print("\n[STEP 3/6] Selecting PostgreSQL engine in wizard dialog...")
        page.wait_for_selector('img[alt="PostgreSQL"]', timeout=30000)
        pg_btn = page.locator('img[alt="PostgreSQL"]').first
        pg_btn.click()
        time.sleep(1)

        continue_btn = page.locator('button:has-text("Continue")')
        if continue_btn.count() > 0 and continue_btn.first.is_visible():
            continue_btn.first.click()
            time.sleep(1)

        ss_step2 = screenshot_dir / "step2_postgres_selected.png"
        page.screenshot(path=str(ss_step2))
        print(f"  [SCREENSHOT] PostgreSQL selected: {ss_step2}")

        # Step 4: Verify role="dialog" and SQL Script tab
        print("\n[STEP 4/6] Locating [role='dialog'], switching to 'SQL Script' tab & pasting DDL...")
        dialog = page.locator('[role="dialog"]')
        if dialog.count() == 0 or not dialog.first.is_visible():
            failed_checks += 1
            raise RuntimeError("Database configuration dialog [role='dialog'] not found or not visible!")

        sql_tab_btn = dialog.locator('button:has-text("SQL Script")')
        if sql_tab_btn.count() == 0 or not sql_tab_btn.first.is_visible():
            failed_checks += 1
            raise RuntimeError("Tab 'SQL Script' button not found inside [role='dialog']!")

        sql_tab_btn.first.click()
        time.sleep(1)

        # Locate monaco editor specifically inside role="dialog"
        dialog_editors = dialog.locator(".monaco-editor").all()
        target_editor = None
        for ed in dialog_editors:
            text = ed.inner_text().strip()
            # Non-instruction editor (no pg_dump example text)
            if "pg_dump" not in text:
                target_editor = ed
                break

        if target_editor is None:
            failed_checks += 1
            raise RuntimeError(
                f"Target SQL input Monaco editor not found inside [role='dialog']! "
                f"(Found {len(dialog_editors)} Monaco editor instances in dialog)"
            )

        print(f"  Target Monaco SQL input editor verified inside [role='dialog'] ({len(dialog_editors)} editors present).")
        target_editor.click()
        time.sleep(0.5)

        # Write SQL to clipboard and paste via Control+V
        page.evaluate("(text) => navigator.clipboard.writeText(text)", sql_content)
        page.keyboard.press("Control+V")
        time.sleep(2)

        ss_step3 = screenshot_dir / "step3_sql_pasted.png"
        page.screenshot(path=str(ss_step3))
        print(f"  [SCREENSHOT] SQL pasted into Monaco editor: {ss_step3}")

        # Step 5: Execute Import
        import_btn = dialog.locator('button:has-text("Import")').first
        if not import_btn.is_visible() or import_btn.is_disabled():
            failed_checks += 1
            raise RuntimeError("Import button inside [role='dialog'] is disabled or missing after pasting SQL content!")

        print("\n[STEP 5/6] Executing Import into ChartDB canvas...")
        import_btn.click()
        time.sleep(5)

        # Rename imported diagram to official Bank Raya title
        page.evaluate("""async (newName) => {
            return new Promise((resolve) => {
                const req = indexedDB.open("ChartDB");
                req.onsuccess = (e) => {
                    const db = e.target.result;
                    const tx = db.transaction(["diagrams", "config"], "readwrite");
                    const diagStore = tx.objectStore("diagrams");
                    const confStore = tx.objectStore("config");

                    diagStore.getAll().onsuccess = (ev) => {
                        const diags = ev.target.result || [];
                        if (diags.length > 0) {
                            const latest = diags[diags.length - 1];
                            latest.name = newName;
                            diagStore.put(latest);
                            confStore.put({ id: 1, defaultDiagramId: latest.id });
                        }
                    };
                    tx.oncomplete = () => resolve(true);
                };
            });
        }""", DEFAULT_DIAGRAM_NAME)

        # Unhide any hidden schemas via official sidebar controls
        print("  Unhiding any hidden schemas via official sidebar controls...")
        unhide_attempts = 0
        while unhide_attempts < 15:
            btn = page.locator('button:has(svg.lucide-eye-off):visible')
            if btn.count() == 0:
                break
            btn.first.click()
            unhide_attempts += 1
            time.sleep(0.3)
        time.sleep(1)

        # Execute Auto Arrange & Fit View via official canvas toolbar buttons
        print("  Executing official Auto Arrange & Fit View on canvas...")
        layout_btn = page.locator('button:has(svg.lucide-layout-grid)')
        if layout_btn.count() > 0:
            layout_btn.click()
            time.sleep(0.8)
            confirm_btn = page.locator('button:has-text("Auto Arrange"), button:has-text("Continue"), button:has-text("Confirm")').last
            if confirm_btn.count() > 0 and confirm_btn.is_visible():
                confirm_btn.click()
                time.sleep(2)

        fit_btn = page.locator('button:has(svg.lucide-scan)')
        if fit_btn.count() > 0:
            fit_btn.click()
            time.sleep(1)

        # Step 6: DOM & Canvas Node Verification from Real DOM
        print("\n[STEP 6/6] Verifying Canvas DOM Nodes & Coordinates from Real DOM...")
        node_locator = page.locator(".react-flow__node")
        nodes_count = node_locator.count()
        print(f"  DOM Selector '.react-flow__node': found {nodes_count} nodes on canvas (Dynamic Expected: {exp_tables_count})")

        node_positions = []
        duplicate_positions = []
        for i in range(nodes_count):
            node_el = node_locator.nth(i)
            box = node_el.bounding_box()
            header = node_el.inner_text().strip().splitlines()[0] if node_el.inner_text() else f"node_{i}"
            tag_name = node_el.evaluate("el => el.tagName")
            style_str = node_el.get_attribute("style") or ""
            if box:
                pos_tuple = (round(box["x"], 1), round(box["y"], 1))
                if pos_tuple in [p[0] for p in node_positions]:
                    duplicate_positions.append((header, pos_tuple))
                node_positions.append((pos_tuple, header))
                print(f"    Node [{i}]: <{tag_name}> '{header}' at position x={pos_tuple[0]}, y={pos_tuple[1]} (style='{style_str[:55]}...')")

        # Edge DOM verification
        edge_locator = page.locator(".react-flow__edge")
        edges_count = edge_locator.count()
        print(f"  DOM Selector '.react-flow__edge': found {edges_count} edges on canvas (Dynamic Expected: {exp_fks_count})")

        # Check node count match
        if nodes_count == exp_tables_count:
            passed_checks += 1
            print(f"  [PASS] Canvas node count matches dynamically expected table count ({nodes_count}/{exp_tables_count}).")
        else:
            failed_checks += 1
            print(f"  [FAIL] Canvas node count mismatch: {nodes_count} found, expected {exp_tables_count}.")

        # Check edge count match
        if edges_count == exp_fks_count:
            passed_checks += 1
            print(f"  [PASS] Canvas edge count matches dynamically expected relationship count ({edges_count}/{exp_fks_count}).")
        else:
            failed_checks += 1
            print(f"  [FAIL] Canvas edge count mismatch: {edges_count} found, expected {exp_fks_count}.")

        # Check duplicate positions
        if duplicate_positions:
            print(f"  [FAIL] Duplicate positions detected on canvas: {duplicate_positions}")
            failed_checks += 1
        else:
            print(f"  [PASS] No duplicate node positions on canvas ({len(node_positions)} unique coordinates).")
            passed_checks += 1

        ss_canvas = screenshot_dir / "step4_final_canvas.png"
        page.screenshot(path=str(ss_canvas))
        print(f"  [SCREENSHOT] Canvas view saved to: {ss_canvas}")

        # Query IndexedDB
        db_verification = page.evaluate("""async () => {
            return new Promise((resolve) => {
                const req = indexedDB.open("ChartDB");
                req.onsuccess = (e) => {
                    const db = e.target.result;
                    const tx = db.transaction(["diagrams", "db_tables", "db_relationships"], "readonly");
                    const tablesReq = tx.objectStore("db_tables").getAll();
                    const relsReq = tx.objectStore("db_relationships").getAll();
                    const diagReq = tx.objectStore("diagrams").getAll();
                    tx.oncomplete = () => {
                        resolve({
                            diagrams: diagReq.result.map(d => ({ id: d.id, name: d.name })),
                            tablesCount: tablesReq.result.length,
                            relationshipsCount: relsReq.result.length,
                            tables: tablesReq.result.map(t => ({
                                schema: t.schema,
                                name: t.name,
                                fieldsCount: (t.fields || []).length
                            })),
                            relationships: relsReq.result.map(r => r.name)
                        });
                    };
                };
            });
        }""")

        # Close context to test persistence
        context.close()

    # Step 7: Persistence Verification across fresh context reopen
    print("\n[PERSISTENCE VERIFICATION] Re-opening persistent profile to verify on-disk storage...")
    with sync_playwright() as p:
        context_reopen = p.chromium.launch_persistent_context(
            str(user_data_dir),
            headless=headless if not keep_open else False,
            viewport={"width": 1440, "height": 900}
        )
        page_reopen = context_reopen.pages[0] if context_reopen.pages else context_reopen.new_page()
        page_reopen.goto(chartdb_url, wait_until="networkidle")
        time.sleep(2)

        persistence_check = page_reopen.evaluate("""async () => {
            return new Promise((resolve) => {
                const req = indexedDB.open("ChartDB");
                req.onsuccess = (e) => {
                    const db = e.target.result;
                    const tx = db.transaction(["diagrams", "db_tables", "db_relationships"], "readonly");
                    const tablesReq = tx.objectStore("db_tables").getAll();
                    const relsReq = tx.objectStore("db_relationships").getAll();
                    const diagReq = tx.objectStore("diagrams").getAll();
                    tx.oncomplete = () => {
                        resolve({
                            diagrams: diagReq.result.map(d => ({ id: d.id, name: d.name })),
                            tablesCount: tablesReq.result.length,
                            relationshipsCount: relsReq.result.length,
                            tables: tablesReq.result.map(t => ({
                                schema: t.schema,
                                name: t.name,
                                fieldsCount: (t.fields || []).length
                            })),
                            relationships: relsReq.result.map(r => r.name)
                        });
                    };
                };
            });
        }""")

        ss_reopen = screenshot_dir / "step5_reopened_canvas.png"
        page_reopen.screenshot(path=str(ss_reopen))
        print(f"  [SCREENSHOT] Reopened profile canvas saved to: {ss_reopen}")

        print(f"  Persistence Check Result from Disk Profile:")
        print(f"    Diagrams count:      {len(persistence_check['diagrams'])} ({persistence_check['diagrams']})")
        print(f"    Tables count:        {persistence_check['tablesCount']}")
        print(f"    Relationships count: {persistence_check['relationshipsCount']}")

        # Validate counts against dynamic expectations
        if persistence_check['tablesCount'] == exp_tables_count:
            passed_checks += 1
            print(f"  [PASS] Persistent tables count matches dynamic expectations ({persistence_check['tablesCount']}/{exp_tables_count}).")
        else:
            failed_checks += 1
            print(f"  [FAIL] Expected {exp_tables_count} tables, found {persistence_check['tablesCount']}")

        if persistence_check['relationshipsCount'] == exp_fks_count:
            passed_checks += 1
            print(f"  [PASS] Persistent relationships count matches dynamic expectations ({persistence_check['relationshipsCount']}/{exp_fks_count}).")
        else:
            failed_checks += 1
            print(f"  [FAIL] Expected {exp_fks_count} relationships, found {persistence_check['relationshipsCount']}")

        if len(persistence_check['diagrams']) == 1:
            passed_checks += 1
            print(f"  [PASS] Exactly 1 persistent diagram exists in IndexedDB (ID: {persistence_check['diagrams'][0]['id']}).")
        else:
            failed_checks += 1
            print(f"  [FAIL] Expected 1 diagram, found {len(persistence_check['diagrams'])}")

        if keep_open:
            print("\n[INFO] Flag --keep-open enabled. Browser window will remain open for your inspection.")
            print("  Press Ctrl+C in this terminal when you are done viewing.")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nClosing browser...")
        else:
            context_reopen.close()

    db_verification["passed_checks"] = passed_checks
    db_verification["failed_checks"] = failed_checks
    db_verification["expected_tables"] = exp_tables_count
    db_verification["expected_relationships"] = exp_fks_count
    return db_verification

def main():
    parser = argparse.ArgumentParser(description="Bank Raya - ChartDB Playwright UI Synchronizer")
    parser.add_argument("--url", default="http://127.0.0.1:8080", help="ChartDB Base URL")
    parser.add_argument("--sql", default=None, help="Path to chartdb_unified_import.sql")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode (default: headed)")
    parser.add_argument("--user-data-dir", default=None, help="Path to persistent browser profile directory")
    parser.add_argument("--screenshot-dir", default=None, help="Path to save execution screenshots")
    parser.add_argument("--keep-open", action="store_true", help="Keep browser open after sync for visual inspection")
    args = parser.parse_args()

    sql_path = Path(args.sql) if args.sql else None
    user_data_dir = Path(args.user_data_dir) if args.user_data_dir else None
    screenshot_dir = Path(args.screenshot_dir) if args.screenshot_dir else None

    result = run_sync(
        chartdb_url=args.url,
        sql_path=sql_path,
        headless=args.headless,
        user_data_dir=user_data_dir,
        screenshot_dir=screenshot_dir,
        keep_open=args.keep_open
    )

    p_count = result["passed_checks"]
    f_count = result["failed_checks"]
    total_columns = sum(t["fieldsCount"] for t in result["tables"])

    print("\n" + "=" * 80)
    print("CHARTDB PLAYWRIGHT UI IMPORT AUDIT SUMMARY")
    print("=" * 80)
    print(f"Diagram ID & Name:    {result['diagrams']}")
    print(f"Total db_tables:      {result['tablesCount']} (Dinamis dari SQL: {result['expected_tables']})")
    for t in sorted(result['tables'], key=lambda x: f"{x['schema']}.{x['name']}"):
        print(f"  - Table: {t['schema']}.{t['name']} ({t['fieldsCount']} columns)")
    print(f"Total Columns:        {total_columns} columns across {result['tablesCount']} tables")
    print(f"Total db_relationships: {result['relationshipsCount']} (Dinamis dari SQL: {result['expected_relationships']})")
    for r in sorted(result['relationships']):
        print(f"  - Relationship: {r}")
    print("=" * 80)
    print(f"HASIL AKHIR: {p_count} lulus, {f_count} gagal")
    print("=" * 80)

    if f_count > 0 or result['tablesCount'] != result['expected_tables'] or result['relationshipsCount'] != result['expected_relationships']:
        print("[ERROR] Verification checks failed or counts mismatched!")
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
