import csv
import os
import shutil
import sys

# Inject Industrial Hash Scanner module path
sys.path.insert(0, r"C:\Dev\PROJECTS\IndustrialHashScanner")
from industrial_hash_scanner import compute_hash  # noqa: E402

# ---------- SETTINGS ----------
DRY_RUN = True
VALID_ROOT_FILTER = r"c:\dev\projects\00_pytoolbelt"
# ------------------------------

REPORT_PATH = r"C:\Dev\PROJECTS\00_PyToolbelt\__CodeBase\CodeTracer\_analysis_reports\orphan_relocations.txt"
OUTPUT_REPORT = r"C:\Dev\PROJECTS\00_PyToolbelt\__CodeBase\CodeGraphX\dry_run_relocation_report.csv"
ARCHIVE_DUPLICATES_DIR = r"C:\Dev\Archives\Purged_Exact_Duplicates_20260410"


def parse_report():
    files = []
    with open(REPORT_PATH, encoding="utf-8", errors="ignore") as f:
        current_file = None
        current_loc = None

        for line in f:
            if line.startswith("File: "):
                current_file = line.strip().split("File: ")[1]
            elif line.startswith("  Current Location: "):
                current_loc = line.strip().split("Current Location: ")[1].strip()
            elif line.startswith("  [!] RECOMMENDED HOME:"):
                parts = line.split("RECOMMENDED HOME:")
                if len(parts) > 1:
                    raw_home = parts[1].split("(")[0].strip()
                    if current_file and current_loc:
                        src_path = os.path.join(current_loc, current_file)
                        dest_path = os.path.join(raw_home, current_file)
                        files.append((src_path, dest_path, raw_home))
                # Reset for next block
                current_file = None
                current_loc = None
    return files


def main():
    print(f"Reading relocation map from: {REPORT_PATH}")
    moves = parse_report()

    # Filter only for source files that physically exist
    active_moves = [(src, dest, home) for src, dest, home in moves if os.path.exists(src)]
    print(f"Found {len(moves)} total mapped orphans. {len(active_moves)} physically exist to be relocated.\n")

    if DRY_RUN:
        print("*** DRY RUN MODE ENABLED. NO FILES WILL BE MOVED. ***")
        print(f"Generating full relocation/dedup report to: {OUTPUT_REPORT}\n")
    else:
        os.makedirs(ARCHIVE_DUPLICATES_DIR, exist_ok=True)

    relocated = 0
    purged_dupes = 0
    skipped_bad_routing = 0
    total = len(active_moves)

    with open(OUTPUT_REPORT, "w", encoding="utf-8", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(["Action", "Source Path", "Destination Path", "Notes"])

        for idx, (src, dest, home_dir) in enumerate(active_moves, 1):
            # STRICT ROUTING POLICY: Target destination must safely reside inside the specified boundary
            if not home_dir.lower().startswith(VALID_ROOT_FILTER.lower()):
                writer.writerow(["REJECTED", src, dest, "Home is outside filter boundary. Skipping."])
                skipped_bad_routing += 1
                continue

            # EXACT DUPLICATE CHECK USING INDUSTRIAL HASHER
            is_exact_duplicate = False
            if os.path.exists(dest):
                try:
                    # Massively speeds up checks by gating massive IO reads behind quick file metadata sizes!
                    if os.path.getsize(src) == os.path.getsize(dest) and compute_hash(src) == compute_hash(dest):
                        is_exact_duplicate = True
                except Exception as e:
                    writer.writerow(["ERROR", src, dest, f"Hash check failed: {e}"])

            if not DRY_RUN:
                try:
                    if is_exact_duplicate:
                        dupe_dest = os.path.join(ARCHIVE_DUPLICATES_DIR, os.path.basename(src))
                        counter = 1
                        base, ext = os.path.splitext(dupe_dest)
                        while os.path.exists(dupe_dest):
                            dupe_dest = f"{base}_dupe_{counter}{ext}"
                            counter += 1

                        shutil.move(src, dupe_dest)
                        purged_dupes += 1
                        writer.writerow(["PURGED", src, dest, "Exact identical hash match on target."])
                    else:
                        os.makedirs(home_dir, exist_ok=True)
                        counter = 1
                        base, ext = os.path.splitext(dest)
                        while os.path.exists(dest):
                            dest = f"{base}_recovered_{counter}{ext}"
                            counter += 1

                        shutil.move(src, dest)
                        relocated += 1
                        writer.writerow(["RELOCATED", src, dest, "Successfully routed with differing checksum."])
                except Exception as e:
                    writer.writerow(["FAILED", src, dest, str(e)])
            else:
                if is_exact_duplicate:
                    purged_dupes += 1
                    writer.writerow(["DRY_RUN_PURGE", src, dest, "Exact Industrial Hash match verified. (Will purge)"])
                else:
                    relocated += 1
                    writer.writerow(
                        [
                            "DRY_RUN_RELOCATE",
                            src,
                            dest,
                            "Checksum uniquely valid for relocation. (Ready to move)",
                        ]
                    )

            # Print brief progress to console for large files so it's not silent
            if idx % 100 == 0:
                print(f"Processed {idx}/{total} mappings...")

    print("\n========================================")
    if DRY_RUN:
        print("DRY RUN TEST COMPLETE")
        print(f"Full CSV routing map generated: {OUTPUT_REPORT}")
        print(f"{relocated} files approved for structural relocation.")
        print(f"{purged_dupes} files identified as exact hash duplicates.")
        print(f"{skipped_bad_routing} dangerous recommendations suppressed.")
    else:
        print("ORPHAN RESOLUTION COMPLETE")
        print(f"Successfully returned {relocated} isolated files to their parent projects.")
        print(f"Safely archived {purged_dupes} exactly matching hash-verified files.")
    print("========================================")


if __name__ == "__main__":
    main()
