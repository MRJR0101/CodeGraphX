# Schema

## Node Labels

- `Project`
- `File`
- `Function`
- `Symbol`

## Edge Types

- `CONTAINS` (`Project -> File`)
- `DEFINES` (`File -> Function`)
- `CALLS` (`Function/File -> Symbol`)
- `CALLS_FUNCTION` (`Function -> Function`)

## Event Identity

Used for incremental load and snapshot comparison.

### Node identity

`node:<label>:<uid>`

### Edge identity

`edge:<type>:<src_label>:<src_uid>:<dst_label>:<dst_uid>`

## UID Patterns

### File

`<project>:<rel_path>`

### Function

`<project>:<rel_path>:<function_name>:<line>`

## Hashing

- Event hash: SHA-1 of stable JSON payload.
- Row hash: SHA-1 of stable parse-row subset.
