-- AI gateway audit trail: one row per model call. No prompt or reply text is stored.
CREATE TABLE ai_calls (
    id INTEGER PRIMARY KEY,
    at TEXT NOT NULL,
    feature TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    digest TEXT NOT NULL,
    input_tokens INTEGER,
    output_tokens INTEGER,
    duration_ms INTEGER NOT NULL,
    outcome TEXT NOT NULL CHECK (outcome IN ('ok', 'invalid', 'timeout', 'unavailable', 'busy', 'refused')),
    accepted INTEGER CHECK (accepted IS NULL OR accepted = 1)
);
CREATE INDEX ai_calls_at ON ai_calls (at);
