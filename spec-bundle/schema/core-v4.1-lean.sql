PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;

CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN (
        'created','preflight','ready','running','paused','stopping','finalizing','completed','failed','killed'
    )),
    stage TEXT CHECK (stage IN ('S0','S1','S2','S3','S4','S5')),
    config_json TEXT NOT NULL,
    started_at TEXT,
    deadline_at TEXT,
    finished_at TEXT,
    cost_cap_usd REAL NOT NULL CHECK (cost_cap_usd >= 0),
    cost_used_usd REAL NOT NULL DEFAULT 0 CHECK (cost_used_usd >= 0),
    gpu_hour_cap REAL,
    gpu_hours_used REAL NOT NULL DEFAULT 0 CHECK (gpu_hours_used >= 0),
    scientific_grade TEXT CHECK (scientific_grade IN ('A','B','C','D')),
    delivery_status TEXT,
    last_error TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    stage TEXT NOT NULL CHECK (stage IN ('S0','S1','S2','S3','S4','S5')),
    role TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN (
        'queued','running','completed','failed','interrupted','cancelled','blocked'
    )),
    attempt INTEGER NOT NULL DEFAULT 0 CHECK (attempt >= 0),
    max_attempts INTEGER NOT NULL DEFAULT 1 CHECK (max_attempts >= 1),
    dependencies_json TEXT NOT NULL DEFAULT '[]',
    input_json TEXT NOT NULL DEFAULT '{}',
    result_json TEXT,
    workspace_relpath TEXT,
    branch_name TEXT,
    source_commit TEXT,
    process_id INTEGER,
    external_job_id TEXT,
    estimated_cost_usd REAL NOT NULL DEFAULT 0 CHECK (estimated_cost_usd >= 0),
    estimated_gpu_hours REAL NOT NULL DEFAULT 0 CHECK (estimated_gpu_hours >= 0),
    started_at TEXT,
    finished_at TEXT,
    error_code TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tasks_run_status ON tasks(run_id, status);
CREATE INDEX IF NOT EXISTS idx_tasks_stage ON tasks(run_id, stage);

CREATE TABLE IF NOT EXISTS experiments (
    experiment_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    task_id TEXT REFERENCES tasks(task_id) ON DELETE SET NULL,
    candidate_id TEXT,
    purpose TEXT NOT NULL CHECK (purpose IN (
        'baseline','search','ablation','counterfactual','reproduction','confirmation'
    )),
    status TEXT NOT NULL CHECK (status IN (
        'created','running','completed','valid','reproduced','confirmed','claim_eligible',
        'invalid_run','mechanical_failure','optimization_failure','valid_null_result','cancelled'
    )),
    data_split TEXT NOT NULL CHECK (data_split IN ('train','search_dev','hidden_confirmation','none')),
    source_commit TEXT,
    config_hash TEXT,
    aggregate_json TEXT NOT NULL DEFAULT '{}',
    guards_json TEXT NOT NULL DEFAULT '{}',
    seeds_json TEXT NOT NULL DEFAULT '[]',
    manifest_relpath TEXT,
    created_at TEXT NOT NULL,
    finished_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_experiments_run_candidate ON experiments(run_id, candidate_id);

CREATE TABLE IF NOT EXISTS metrics (
    metric_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    experiment_id TEXT NOT NULL REFERENCES experiments(experiment_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    split TEXT NOT NULL,
    seed INTEGER,
    value REAL,
    value_json TEXT,
    is_primary INTEGER NOT NULL DEFAULT 0 CHECK (is_primary IN (0,1)),
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_metrics_experiment ON metrics(experiment_id, name);

CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    task_id TEXT REFERENCES tasks(task_id) ON DELETE SET NULL,
    experiment_id TEXT REFERENCES experiments(experiment_id) ON DELETE SET NULL,
    kind TEXT NOT NULL,
    relpath TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
    source_commit TEXT,
    retained INTEGER NOT NULL DEFAULT 1 CHECK (retained IN (0,1)),
    created_at TEXT NOT NULL,
    UNIQUE(run_id, relpath)
);

CREATE INDEX IF NOT EXISTS idx_artifacts_experiment ON artifacts(experiment_id, kind);

CREATE TABLE IF NOT EXISTS decisions (
    decision_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    stage TEXT,
    kind TEXT NOT NULL,
    choice TEXT NOT NULL,
    rationale TEXT NOT NULL,
    evidence_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS model_calls (
    call_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    task_id TEXT REFERENCES tasks(task_id) ON DELETE SET NULL,
    role TEXT NOT NULL,
    model TEXT NOT NULL,
    effort TEXT,
    input_tokens INTEGER,
    output_tokens INTEGER,
    estimated_cost_usd REAL NOT NULL DEFAULT 0 CHECK (estimated_cost_usd >= 0),
    stop_reason TEXT,
    status TEXT NOT NULL CHECK (status IN ('completed','refusal','rate_limited','failed')),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reviews (
    review_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    round INTEGER NOT NULL CHECK (round IN (1,2)),
    reviewer TEXT NOT NULL CHECK (reviewer IN ('R1','R2','R3')),
    model TEXT NOT NULL,
    effort TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('completed','failed','refusal')),
    findings_json TEXT NOT NULL DEFAULT '[]',
    verdict TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(run_id, round, reviewer)
);

CREATE TABLE IF NOT EXISTS events (
    event_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    task_id TEXT REFERENCES tasks(task_id) ON DELETE SET NULL,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_run_seq ON events(run_id, event_seq);
