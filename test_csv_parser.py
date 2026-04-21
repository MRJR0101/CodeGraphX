"""Unit tests for ``parse_txt_to_csv.parse_txt_content``.

Imports the production parser directly so the test cannot silently diverge
from the real implementation (previously the test shipped its own copy of
the function, which defeated the point of testing).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

# Make the repo root importable no matter where pytest is launched from.
CODE_DIR = Path(__file__).resolve().parent
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from parse_txt_to_csv import parse_txt_content  # noqa: E402


class TestTxtToCsvParser(unittest.TestCase):
    """Test suite for the parsing logic of the dry run report."""

    def test_parses_all_tristate_conditions(self) -> None:
        """Validates that the parser processes REJECTED, PURGE, and RELOCATE actions."""
        mock_report = r"""========================================
 ORPHAN RELOCATION DRY-RUN REPORT
========================================

[1/3] EVALUATING: c:\dev\source1.py
        └─ TARGET: c:\dev\KnowledgeBase\ghost.py
        └─ [REJECTED]: Recommended home is outside the filter boundary. Skipping.

[2/3] EVALUATING: c:\dev\source2.py
        └─ TARGET: c:\dev\projects\00_pytoolbelt\exact.py
        └─ [DRY RUN PURGE: Exact content duplicate verified. Will archive orphan.]

[3/3] EVALUATING: c:\dev\source3.py
        └─ TARGET: c:\dev\projects\00_pytoolbelt\safe.py
        └─ [DRY RUN RELOCATE: Path validated for safe relocation.]
"""
        entries = parse_txt_content(mock_report)

        self.assertEqual(len(entries), 3)

        # Ghost rejection
        self.assertEqual(entries[0][0], "REJECTED")
        self.assertEqual(entries[0][1], r"c:\dev\source1.py")
        self.assertEqual(entries[0][2], r"c:\dev\KnowledgeBase\ghost.py")

        # Duplicate purge
        self.assertEqual(entries[1][0], "PURGE (Duplicate)")
        self.assertEqual(entries[1][1], r"c:\dev\source2.py")
        self.assertEqual(entries[1][2], r"c:\dev\projects\00_pytoolbelt\exact.py")

        # Safe relocate
        self.assertEqual(entries[2][0], "RELOCATE")
        self.assertEqual(entries[2][1], r"c:\dev\source3.py")
        self.assertEqual(entries[2][2], r"c:\dev\projects\00_pytoolbelt\safe.py")

    def test_ignores_blocks_that_are_too_short(self) -> None:
        """Regression: a block whose body collapses below the 2-line minimum is dropped."""
        partial = "EVALUATING: c:\\dev\\only_header.py\n"
        self.assertEqual(parse_txt_content(partial), [])


if __name__ == "__main__":
    unittest.main()
