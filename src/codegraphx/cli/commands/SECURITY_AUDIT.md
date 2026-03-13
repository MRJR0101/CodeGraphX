# Security Audit -- CodeGraphX CLI Commands

**Audited:** 2026-03-10
**Auditor:** Claude (Anthropic) via Desktop Commander
**Scope:** `C:\Dev\PROJECTS\CodeGraphX\src\codegraphx\cli\commands\`
**Files reviewed:** analyze.py, ask.py, compare.py, delta.py, doctor.py,
                    enrich.py, extract.py, impact.py, load.py, parse.py,
                    query.py, scan.py, search.py, snapshots.py

---

## Severity Legend

- CRITICAL -- Exploitable without additional access; fix before next release
- HIGH     -- Exploitable under realistic conditions; fix this sprint
- MEDIUM   -- Defense-in-depth gap; fix in next planned cycle
- LOW      -- Hardening / future-proofing; address when touching the file

---

## CRITICAL

### C-01 -- query.py -- Write operations allowed by default

**Lines:** 38-40

The `--safe` flag that blocks write Cypher is opt-in. Without it, any caller
can run CREATE, MERGE, DELETE, DETACH DELETE, DROP, SET, REMOVE, or APOC
write procedures against the live Neo4j graph with no confirmation or guard.

```python
# Current -- safe defaults to False
if safe and _looks_write_query(query):
    raise typer.BadParameter("safe mode rejected write-like query")
```

**Fix:** Invert the default. Safe mode should be on by default; an explicit
`--allow-write` flag should be required to run mutating queries.

---

### C-02 -- query.py -- Write-guard regex is bypassable

**Lines:** 20-32  (`_looks_write_query`)

The regex anchors on `^`, `;\s*`, and `\n\s*`. Several bypass vectors exist:

- `/* comment */ CREATE (n:Node)` -- comment prefix before keyword
- `MATCH (n) /* hidden */ SET n.x=1` -- SET after inline block comment
- `MATCH (n)\r\nCREATE` -- CR-only line ending bypasses `\n` anchor
- `CALL apoc .` (with space) -- space between `apoc.` breaks the match
- Multi-statement strings with unusual whitespace between clauses

**Fix:** Tokenize or use a proper Cypher parser rather than regex. At minimum,
strip all block comments (`/* ... */`) and normalize all line endings to `\n`
before applying the pattern. Add `\r` to the alternation.

---

## HIGH

### H-01 -- analyze.py, impact.py -- f-string interpolation into Cypher

**analyze.py lines:** 23, 50, 106, 120, 137
**impact.py lines:** 22, 26, 31, 37

`limit` and `depth` integers are interpolated directly into Cypher strings
using f-strings. While Typer enforces `int` at the CLI boundary, any
programmatic caller bypasses this. Neo4j does not support parameterized LIMIT
or path length, but the values must still be range-validated before use.

```python
# Current -- no ceiling enforced
f"ORDER BY coupling DESC LIMIT {limit}"
f"MATCH p=(caller:Function)-[:CALLS_FUNCTION*1..{depth}]->(target)"
```

**Fix:** Add explicit range clamping before interpolation:

```python
limit = max(1, min(int(limit), 500))   # hard ceiling of 500
depth = max(1, min(int(depth), 10))    # already has max=10 in typer but enforce here too
```

---

### H-02 -- enrich.py -- No timeout on subprocess.run

**Lines:** 29  (`_run_script`)

```python
proc = subprocess.run(cmd, cwd=str(root), capture_output=True)
```

No `timeout=` argument. A hung enrichment script (network hang, deadlock,
infinite loop) will block the process indefinitely with no way to recover
short of killing the parent.

**Fix:**

```python
proc = subprocess.run(cmd, cwd=str(root), capture_output=True, timeout=600)
```

Wrap in `except subprocess.TimeoutExpired` and surface a clear error message.

---

### H-03 -- enrich.py -- User-controlled paths passed to subprocess without validation

**Lines:** backlog_cmd, chunk_scan_cmd, campaign_cmd, collectors_cmd, intelligence_cmd

`--db`, `--target-root`, `--source-path`, `--output`, `--scan`, and
`--update-db` are all passed verbatim as CLI arguments to child scripts via
`_run_script`. No path normalization, no prefix restriction, no traversal guard.

A value such as `--output ../../sensitive/creds.json` passes through
unchecked.

**Fix:** Resolve and validate all path arguments before forwarding:

```python
def _validate_path_arg(val: str, must_exist: bool = False) -> str:
    p = Path(val).resolve()
    if must_exist and not p.exists():
        raise typer.BadParameter(f"path does not exist: {p}")
    return str(p)
```

Apply to all path-type options before appending to `args`.

---

## MEDIUM

### M-01 -- analyze.py, delta.py, snapshots.py -- Output path traversal via --output

**analyze.py lines:** 155-158
**delta.py lines:** 121-128
**snapshots.py lines:** report_cmd, create_cmd

All `--output` flags write to caller-supplied paths with no validation.
`analyze.py` is the most dangerous case -- it calls `mkdir(parents=True)` on
the parent of the supplied path, which will silently create any directory tree:

```python
out_path = Path(output)
out_path.parent.mkdir(parents=True, exist_ok=True)   # creates arbitrary dirs
out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
```

**Fix:** Resolve the output path and optionally restrict it to the configured
`out_dir`. At minimum, remove the `parents=True` call and require the target
directory to already exist.

---

### M-02 -- doctor.py -- Exception detail leaks internal paths and config values

**Lines:** 52-53, 59-60

```python
except Exception as exc:  # noqa: BLE001
    checks.append({"check": "projects_loaded", "status": "fail", "detail": str(exc)})
```

`str(exc)` on a YAML parse error or Neo4j connection failure can expose full
file paths, connection strings, usernames, or passwords embedded in config
files. This output is printed directly to stdout.

**Fix:** Truncate or sanitize detail strings. Strip anything that looks like
a connection URI or file path before including in output. At minimum, limit
`detail` to the first 120 characters with a truncation marker.

---

### M-03 -- query.py -- Unrestricted .cypher file read

**Lines:** 12-16  (`_resolve_query`)

```python
if path.suffix.lower() == ".cypher" and path.exists() and path.is_file():
    return path.read_text(encoding="utf-8")
```

Any `.cypher` file anywhere on disk is readable and executed as a query. An
attacker with write access to any directory reachable from the CLI invocation
could place a malicious `.cypher` file and execute arbitrary graph mutations
(once C-01/C-02 are also resolved).

**Fix:** Restrict file reads to a known `queries/` directory relative to the
repo root:

```python
allowed_root = _repo_root() / "queries"
resolved = path.resolve()
if not str(resolved).startswith(str(allowed_root)):
    raise typer.BadParameter(f"query file must be inside {allowed_root}")
```

---

## LOW

### L-01 -- enrich.py -- Fragile _repo_root() via __file__ resolution

**Lines:** 13-14

```python
def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]
```

If the package is installed via a symlink, editable install in an unexpected
location, or the directory depth changes, `parents[4]` silently resolves to
the wrong directory. A wrong root means `scripts/enrichment_backlog.py` etc.
are not found -- or worse, a different file at that path is executed.

**Fix:** After resolving, verify the expected marker exists:

```python
root = Path(__file__).resolve().parents[4]
if not (root / "pyproject.toml").exists():
    raise RuntimeError(f"_repo_root() resolved to unexpected path: {root}")
return root
```

---

### L-02 -- ask.py -- Future LLM input path has no sanitization hook

**Lines:** 42-54

`--model` and `--model-name` are accepted but the docstring explicitly states
no LLM is called yet. When LLM integration is wired in, the raw `question`
string from the CLI will go to the model without any sanitization, length
limit, or prompt injection guard.

**Action:** Before wiring in LLM calls, add:
- Maximum input length (suggested: 2000 chars)
- Strip control characters
- Document the injection risk in the function docstring

---

### L-03 -- General -- No query size limit on raw Cypher or search inputs

**Affected:** query.py (cypher argument), search.py (query argument),
             ask.py (question argument)

No maximum length is enforced on any user-supplied string before it is passed
to the Neo4j driver or FTS engine. Very large inputs can cause memory pressure
in the driver or degrade FTS performance.

**Fix:** Add a simple length guard at the top of each command:

```python
if len(cypher) > 10_000:
    raise typer.BadParameter("query exceeds maximum allowed length (10000 chars)")
```

---

## Summary Table

| ID   | File(s)                              | Issue                                      | Severity |
|------|--------------------------------------|--------------------------------------------|----------|
| C-01 | query.py                             | Write ops allowed by default               | CRITICAL |
| C-02 | query.py                             | Write-guard regex bypassable               | CRITICAL |
| H-01 | analyze.py, impact.py                | f-string interpolation into Cypher         | HIGH     |
| H-02 | enrich.py                            | No subprocess timeout                      | HIGH     |
| H-03 | enrich.py                            | Unvalidated paths forwarded to subprocess  | HIGH     |
| M-01 | analyze.py, delta.py, snapshots.py   | Output path traversal via --output         | MEDIUM   |
| M-02 | doctor.py                            | Exception detail leaks internals           | MEDIUM   |
| M-03 | query.py                             | Unrestricted .cypher file read from disk   | MEDIUM   |
| L-01 | enrich.py                            | Fragile _repo_root() depth assumption      | LOW      |
| L-02 | ask.py                               | No sanitization hook for future LLM input  | LOW      |
| L-03 | query.py, search.py, ask.py          | No input length limit on query strings     | LOW      |

---

## Recommended Fix Order

1. C-01 -- Flip --safe default in query.py
2. C-02 -- Replace write-guard regex with comment-stripping + improved pattern
3. H-02 -- Add timeout=600 to subprocess.run in enrich.py
4. H-03 -- Add path validation helper to enrich.py
5. M-03 -- Restrict .cypher file reads to queries/ directory
6. H-01 -- Add range clamps before all f-string LIMIT/depth interpolations
7. M-01 -- Remove parents=True from analyze.py output mkdir; validate output paths
8. M-02 -- Truncate exception detail strings in doctor.py
9. L-01 -- Add pyproject.toml existence check in _repo_root()
10. L-02 -- Add length limit and sanitization stub in ask.py
11. L-03 -- Add length guards to query, search, ask commands

---

*End of audit. No files were modified. All findings are advisory.*
