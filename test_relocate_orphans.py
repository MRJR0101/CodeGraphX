import sys
import tempfile
import unittest
from pathlib import Path

# Insert the code directory to the path to import our script under test.
# Resolved from this file's location so the test is portable across checkouts.
CODE_DIR = Path(__file__).resolve().parent
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

import relocate_orphans  # noqa: E402


class TestTriStateOrphanRelocator(unittest.TestCase):
    def setUp(self):
        # Create a temporary sandboxed environment
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

        self.source_dir = self.root / "_SYSTEM_CACHE"
        self.toolbelt_dir = self.root / "projects" / "00_pytoolbelt"
        self.kb_dir = self.root / "KnowledgeBase"
        self.archive_dir = self.root / "Archives"

        self.source_dir.mkdir(parents=True)
        self.toolbelt_dir.mkdir(parents=True)
        self.kb_dir.mkdir(parents=True)
        self.archive_dir.mkdir(parents=True)

        # ---------------------------------------------------------
        # Scenario 1: External Hallucinated Routing (Should Reject)
        # ---------------------------------------------------------
        self.ghost_src = self.source_dir / "ghost.py"
        self.ghost_src.write_text("ghost content")
        self.ghost_dest_dir = self.kb_dir / "external_pkg"

        # ---------------------------------------------------------
        # Scenario 2: Perfect Existent Duplicate (Should Purge)
        # ---------------------------------------------------------
        self.dupe_src = self.source_dir / "dupe.py"
        self.dupe_dest_dir = self.toolbelt_dir / "module_a"
        self.dupe_dest_dir.mkdir(parents=True)
        self.dupe_dest = self.dupe_dest_dir / "dupe.py"
        self.dupe_src.write_text("x = 100")
        self.dupe_dest.write_text("x = 100")  # Exact identical match

        # ---------------------------------------------------------
        # Scenario 3: Different Content Collisions (Should Recover)
        # ---------------------------------------------------------
        self.diff_src = self.source_dir / "diff.py"
        self.diff_dest_dir = self.toolbelt_dir / "module_b"
        self.diff_dest_dir.mkdir(parents=True)
        self.diff_dest = self.diff_dest_dir / "diff.py"
        self.diff_src.write_text("y = 200 # version B")
        self.diff_dest.write_text("y = 100 # version A")  # Collision but differs

        # ---------------------------------------------------------
        # Scenario 4: Clean Relocation (Should Relocate)
        # ---------------------------------------------------------
        self.safe_src = self.source_dir / "safe.py"
        self.safe_dest_dir = self.toolbelt_dir / "module_c"
        self.safe_src.write_text("z = 300")

        # Create a Mock `orphan_relocations.txt` report
        self.mock_report = self.root / "mock_report.txt"

        def _entry(name: str, home: Path, score: int) -> str:
            return (
                f"File: {name}\n"
                f"  Current Location: {self.source_dir}\n"
                f"  [!] RECOMMENDED HOME:   {home} (Strong match: {score})\n"
            )

        with open(self.mock_report, "w", encoding="utf-8") as f:
            f.write(_entry("ghost.py", self.ghost_dest_dir, 99))
            f.write(_entry("dupe.py", self.dupe_dest_dir, 80))
            f.write(_entry("diff.py", self.diff_dest_dir, 50))
            f.write(_entry("safe.py", self.safe_dest_dir, 70))

        # Mock all global config state for testing
        relocate_orphans.DRY_RUN = False
        relocate_orphans.REPORT_PATH = str(self.mock_report)
        relocate_orphans.OUTPUT_REPORT = str(self.root / "report.txt")
        relocate_orphans.ARCHIVE_DUPLICATES_DIR = str(self.archive_dir)
        # Point the strict routing filter to our mocked project sandbox instead of C:\
        relocate_orphans.VALID_ROOT_FILTER = str(self.toolbelt_dir)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_tri_state_execution(self):
        # Fire the execution logic into the mock sandboxed realm
        relocate_orphans.main()

        # ASSERTS

        # 1. External ghost should be REJECTED. It should still exist in source cache.
        self.assertTrue(self.ghost_src.exists(), "Ghost source should not have been moved!")
        self.assertFalse((self.ghost_dest_dir / "ghost.py").exists(), "Ghost should NOT have hopped boundary!")

        # 2. Perfect Duplicate should be PURGED to the Archive directory.
        self.assertFalse(self.dupe_src.exists(), "FDUPE source should have been moved away.")
        self.assertTrue((self.archive_dir / "dupe.py").exists(), "FDUPE should be explicitly trapped in archive.")
        self.assertTrue(self.dupe_dest.exists(), "Original target dupe file should remain pristine.")

        # 3. Differing Collision should be RETAINED and RENAMED to `_recovered_1.py`.
        self.assertFalse(self.diff_src.exists(), "Diff source should have been moved.")
        self.assertTrue(self.diff_dest.exists(), "Original file should still be there.")
        self.assertTrue(
            (self.diff_dest_dir / "diff_recovered_1.py").exists(),
            "Differing code should map cleanly as a recovered copy side-by-side.",
        )

        # 4. Clean Safe Relocation should magically shift.
        self.assertFalse(self.safe_src.exists(), "Safe file should leave its source.")
        self.assertTrue((self.safe_dest_dir / "safe.py").exists(), "Clean file perfectly relocated to its home.")


if __name__ == "__main__":
    unittest.main()
