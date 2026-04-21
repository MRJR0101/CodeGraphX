import os
import shutil
import sys
from pathlib import Path
from typing import Any

# ---------- SAFE MODE SETTINGS ----------
DRY_RUN = True
TEST_BATCH_SIZE = 15  # Only test the first few files to verify logic
# ----------------------------------------

# Import the packaged CodeGraphX runtime directly so we can use a
# parameterized, file-aware query instead of scraping CLI table output.
REPO_ROOT = Path(__file__).resolve().parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from codegraphx.core.config import load_settings  # noqa: E402
from codegraphx.graph.neo4j_client import run_query  # noqa: E402

# Paths Based on Your Environment
REPORT_PATH = r"C:\Dev\PROJECTS\00_PyToolbelt\__CodeBase\CodeTracer\_analysis_reports\orphan_relocations.txt"
SETTINGS_PATH = str(REPO_ROOT / "config" / "default.yaml")
ARCHIVE_DIR = r"C:\Dev\Archives\Quarantine_Orphans_NoImpact_20260409"

_FILE_IMPACT_QUERY = """
MATCH (f:File)
WHERE toLower(f.path) = toLower($path)
OPTIONAL MATCH (f)-[:DEFINES]->(fn:Function)
WITH f,
     [node IN collect(DISTINCT fn) WHERE node IS NOT NULL] AS functions,
     [name IN collect(DISTINCT fn.name) WHERE name IS NOT NULL] AS function_names
OPTIONAL MATCH (caller_fn:Function)-[:CALLS_FUNCTION]->(target_fn:Function)
WHERE target_fn IN functions
WITH f, functions, function_names, count(DISTINCT caller_fn) AS function_callers
OPTIONAL MATCH (caller_symbol:Function)-[:CALLS]->(sym:Symbol)
WHERE sym.name IN function_names
WITH f, functions, function_names, function_callers, count(DISTINCT caller_symbol) AS symbol_callers
OPTIONAL MATCH (caller_file:File)-[:CALLS]->(sym2:Symbol)
WHERE sym2.name IN function_names
RETURN 1 AS matching_files,
       size(functions) AS definitions,
       function_callers,
       symbol_callers,
       count(DISTINCT caller_file) AS file_callers
"""


def parse_report():
    files = []
    with open(REPORT_PATH, encoding="utf-8", errors="ignore") as f:
        current_file = None
        for line in f:
            if line.startswith("File: "):
                current_file = line.strip().split("File: ")[1]
            elif line.startswith("  Current Location: "):
                location = line.strip().split("Current Location: ")[1].strip()
                if current_file:
                    full_path = os.path.join(location, current_file)
                    files.append(full_path)
                    current_file = None
    return files


def _query_file_impact(file_path: str) -> dict[str, Any] | None:
    settings = load_settings(SETTINGS_PATH)
    result = run_query(
        settings,
        _FILE_IMPACT_QUERY,
        params={"path": file_path},
        readonly=True,
    )
    if not result.rows:
        return None
    return result.rows[0]


def check_impact(file_path):
    # Only archive files we can positively prove are isolated.
    try:
        impact = _query_file_impact(file_path)
        if impact is None:
            print("[File not found in graph]", end=" ")
            return False

        definitions = int(impact.get("definitions", 0) or 0)
        function_callers = int(impact.get("function_callers", 0) or 0)
        symbol_callers = int(impact.get("symbol_callers", 0) or 0)
        file_callers = int(impact.get("file_callers", 0) or 0)

        print(
            f"[defs: {definitions}, fn: {function_callers}, sym: {symbol_callers}, file: {file_callers}]",
            end=" ",
        )

        return function_callers == 0 and symbol_callers == 0 and file_callers == 0
    except Exception as e:
        print(f"[-] Error querying graph for {file_path}: {e}", end=" ")
        return False


def main():
    print(f"Reading orphan report from: {REPORT_PATH}")
    files = parse_report()

    # Filter for files that physically still exist before spinning up subprocesses
    active_files = [f for f in files if os.path.exists(f)]
    print(f"Found {len(files)} orphans total. {len(active_files)} physically exist to check.")

    os.makedirs(ARCHIVE_DIR, exist_ok=True)

    if DRY_RUN:
        print("\n*** DRY RUN MODE ENABLED. NO FILES WILL BE MOVED. ***")
        active_files = active_files[:TEST_BATCH_SIZE]
        print(f"Testing the first {TEST_BATCH_SIZE} files...\n")
    else:
        print(f"\nSafe archiving destination: {ARCHIVE_DIR}\n")

    purged = 0
    total = len(active_files)

    print("Initiating CodeGraphX safety verifications...")
    for idx, fp in enumerate(active_files, 1):
        # STRICT SAFETY: Only evaluate files inside the PyToolbelt boundary
        if r"c:\dev\projects\00_pytoolbelt" not in fp.lower():
            print(f"[{idx}/{total}] SKIPPING (External Boundary): {fp}")
            continue

        print(f"[{idx}/{total}] Checking {fp}...", end=" ", flush=True)

        is_safe = check_impact(fp)
        if is_safe:
            print("SAFE. Archiving.")
            dest = os.path.join(ARCHIVE_DIR, os.path.basename(fp))

            # Avoid overwriting identically named orphans
            counter = 1
            base, ext = os.path.splitext(dest)
            while os.path.exists(dest):
                dest = f"{base}_{counter}{ext}"
                counter += 1

            if not DRY_RUN:
                try:
                    shutil.move(fp, dest)
                    purged += 1
                except Exception as e:
                    print(f"Move failed: {e}")
            else:
                print(f"   -> [DRY RUN] Would move to: {dest}")
                purged += 1
        else:
            print("DANGER (Active references or failed check). Skipping.")

    print("\n========================================")
    if DRY_RUN:
        print("DRY RUN TEST COMPLETE")
        print(f"{purged} out of {TEST_BATCH_SIZE} isolated files would have been moved.")
    else:
        print("ORPHAN PURGE COMPLETE")
        print(f"Successfully archived {purged} strictly isolated files.")
    print("========================================")


if __name__ == "__main__":
    main()
