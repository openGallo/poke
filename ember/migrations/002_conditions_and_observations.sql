-- Non-destructive: stored JSON, IDs, photos and purchase records are retained.
-- Certificate numbers are unique within a grading company, not across companies.
UPDATE copies SET cert = 'PSA:' || cert WHERE cert IS NOT NULL AND instr(cert, ':') = 0;
CREATE TABLE IF NOT EXISTS listing_history(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 listing_id TEXT NOT NULL REFERENCES listings(id),
 fingerprint TEXT NOT NULL,
 observed_at TEXT NOT NULL,
 data TEXT NOT NULL,
 UNIQUE(listing_id, fingerprint, observed_at)
);
CREATE INDEX IF NOT EXISTS listing_history_item_time ON listing_history(listing_id, observed_at);
CREATE TABLE IF NOT EXISTS aggregates(
 id TEXT PRIMARY KEY,
 variant_id TEXT NOT NULL REFERENCES variants(id),
 data TEXT NOT NULL
);
