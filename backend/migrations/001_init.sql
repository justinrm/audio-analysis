CREATE TABLE projects (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  mode TEXT NOT NULL CHECK (mode IN ('study')),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE assets (
  id TEXT PRIMARY KEY,
  sha256 TEXT NOT NULL UNIQUE,
  original_name TEXT NOT NULL,
  byte_length INTEGER NOT NULL,
  duration_s REAL NOT NULL,
  sample_rate INTEGER NOT NULL,
  channels INTEGER NOT NULL,
  subtype TEXT NOT NULL CHECK (subtype IN ('pcm_16', 'pcm_24')),
  analysis_status TEXT NOT NULL CHECK (analysis_status IN ('not_run')),
  playback_status TEXT NOT NULL CHECK (playback_status IN ('ready', 'unavailable')),
  created_at TEXT NOT NULL
);

CREATE TABLE project_assets (
  project_id TEXT NOT NULL REFERENCES projects(id),
  asset_id TEXT NOT NULL REFERENCES assets(id),
  ordering INTEGER NOT NULL,
  PRIMARY KEY (project_id, asset_id)
);

CREATE TABLE jobs (
  id TEXT PRIMARY KEY,
  asset_id TEXT NOT NULL REFERENCES assets(id),
  status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'completed', 'failed', 'canceled')),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  error TEXT
);
