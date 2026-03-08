# Queries

## Common Cypher Snippets

### List all functions

```cypher
MATCH (f:Function)
RETURN f.project AS project, f.name AS function, f.file_uid AS file
ORDER BY project, function
LIMIT 100
```

### Function fan-in / fan-out (intra-project calls)

Uses `CALLS_FUNCTION` edges which represent resolved function-to-function calls
within the same project. `CALLS` edges point to unresolved `Symbol` nodes and
are not suitable for coupling metrics.

```cypher
MATCH (f:Function)
OPTIONAL MATCH (f)<-[:CALLS_FUNCTION]-(inbound:Function)
OPTIONAL MATCH (f)-[:CALLS_FUNCTION]->(outbound:Function)
RETURN f.project AS project,
       f.name AS function,
       count(DISTINCT inbound) AS fan_in,
       count(DISTINCT outbound) AS fan_out
ORDER BY (count(DISTINCT inbound) + count(DISTINCT outbound)) DESC
LIMIT 50
```

### Most-called functions (highest fan-in)

```cypher
MATCH (caller:Function)-[:CALLS_FUNCTION]->(callee:Function)
RETURN callee.project AS project, callee.name AS name, count(caller) AS fan_in
ORDER BY fan_in DESC
LIMIT 20
```

### Duplicate function signatures

```cypher
MATCH (f:Function)
WITH f.signature_hash AS sig, collect(f.name) AS names, count(*) AS copies
WHERE copies > 1
RETURN sig, copies, names
ORDER BY copies DESC
```

### Transitive callers of a function

```cypher
MATCH (target:Function {name: $symbol})
MATCH p = (caller:Function)-[:CALLS_FUNCTION*1..4]->(target)
WITH caller, min(length(p)) AS hops
RETURN caller.project, caller.name, caller.file_uid, hops
ORDER BY hops, caller.name
LIMIT 100
```

### Files importing a module

```cypher
MATCH (f:File)-[:IMPORTS]->(m:Module {name: $module})
RETURN f.project AS project, f.rel_path AS file
ORDER BY project, file
```

### Cross-project shared symbols

Find symbol names called by functions in both project A and project B:

```cypher
MATCH (f:Function {project: $project_a})-[:CALLS]->(s:Symbol)
      <-[:CALLS]-(g:Function {project: $project_b})
RETURN DISTINCT s.name AS shared_symbol
ORDER BY shared_symbol
LIMIT 50
```

### Node counts by label

```cypher
MATCH (n)
RETURN labels(n)[0] AS label, count(n) AS count
ORDER BY count DESC
```

### Edge counts by type

```cypher
MATCH ()-[r]->()
RETURN type(r) AS rel, count(r) AS count
ORDER BY count DESC
```

## Using the Query Command

Run inline Cypher:

```bash
codegraphx query "MATCH (f:Function) RETURN f.name LIMIT 10"
```

Add `--safe` to enable the write-guard for ad-hoc sessions:

```bash
codegraphx query "MATCH (f:Function) RETURN f.name LIMIT 10" --safe
```

Run from a `.cypher` file:

```bash
codegraphx query path/to/query.cypher
```
