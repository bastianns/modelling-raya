#!/usr/bin/env python3
"""
Bank Raya - ChartDB Canvas E2E Test Suite (Playwright)
Validates Canvas Rendering (9 tables, 5 edges), No Modal, Zero Console Errors,
and Shape Matching across 4 profiles:
  (a) Fresh Context / Empty Profile
  (b) Existing Database with Dummy Diagram Preserved
  (c) F5 Reload Persistence
  (d) Toxic Legacy DB Upgrade & Reconciliation
"""

import sys
import json
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright, expect

SCREENSHOT_DIR = Path("docs/screenshots")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

SCHEMA_PATH = Path("sources/bank_raya_unified_schema.json")
try:
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        _schema = json.load(f)
        EXP_NODES = len(_schema.get("tables", []))
        EXP_EDGES = len(_schema.get("relations", []))
except Exception:
    EXP_NODES = 10
    EXP_EDGES = 5

async def run_profile_a(browser):
    print("\n" + "=" * 60)
    print("RUNNING PROFILE (A): Empty Profile (Fresh Browser Context)")
    print("=" * 60)
    context = await browser.new_context()
    page = await context.new_page()

    console_errors = []
    page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
    page.on("pageerror", lambda exc: console_errors.append(str(exc)))

    # Navigate to autoload
    print("  -> Navigating to http://localhost:8080/autoload.html...")
    await page.goto("http://localhost:8080/autoload.html", wait_until="domcontentloaded")

    # Wait for redirect to /diagrams/bank_raya_main_diagram
    print("  -> Waiting for redirection to /diagrams/bank_raya_main_diagram...")
    await page.wait_for_url("**/diagrams/bank_raya_main_diagram", timeout=15000)
    print(f"  [PASS] Redirected to URL: {page.url}")

    # Assert nodes and edges render
    nodes_loc = page.locator(".react-flow__node")
    edges_loc = page.locator(".react-flow__edge")
    await expect(nodes_loc).to_have_count(EXP_NODES, timeout=15000)
    await expect(edges_loc).to_have_count(EXP_EDGES, timeout=15000)
    print(f"  [PASS] Detected exactly {EXP_NODES} nodes and {EXP_EDGES} edges on canvas.")

    # Assert 'What is your Database?' dialog is NOT visible
    db_dialog = await page.query_selector("text='What is your Database?'")
    assert db_dialog is None, "Modal 'What is your Database?' unexpectedly appeared!"
    print("  [PASS] 'What is your Database?' modal is NOT present.")

    # Check fatal console errors
    fatal_errors = [e for e in console_errors if "favicon" not in e and "HydrateFallback" not in e]
    print(f"  -> Fatal console errors: {len(fatal_errors)}")
    assert len(fatal_errors) == 0, f"Unexpected console errors: {fatal_errors}"
    print("  [PASS] Zero console errors on canvas.")

    screenshot_path = SCREENSHOT_DIR / "canvas_profile_a.png"
    await page.screenshot(path=str(screenshot_path))
    print(f"  [PASS] Screenshot saved to: {screenshot_path}")

    await context.close()
    return True

async def run_profile_b(browser):
    print("\n" + "=" * 60)
    print("RUNNING PROFILE (B): Existing DB with Dummy Diagram Preserved")
    print("=" * 60)
    context = await browser.new_context()
    page = await context.new_page()

    # Pre-populate IndexedDB with a dummy diagram
    await page.goto("http://localhost:8080/", wait_until="domcontentloaded")
    await page.wait_for_timeout(1000)
    await page.evaluate("""async () => {
        return new Promise((resolve) => {
            const req = indexedDB.open("ChartDB", 130);
            req.onsuccess = (e) => {
                const db = e.target.result;
                const tx = db.transaction(["diagrams", "db_tables"], "readwrite");
                tx.objectStore("diagrams").put({
                    id: "user_dummy_diagram_999",
                    name: "User Custom Diagram",
                    databaseType: "postgresql",
                    databaseEdition: null,
                    createdAt: new Date(),
                    updatedAt: new Date()
                });
                tx.objectStore("db_tables").put({
                    id: "tbl_dummy_table_1",
                    diagramId: "user_dummy_diagram_999",
                    name: "dummy_table",
                    schema: "public",
                    x: 100,
                    y: 100,
                    order: 0,
                    fields: [],
                    indexes: [],
                    color: "#ffffff",
                    comment: "",
                    isView: false,
                    isMaterializedView: false,
                    createdAt: Date.now()
                });
                tx.oncomplete = () => {
                    db.close();
                    resolve();
                };
            };
        });
    }""")
    print("  -> Pre-populated IndexedDB with dummy diagram 'user_dummy_diagram_999'.")

    # Navigate to autoload
    await page.goto("http://localhost:8080/autoload.html", wait_until="domcontentloaded")
    await page.wait_for_url("**/diagrams/bank_raya_main_diagram", timeout=15000)
    await expect(page.locator(".react-flow__node")).to_have_count(EXP_NODES, timeout=15000)
    await expect(page.locator(".react-flow__edge")).to_have_count(EXP_EDGES, timeout=15000)
    print(f"  [PASS] Bank Raya canvas rendered {EXP_NODES} nodes and {EXP_EDGES} edges.")

    # Verify dummy diagram was NOT deleted
    has_dummy = await page.evaluate("""async () => {
        return new Promise((resolve) => {
            const req = indexedDB.open("ChartDB", 130);
            req.onsuccess = (e) => {
                const db = e.target.result;
                const tx = db.transaction("diagrams", "readonly");
                const q = tx.objectStore("diagrams").get("user_dummy_diagram_999");
                q.onsuccess = () => {
                    const found = !!q.result;
                    db.close();
                    resolve(found);
                };
            };
        });
    }""")
    assert has_dummy, "User dummy diagram was unexpectedly deleted!"
    print("  [PASS] Dummy diagram 'user_dummy_diagram_999' was successfully PRESERVED.")

    screenshot_path = SCREENSHOT_DIR / "canvas_profile_b.png"
    await page.screenshot(path=str(screenshot_path))
    print(f"  [PASS] Screenshot saved to: {screenshot_path}")

    await context.close()
    return True

async def run_profile_c(browser):
    print("\n" + "=" * 60)
    print("RUNNING PROFILE (C): F5 Reload Persistence")
    print("=" * 60)
    context = await browser.new_context()
    page = await context.new_page()

    await page.goto("http://localhost:8080/autoload.html", wait_until="domcontentloaded")
    await page.wait_for_url("**/diagrams/bank_raya_main_diagram", timeout=15000)
    await expect(page.locator(".react-flow__node")).to_have_count(EXP_NODES, timeout=15000)

    print("  -> Pressing F5 / Reloading page directly at /diagrams/bank_raya_main_diagram...")
    await page.reload(wait_until="domcontentloaded")
    await expect(page.locator(".react-flow__node")).to_have_count(EXP_NODES, timeout=15000)
    await expect(page.locator(".react-flow__edge")).to_have_count(EXP_EDGES, timeout=15000)
    print(f"  [PASS] Nodes and edges retained after F5: exactly {EXP_NODES} nodes, {EXP_EDGES} edges.")

    screenshot_path = SCREENSHOT_DIR / "canvas_profile_c.png"
    await page.screenshot(path=str(screenshot_path))
    print(f"  [PASS] Screenshot saved to: {screenshot_path}")

    await context.close()
    return True

async def run_profile_d(browser):
    print("\n" + "=" * 60)
    print("RUNNING PROFILE (D): Toxic Legacy DB Upgrade & Reconciliation")
    print("=" * 60)
    context = await browser.new_context()
    page = await context.new_page()

    # Pre-create "toxic" database with old seeder structure
    await page.goto("http://localhost:8080/", wait_until="domcontentloaded")
    await page.wait_for_timeout(1000)
    await page.evaluate("""async () => {
        indexedDB.deleteDatabase("ChartDB");
    }""")
    await page.wait_for_timeout(1000)

    await page.evaluate("""async () => {
        return new Promise((resolve) => {
            const req = indexedDB.open("ChartDB", 120);
            req.onupgradeneeded = (e) => {
                const db = e.target.result;
                const st = db.createObjectStore("db_tables", { keyPath: "id" });
                st.createIndex("diagramId", "diagramId", { unique: false });
                const dg = db.createObjectStore("diagrams", { keyPath: "id" });
                const cf = db.createObjectStore("config", { keyPath: "id" });
            };
            req.onsuccess = (e) => {
                const db = e.target.result;
                const tx = db.transaction(["diagrams", "db_tables"], "readwrite");
                tx.objectStore("diagrams").put({ id: 1, name: "Old Numeric Diagram" });
                tx.objectStore("db_tables").put({ id: "old_tbl_1", diagramId: 1, name: "toxic_table" });
                tx.oncomplete = () => {
                    db.close();
                    resolve();
                };
            };
        });
    }""")
    print("  -> Created toxic old seeder database (v120, missing stores & 'order' index).")

    # Navigate to autoload.html
    print("  -> Navigating to http://localhost:8080/autoload.html...")
    await page.goto("http://localhost:8080/autoload.html", wait_until="domcontentloaded")
    await page.wait_for_timeout(1500)

    # Verify toxic warning message appears
    title_text = await page.inner_text("#title")
    print(f"  -> Title text: '{title_text}'")
    assert "Perlu Perbaikan Skema" in title_text

    # Button #repair-btn should be visible
    repair_btn = page.locator("#repair-btn")
    is_visible = await repair_btn.is_visible()
    assert is_visible, "Repair button #repair-btn must be visible for toxic database"
    print("  -> Repair button is visible. Clicking...")
    await repair_btn.click()

    # Wait for redirect
    await page.wait_for_url("**/diagrams/bank_raya_main_diagram", timeout=15000)
    print(f"  [PASS] Successfully redirected after repair: {page.url}")

    await expect(page.locator(".react-flow__node")).to_have_count(EXP_NODES, timeout=15000)
    await expect(page.locator(".react-flow__edge")).to_have_count(EXP_EDGES, timeout=15000)
    print(f"  [PASS] Nodes and edges verified after repair: {EXP_NODES} nodes, {EXP_EDGES} edges.")

    screenshot_path = SCREENSHOT_DIR / "canvas_profile_d.png"
    await page.screenshot(path=str(screenshot_path))
    print(f"  [PASS] Screenshot saved to: {screenshot_path}")

    await context.close()
    return True

async def run_shape_matching_test(browser):
    print("\n" + "=" * 60)
    print("RUNNING SHAPE MATCHING ASSERTION (Native Template vs Bank Raya Seeder)")
    print("=" * 60)
    context = await browser.new_context()
    page = await context.new_page()

    await page.goto("http://localhost:8080/autoload.html", wait_until="domcontentloaded")
    await page.wait_for_url("**/diagrams/bank_raya_main_diagram", timeout=15000)
    await page.wait_for_timeout(2000)

    shape_result = await page.evaluate("""async () => {
        return new Promise((resolve) => {
            const req = indexedDB.open("ChartDB", 130);
            req.onsuccess = async (e) => {
                const db = e.target.result;
                const tx = db.transaction(["diagrams", "db_tables", "db_relationships"], "readonly");
                const diag = await new Promise(r => {
                    const q = tx.objectStore("diagrams").get("bank_raya_main_diagram");
                    q.onsuccess = () => r(q.result);
                });
                const table = await new Promise(r => {
                    const q = tx.objectStore("db_tables").getAll();
                    q.onsuccess = () => r(q.result[0]);
                });
                const rel = await new Promise(r => {
                    const q = tx.objectStore("db_relationships").getAll();
                    q.onsuccess = () => r(q.result[0]);
                });
                db.close();

                const getType = (v) => Object.prototype.toString.call(v);

                resolve({
                    diag: {
                        keys: Object.keys(diag).sort(),
                        createdAtType: getType(diag.createdAt),
                        updatedAtType: getType(diag.updatedAt),
                        databaseEdition: diag.databaseEdition
                    },
                    table: {
                        keys: Object.keys(table).sort(),
                        orderType: getType(table.order),
                        createdAtType: getType(table.createdAt),
                        indexShape: table.indexes[0] ? Object.keys(table.indexes[0]).sort() : []
                    },
                    rel: {
                        keys: Object.keys(rel).sort(),
                        createdAtType: getType(rel.createdAt),
                        hasTypeProp: "type" in rel,
                        hasSourceCard: "sourceCardinality" in rel,
                        hasTargetCard: "targetCardinality" in rel
                    }
                });
            };
        });
    }""")

    print("Shape Result Inspection:")
    print(json.dumps(shape_result, indent=2))

    # Assert Diagram Shape
    assert shape_result["diag"]["createdAtType"] == "[object Date]", "Diagram createdAt must be Date object"
    assert shape_result["diag"]["updatedAtType"] == "[object Date]", "Diagram updatedAt must be Date object"
    assert shape_result["diag"]["databaseEdition"] is None, "Diagram databaseEdition must be null"

    # Assert Table Shape
    table_expected_keys = sorted(["color", "comment", "createdAt", "diagramId", "fields", "id", "indexes", "isMaterializedView", "isView", "name", "order", "schema", "x", "y"])
    assert shape_result["table"]["keys"] == table_expected_keys, f"Table keys mismatch: {shape_result['table']['keys']}"
    assert shape_result["table"]["orderType"] == "[object Number]", "Table order must be Number"
    assert shape_result["table"]["createdAtType"] == "[object Number]", "Table createdAt must be Number"

    # Assert Relationship Shape
    assert shape_result["rel"]["hasTypeProp"] is False, "Relationship must NOT have 'type' property"
    assert shape_result["rel"]["hasSourceCard"] is True, "Relationship must have 'sourceCardinality'"
    assert shape_result["rel"]["hasTargetCard"] is True, "Relationship must have 'targetCardinality'"
    assert shape_result["rel"]["createdAtType"] == "[object Number]", "Relationship createdAt must be Number"

    print("  [PASS] All Shape Matching assertions passed with 100% fidelity.")
    await context.close()
    return True

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            await run_profile_a(browser)
            await run_profile_b(browser)
            await run_profile_c(browser)
            await run_profile_d(browser)
            await run_shape_matching_test(browser)
            print("\n" + "=" * 60)
            print("ALL 4 PROFILES & SHAPE MATCHING TEST PASSED (100%)")
            print("=" * 60)
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
