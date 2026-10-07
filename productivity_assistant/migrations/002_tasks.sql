CREATE TABLE projects (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE CHECK (length(name) BETWEEN 1 AND 100),
    private INTEGER NOT NULL DEFAULT 0 CHECK (private IN (0, 1)),
    created_at TEXT NOT NULL
);

CREATE TABLE tasks (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL CHECK (length(title) BETWEEN 1 AND 200),
    notes TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'done')),
    due_date TEXT CHECK (due_date IS NULL OR date(due_date) = due_date),
    importance INTEGER NOT NULL DEFAULT 2 CHECK (importance BETWEEN 1 AND 3),
    effort_minutes INTEGER CHECK (effort_minutes IS NULL OR effort_minutes > 0),
    project_id INTEGER REFERENCES projects (id),
    source TEXT NOT NULL DEFAULT 'manual',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT,
    deleted_at TEXT
);
CREATE INDEX tasks_open ON tasks (status, due_date) WHERE deleted_at IS NULL;

-- task_id cannot start until blocked_by_id is done.
CREATE TABLE task_dependencies (
    task_id INTEGER NOT NULL REFERENCES tasks (id),
    blocked_by_id INTEGER NOT NULL REFERENCES tasks (id),
    PRIMARY KEY (task_id, blocked_by_id),
    CHECK (task_id <> blocked_by_id)
);
CREATE INDEX task_dependencies_blocker ON task_dependencies (blocked_by_id);

CREATE TABLE task_history (
    id INTEGER PRIMARY KEY,
    task_id INTEGER NOT NULL REFERENCES tasks (id),
    at TEXT NOT NULL,
    actor TEXT NOT NULL CHECK (actor IN ('you', 'import', 'ai_accepted', 'system')),
    action TEXT NOT NULL,
    changes TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX task_history_task ON task_history (task_id, id);
