-- Factual briefings and reviews with the facts they were built from.
CREATE TABLE briefings (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('morning', 'evening')),
    day TEXT NOT NULL CHECK (date(day) = day),
    generated_at TEXT NOT NULL,
    trigger TEXT NOT NULL CHECK (trigger IN ('schedule', 'catch_up', 'manual')),
    content TEXT NOT NULL
);
CREATE INDEX briefings_kind_day ON briefings (kind, day, id);
