CREATE TABLE export_runs (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  asset_id TEXT NOT NULL,
  profile TEXT NOT NULL CHECK (profile IN ('technical', 'lyricist', 'combined')),
  lyrics_mode TEXT NOT NULL CHECK (lyrics_mode IN ('summarized', 'included', 'omitted')),
  lyric_revision INTEGER,
  source_sha256 TEXT NOT NULL CHECK (length(source_sha256) = 64),
  algorithm_version TEXT,
  params_hash TEXT,
  content_sha256 TEXT NOT NULL CHECK (length(content_sha256) = 64),
  created_at TEXT NOT NULL,
  FOREIGN KEY (project_id, asset_id) REFERENCES project_assets(project_id, asset_id)
);
