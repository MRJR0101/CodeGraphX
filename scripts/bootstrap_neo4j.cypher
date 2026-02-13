// Constraints / indexes for MVP
CREATE CONSTRAINT project_name IF NOT EXISTS FOR (p:Project) REQUIRE p.name IS UNIQUE;
CREATE CONSTRAINT file_id IF NOT EXISTS FOR (f:File) REQUIRE f.uid IS UNIQUE;
CREATE CONSTRAINT func_id IF NOT EXISTS FOR (fn:Function) REQUIRE fn.uid IS UNIQUE;
CREATE INDEX func_hash IF NOT EXISTS FOR (fn:Function) ON (fn.signature_hash);
