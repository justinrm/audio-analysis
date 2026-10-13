CREATE TABLE assets_v2 (
  id TEXT PRIMARY KEY,
  sha256 TEXT NOT NULL UNIQUE,
  original_name TEXT NOT NULL,
  byte_length INTEGER NOT NULL,
  duration_s REAL NOT NULL,
  sample_rate INTEGER NOT NULL,
  channels INTEGER NOT NULL,
  subtype TEXT NOT NULL CHECK (subtype IN ('pcm_16', 'pcm_24')),
  analysis_status TEXT NOT NULL CHECK (
    analysis_status IN ('not_run', 'queued', 'running', 'completed', 'failed')
  ),
  playback_status TEXT NOT NULL CHECK (playback_status IN ('ready', 'unavailable')),
  created_at TEXT NOT NULL
);

INSERT INTO assets_v2 (
  id, sha256, original_name, byte_length, duration_s, sample_rate, channels,
  subtype, analysis_status, playback_status, created_at
)
SELECT
  id, sha256, original_name, byte_length, duration_s, sample_rate, channels,
  subtype, analysis_status, playback_status, created_at
FROM assets;

DROP TABLE assets;
ALTER TABLE assets_v2 RENAME TO assets;

CREATE TABLE analysis_runs (
  id TEXT PRIMARY KEY,
  asset_id TEXT NOT NULL REFERENCES assets(id),
  algorithm_version TEXT NOT NULL,
  params_hash TEXT NOT NULL,
  status TEXT NOT NULL CHECK (
    status IN ('queued', 'running', 'completed', 'failed', 'canceled')
  ),
  started_at TEXT,
  finished_at TEXT,
  error TEXT,
  metrics_path TEXT,
  evidence_path TEXT,
  UNIQUE (asset_id, algorithm_version, params_hash)
);
