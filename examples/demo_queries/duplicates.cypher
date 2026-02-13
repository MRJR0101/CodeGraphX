MATCH (fn:Function)
WITH fn.signature_hash AS h, collect(fn) AS funcs
WHERE h IS NOT NULL AND size(funcs) > 1
RETURN h, [f IN funcs | f.uid] AS function_ids, size(funcs) AS n
ORDER BY n DESC
LIMIT 50;
