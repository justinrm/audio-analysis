CREATE TABLE projects_v5 (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  mode TEXT NOT NULL CHECK (mode IN ('study', 'album')),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

INSERT INTO projects_v5 (id, name, mode, created_at, updated_at)
SELECT id, name, mode, created_at, updated_at FROM projects;

DROP TABLE projects;
ALTER TABLE projects_v5 RENAME TO projects;

CREATE TABLE album_reviews (
  project_id TEXT NOT NULL REFERENCES projects(id),
  asset_id TEXT NOT NULL DEFAULT '',
  checkpoint_id TEXT NOT NULL,
  status TEXT NOT NULL CHECK (
    status IN ('unchecked', 'confirmed_issue', 'intentional', 'not_audible')
  ),
  note TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL,
  PRIMARY KEY (project_id, asset_id, checkpoint_id)
);

CREATE TABLE album_export_runs (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id),
  comparison_version TEXT NOT NULL,
  report_version TEXT NOT NULL,
  content_sha256 TEXT NOT NULL CHECK (length(content_sha256) = 64),
  created_at TEXT NOT NULL
);
