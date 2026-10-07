ALTER TABLE tasks ADD COLUMN snoozed_until TEXT
    CHECK (snoozed_until IS NULL OR date(snoozed_until) = snoozed_until);

-- At most one active override per task; replaced or cleared by you.
CREATE TABLE priority_overrides (
    task_id INTEGER PRIMARY KEY REFERENCES tasks (id),
    kind TEXT NOT NULL CHECK (kind IN ('pin', 'raise', 'lower')),
    created_at TEXT NOT NULL
);

-- Every override or snooze, with the task's rank and score at that moment.
-- Kept so later milestones can propose weight changes; never applied automatically.
CREATE TABLE priority_feedback (
    id INTEGER PRIMARY KEY,
    task_id INTEGER NOT NULL REFERENCES tasks (id),
    kind TEXT NOT NULL CHECK (kind IN ('pin', 'raise', 'lower', 'clear', 'snooze')),
    at TEXT NOT NULL,
    rank_before INTEGER,
    score_before REAL,
    project_id INTEGER,
    importance INTEGER NOT NULL
);
