# Useful Cypher Queries

## Find duplicate functions by signature hash
```cypher
MATCH (fn:Function)
WITH fn.signature_hash AS h, collect(fn) AS funcs
WHERE h IS NOT NULL AND size(funcs) > 1
RETURN h, [f IN funcs | f.uid] AS function_ids, size(funcs) AS n
ORDER BY n DESC
LIMIT 50;
```

## Find plugin-style class clusters
```cypher
MATCH (c:Class)-[:INHERITS]->(base:Class {name:"BasePlugin"})
RETURN c.project, count(c)
```

## Compare call trees between projects
```cypher
MATCH p1 = (f:Function {project:"MainScraper"})-[:CALLS*1..4]->()
MATCH p2 = (g:Function {project:"UltimateScraper"})-[:CALLS*1..4]->()
WHERE f.name = g.name
RETURN f, g
```
