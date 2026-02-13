#!/usr/bin/env python3
# === RESTORATION CERTIFICATION ===
# Project: codegraphx
# Python: 3.13
# Restored: 2026-02-12 01:12
# Status: CERTIFIED 
# Report: restore_report.json
# Cert: smoke_report.json
# ==================================

"""
Pre-commit hook for CodeGraphX analysis.

Run this script as a pre-commit hook to analyze code before committing.

Usage:
    # Install as pre-commit hook
    echo "python scripts/pre-commit.py" > .git/hooks/pre-commit
    chmod +x .git/hooks/pre-commit

Or install via pre-commit framework:
    # .pre-commit-config.yaml
    - repo: local
      hooks:
        - id: codegraphx-analyze
          name: CodeGraphX Analysis
          entry: python scripts/pre-commit.py
          language: system
          stages: [push]
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path


# Configuration
CONFIG_FILE = "config/default.yaml"
PROJECTS_FILE = "config/projects.yaml"
AUDIT_LOG = ".codegraphx_audit.log"

# Severity levels
SEVERITY_HIGH = "HIGH"
SEVERITY_MEDIUM = "MEDIUM"
SEVERITY_LOW = "LOW"


def run_command(
    cmd: list[str],
    cwd: Path | None = None,
    timeout: int = 120,
) -> tuple[int, str, str]:
    """Run a command and return exit code, stdout, stderr."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except Exception as e:
        return -1, "", str(e)


def check_codegraphx_installed() -> bool:
    """Check if codegraphx is installed."""
    code, _, _ = run_command(["codegraphx", "--version"])
    return code == 0


def get_staged_files() -> list[str]:
    """Get list of staged Python files."""
    code, stdout, _ = run_command(
        ["git", "diff", "--cached", "--name-only", "--", ".py"]
    )
    if code != 0:
        return []
    return [f for f in stdout.strip().split("\n") if f]


def run_quick_scan(files: list[str]) -> dict:
    """Run quick analysis on staged files."""
    if not files:
        return {"issues": [], "metrics": {}}

    # Get project name from files
    project = Path(files[0]).parts[0] if files else "unknown"

    # Run security check on changed files
    issues = []

    # Check for common issues in staged files
    for file_path in files:
        try:
            content = Path(file_path).read_text(errors="ignore")
            lines = content.split("\n")

            for i, line in enumerate(lines, 1):
                # Check for potential issues
                if "eval(" in line and "user" in line.lower():
                    issues.append({
                        "file": file_path,
                        "line": i,
                        "severity": SEVERITY_HIGH,
                        "message": "Potential user input in eval()",
                        "code": line.strip()[:50],
                    })

                if "exec(" in line and "user" in line.lower():
                    issues.append({
                        "file": file_path,
                        "line": i,
                        "severity": SEVERITY_HIGH,
                        "message": "Potential user input in exec()",
                        "code": line.strip()[:50],
                    })

                if "SELECT" in line and "{" in line:
                    issues.append({
                        "file": file_path,
                        "line": i,
                        "severity": SEVERITY_MEDIUM,
                        "message": "Possible SQL injection risk",
                        "code": line.strip()[:50],
                    })

                if "password" in line.lower() and "=" in line:
                    issues.append({
                        "file": file_path,
                        "line": i,
                        "severity": SEVERITY_LOW,
                        "message": "Possible hardcoded password",
                        "code": line.strip()[:50],
                    })

        except Exception:
            pass  # Skip files we can't read

    # Get metrics
    metrics = {
        "files_changed": len(files),
        "lines_added": 0,
        "lines_deleted": 0,
    }

    # Get diff stats
    code, stdout, _ = run_command(
        ["git", "diff", "--numstat", "--", "*.py"]
    )
    if code == 0:
        for line in stdout.strip().split("\n"):
            if line:
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        metrics["lines_added"] += int(parts[0])
                        metrics["lines_deleted"] += int(parts[1])
                    except ValueError:
                        pass

    return {"issues": issues, "metrics": metrics}


def log_audit(event: str, details: dict):
    """Log audit event to file."""
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "event": event,
        "details": details,
    }

    audit_path = Path(AUDIT_LOG)
    with open(audit_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def print_issues(issues: list[dict]):
    """Print found issues in a formatted way."""
    if not issues:
        return

    # Group by severity
    by_severity = {"HIGH": [], "MEDIUM": [], "LOW": []}
    for issue in issues:
        severity = issue.get("severity", "LOW")
        by_severity[severity].append(issue)

    # Print high severity first
    for severity in [SEVERITY_HIGH, SEVERITY_MEDIUM, SEVERITY_LOW]:
        for issue in by_severity[severity]:
            label = "ERROR" if severity == SEVERITY_HIGH else "WARN" if severity == SEVERITY_MEDIUM else "INFO"
            print(f"{label} [{severity}] {issue['file']}:{issue['line']}")
            print(f"   {issue['message']}")
            print(f"   {issue['code']}")


def main():
    """Main pre-commit hook."""
    print("CodeGraphX Pre-commit Analysis")
    print("=" * 50)

    # Get staged files
    staged_files = get_staged_files()

    if not staged_files:
        print("OK: No Python files staged for commit")
        return 0

    print(f"Analyzing {len(staged_files)} staged Python file(s)...")

    # Run quick scan
    results = run_quick_scan(staged_files)
    issues = results.get("issues", [])
    metrics = results.get("metrics", {})

    # Log the analysis
    log_audit("pre_commit_scan", {
        "files": staged_files,
        "issues_found": len(issues),
        "metrics": metrics,
    })

    # Print metrics
    print("\nChange Summary:")
    print(f"   Files: {metrics.get('files_changed', 0)}")
    print(f"   Lines added: +{metrics.get('lines_added', 0)}")
    print(f"   Lines deleted: -{metrics.get('lines_deleted', 0)}")

    # Print issues
    if issues:
        print(f"\nWARNING: Found {len(issues)} potential issue(s):")
        print_issues(issues)

        # Count by severity
        high = sum(1 for i in issues if i.get("severity") == SEVERITY_HIGH)
        medium = sum(1 for i in issues if i.get("severity") == SEVERITY_MEDIUM)

        # Fail on high severity issues
        if high > 0:
            print(f"\nBLOCKED: {high} high-severity issue(s) found")
            print("   Fix these issues before committing")
            return 1

        # Warn on medium severity
        if medium > 0:
            print(f"\nWARNING: {medium} medium-severity issue(s) found")
            print("   Consider fixing these before committing")

        # Allow commit but warn
        print("\nCommit allowed with warnings")
        return 0

    print("\nOK: No issues found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
