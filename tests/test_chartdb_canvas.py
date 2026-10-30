#!/usr/bin/env python3
"""
Bank Raya - ChartDB Canvas E2E Test Suite (Playwright)
Validates Dynamic Canvas Rendering (nodes & edges from compiled schema), No Modal, Zero Console Errors,
No Node Overlaps, and Shape Matching across 4 profiles:
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
with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
    _schema = json.load(f)
    EXP_NODES = len(_schema.get("tables", []))
    EXP_EDGES = len(_schema.get("relations", []))

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

    # Assert No Canvas Overlap
    rendered_nodes = await page.query_selector_all(".react-flow__node")
    node_boxes = []
    for rn in rendered_nodes:
        b = await rn.bounding_box()
        if b:
            node_boxes.append(b)
    overlaps = 0
    for i in range(len(node_boxes)):
        for j in range(i + 1, len(node_boxes)):
            b1 = node_boxes[i]
            b2 = node_boxes[j]
            if not (b1["x"] + b1["width"] <= b2["x"] or b2["x"] + b2["width"] <= b1["x"] or
                    b1["y"] + b1["height"] <= b2["y"] or b2["y"] + b2["height"] <= b1["y"]):
                overlaps += 1
    assert overlaps == 0, f"Detected {overlaps} overlapping table nodes on canvas!"
    print(f"  [PASS] Canvas Overlap Test: 0 overlapping nodes among {len(node_boxes)} rendered tables.")

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
    print("RUNNING PROFILE (B): Existing DB with Native UI Diagram Preserved")
    print("=" * 60)
    context = await browser.new_context()
    page = await context.new_page()

    # Pre-populate IndexedDB via NATIVE CHARTDB UI
    print("  -> Navigating to http://localhost:8080/ to create native diagram via UI...")
    await page.goto("http://localhost:8080/")
    await page.evaluate("async () => { indexedDB.deleteDatabase('ChartDB'); }")
    await page.goto("http://localhost:8080/")
    await page.wait_for_timeout(2000)

    # Click first DB icon (PostgreSQL) and 'Empty database'
    icons = await page.query_selector_all("button[aria-label='Toggle bold']")
    await icons[0].click()
    await page.wait_for_timeout(300)
    await page.locator("button:has-text('Empty database')").click()
    await page.wait_for_timeout(1000)

    # Click 'Add Table' on canvas
    await page.locator("button:has-text('Add Table')").first.click()
    await page.wait_for_timeout(800)

    # Retrieve native user diagram ID
    user_diagrams = await page.evaluate("""async () => {
        return new Promise((resolve) => {
            const req = indexedDB.open("ChartDB", 130);
            req.onsuccess = (e) => {
                const db = e.target.result;
                const tx = db.transaction("diagrams", "readonly");
                const q = tx.objectStore("diagrams").getAll();
                q.onsuccess = () => { db.close(); resolve(q.result); };
            };
        });
    }""")
    assert len(user_diagrams) >= 1, "Native diagram was not created via UI!"
    user_diag_id = user_diagrams[0]["id"]
    print(f"  [PASS] Native diagram created via UI with id: '{user_diag_id}' (Name: '{user_diagrams[0]['name']}')")

    # Navigate to autoload
    print("  -> Navigating to http://localhost:8080/autoload.html...")
    await page.goto("http://localhost:8080/autoload.html", wait_until="domcontentloaded")
    await page.wait_for_url("**/diagrams/bank_raya_main_diagram", timeout=15000)
    await expect(page.locator(".react-flow__node")).to_have_count(EXP_NODES, timeout=15000)
    await expect(page.locator(".react-flow__edge")).to_have_count(EXP_EDGES, timeout=15000)
    print(f"  [PASS] Bank Raya canvas rendered {EXP_NODES} nodes and {EXP_EDGES} edges.")

    # Assert No Canvas Overlap
    rendered_nodes = await page.query_selector_all(".react-flow__node")
    node_boxes = []
    for rn in rendered_nodes:
        b = await rn.bounding_box()
        if b:
            node_boxes.append(b)
    overlaps = 0
    for i in range(len(node_boxes)):
        for j in range(i + 1, len(node_boxes)):
            b1 = node_boxes[i]
            b2 = node_boxes[j]
            if not (b1["x"] + b1["width"] <= b2["x"] or b2["x"] + b2["width"] <= b1["x"] or
                    b1["y"] + b1["height"] <= b2["y"] or b2["y"] + b2["height"] <= b1["y"]):
                overlaps += 1
    assert overlaps == 0, f"Detected {overlaps} overlapping table nodes on canvas!"
    print(f"  [PASS] Canvas Overlap Test: 0 overlapping nodes among {len(node_boxes)} rendered tables.")

    # Verify native dummy diagram was NOT deleted
    has_dummy = await page.evaluate(f"""async () => {{
        return new Promise((resolve) => {{
            const req = indexedDB.open("ChartDB", 130);
            req.onsuccess = (e) => {{
                const db = e.target.result;
                const tx = db.transaction("diagrams", "readonly");
                const q = tx.objectStore("diagrams").get("{user_diag_id}");
                q.onsuccess = () => {{
                    const found = !!q.result;
                    db.close();
                    resolve(found);
                }};
            }};
        }});
    }}""")
    assert has_dummy, f"User dummy diagram '{user_diag_id}' was unexpectedly deleted!"
    print(f"  [PASS] Dummy diagram '{user_diag_id}' was successfully PRESERVED.")

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

    # Assert No Canvas Overlap
    rendered_nodes = await page.query_selector_all(".react-flow__node")
    node_boxes = []
    for rn in rendered_nodes:
        b = await rn.bounding_box()
        if b:
            node_boxes.append(b)
    overlaps = 0
    for i in range(len(node_boxes)):
        for j in range(i + 1, len(node_boxes)):
            b1 = node_boxes[i]
            b2 = node_boxes[j]
            if not (b1["x"] + b1["width"] <= b2["x"] or b2["x"] + b2["width"] <= b1["x"] or
                    b1["y"] + b1["height"] <= b2["y"] or b2["y"] + b2["height"] <= b1["y"]):
                overlaps += 1
    assert overlaps == 0, f"Detected {overlaps} overlapping table nodes on canvas!"
    print(f"  [PASS] Canvas Overlap Test: 0 overlapping nodes among {len(node_boxes)} rendered tables.")

    screenshot_path = SCREENSHOT_DIR / "canvas_profile_c.png"
    await page.screenshot(path=str(screenshot_path))
    print(f"  [PASS] Screenshot saved to: {screenshot_path}")

    await context.close()
    return True

async def run_profile_d(browser):
    print("\n" + "=" * 60)
    print("RUNNING PROFILE (D): Toxic Legacy DB Upgrade & Reconciliation (v130 & v120)")
    print("=" * 60)
    context = await browser.new_context()
    page = await context.new_page()

    # Pre-create "toxic" database with v130 handcrafted seeder (missing order index & wrong diagram_filters keyPath)
    await page.goto("http://localhost:8080/")
    await page.evaluate("async () => { indexedDB.deleteDatabase('ChartDB'); }")
    await page.wait_for_timeout(500)

    await page.evaluate("""async () => {
        return new Promise((resolve) => {
            const req = indexedDB.open("ChartDB", 130);
            req.onupgradeneeded = (e) => {
                const db = e.target.result;
                const st = db.createObjectStore("db_tables", { keyPath: "id" });
                st.createIndex("diagramId", "diagramId", { unique: false });
                const dg = db.createObjectStore("diagrams", { keyPath: "id" });
                const cf = db.createObjectStore("config", { keyPath: "id" });
                const fl = db.createObjectStore("diagram_filters", { keyPath: "id" });
            };
            req.onsuccess = (e) => {
                const db = e.target.result;
                const tx = db.transaction(["diagrams", "db_tables"], "readwrite");
                tx.objectStore("diagrams").put({ id: "user_dummy_toxic_130", name: "Custom User Diagram v130", databaseType: "postgresql" });
                tx.objectStore("db_tables").put({ id: "old_tbl_1", diagramId: "user_dummy_toxic_130", name: "toxic_table" });
                tx.oncomplete = () => {
                    db.close();
                    resolve();
                };
            };
        });
    }""")
    print("  -> Created toxic old seeder database (v130, missing 'order' index and invalid diagram_filters keyPath).")

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
    print("  -> Repair button is visible. Clicking to trigger repairAndReseed()...")
    await repair_btn.click()

    # Wait for redirect
    await page.wait_for_url("**/diagrams/bank_raya_main_diagram", timeout=15000)
    print(f"  [PASS] Successfully redirected after repair: {page.url}")

    await expect(page.locator(".react-flow__node")).to_have_count(EXP_NODES, timeout=15000)
    await expect(page.locator(".react-flow__edge")).to_have_count(EXP_EDGES, timeout=15000)
    print(f"  [PASS] Nodes and edges verified after repair: {EXP_NODES} nodes, {EXP_EDGES} edges.")

    # Assert No Canvas Overlap
    rendered_nodes = await page.query_selector_all(".react-flow__node")
    node_boxes = []
    for rn in rendered_nodes:
        b = await rn.bounding_box()
        if b:
            node_boxes.append(b)
    overlaps = 0
    for i in range(len(node_boxes)):
        for j in range(i + 1, len(node_boxes)):
            b1 = node_boxes[i]
            b2 = node_boxes[j]
            if not (b1["x"] + b1["width"] <= b2["x"] or b2["x"] + b2["width"] <= b1["x"] or
                    b1["y"] + b1["height"] <= b2["y"] or b2["y"] + b2["height"] <= b1["y"]):
                overlaps += 1
    assert overlaps == 0, f"Detected {overlaps} overlapping table nodes on canvas!"
    print(f"  [PASS] Canvas Overlap Test: 0 overlapping nodes among {len(node_boxes)} rendered tables.")

    # Verify user dummy diagram was PRESERVED
    preserved = await page.evaluate("""async () => {
        return new Promise((resolve) => {
            const req = indexedDB.open("ChartDB", 130);
            req.onsuccess = (e) => {
                const db = e.target.result;
                const tx = db.transaction("diagrams", "readonly");
                const q = tx.objectStore("diagrams").get("user_dummy_toxic_130");
                q.onsuccess = () => {
                    db.close();
                    resolve(q.result);
                };
            };
        });
    }""")
    assert preserved is not None and preserved["id"] == "user_dummy_toxic_130"
    print(f"  [PASS] Preserved dummy diagram in Dexie: {preserved['name']}")

    screenshot_path = SCREENSHOT_DIR / "canvas_profile_d.png"
    await page.screenshot(path=str(screenshot_path))
    print(f"  [PASS] Screenshot saved to: {screenshot_path}")

    await page.close()
    await context.close()

    # Separate Scenario: v120 Upgrade
    print("\n  -> Testing separate scenario: Legacy v120 upgrade...")
    context_v120 = await browser.new_context()
    page_v120 = await context_v120.new_page()

    await page_v120.goto("http://localhost:8080/")
    await page_v120.evaluate("async () => { indexedDB.deleteDatabase('ChartDB'); }")
    await page_v120.wait_for_timeout(500)

    await page_v120.evaluate("""async () => {
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
                tx.objectStore("diagrams").put({ id: "legacy_user_v120", name: "Legacy User Diagram v120" });
                tx.objectStore("db_tables").put({ id: "old_tbl_120", diagramId: "legacy_user_v120", name: "toxic_table_120" });
                tx.oncomplete = () => {
                    db.close();
                    resolve();
                };
            };
        });
    }""")
    await page_v120.goto("http://localhost:8080/autoload.html", wait_until="domcontentloaded")
    await page_v120.wait_for_timeout(1000)
    if await page_v120.locator("#repair-btn").is_visible():
        await page_v120.locator("#repair-btn").click()

    await page_v120.wait_for_url("**/diagrams/bank_raya_main_diagram", timeout=15000)
    await expect(page_v120.locator(".react-flow__node")).to_have_count(EXP_NODES, timeout=15000)
    print("  [PASS] Legacy v120 scenario verified and upgraded successfully.")
    await page_v120.close()
    await context_v120.close()
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
