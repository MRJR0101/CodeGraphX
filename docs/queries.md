# Queries

## Common Cypher Snippets

### List functions

```cypher
MATCH (f:Function)
RETURN f.project AS project, f.name AS function, f.file_uid AS file
ORDER BY function
LIMIT 100
```

### Highest fan-in/out

```cypher
MATCH (f:Function)
OPTIONAL MATCH (f)<-[:CALLS]-(inbound)
OPTIONAL MATCH (f)-[:CALLS]->(outbound)
RETURN f.name AS function,
       count(DISTINCT inbound) AS fan_in,
       count(DISTINCT outbound) AS fan_out
ORDER BY (fan_in + fan_out) DESC
LIMIT 50
```

### Duplicate signatures

```cypher
MATCH (f:Function)
WITH f.signature_hash AS signature_hash, collect(f.name) AS names, count(*) AS copies
WHERE copies > 1
RETURN signature_hash, copies, names
ORDER BY copies DESC
```

### Transitive callers

```cypher
MATCH (target:Function {name:$symbol})
MATCH p=(caller:Function)-[:CALLS_FUNCTION*1..4]->(target)
WITH caller, min(length(p)) AS hops
RETURN caller.project, caller.name, caller.file_uid, hops
ORDER BY hops, caller.name
LIMIT 100
```

## Using Query Command

```bash
codegraphx query "MATCH (f:Function) RETURN f.name LIMIT 10" --safe
```

Or from file:

```bash
codegraphx query docs/cypher/list_functions.cypher
```
