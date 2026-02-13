MATCH (c:Class)-[:INHERITS]->(base:Class)
WITH base.name AS base_name, c.project AS proj, collect(c.name) AS impls
WHERE size(impls) > 1
RETURN base_name, proj, impls, size(impls) AS n
ORDER BY n DESC;
