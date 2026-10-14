CREATE TABLE lyric_files (
  sha256 TEXT PRIMARY KEY CHECK (length(sha256) = 64),
  byte_length INTEGER NOT NULL CHECK (byte_length >= 0),
  created_at TEXT NOT NULL
);

CREATE TABLE lyric_uploads (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  asset_id TEXT NOT NULL,
  file_sha256 TEXT NOT NULL REFERENCES lyric_files(sha256),
  source_kind TEXT NOT NULL CHECK (source_kind IN ('txt', 'md', 'srt')),
  original_name TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (project_id, asset_id) REFERENCES project_assets(project_id, asset_id)
);

CREATE TABLE lyric_documents (
  id TEXT PRIMARY KEY,
  upload_id TEXT NOT NULL REFERENCES lyric_uploads(id),
  project_id TEXT NOT NULL,
  asset_id TEXT NOT NULL,
  revision INTEGER NOT NULL CHECK (revision >= 1),
  is_current INTEGER NOT NULL CHECK (is_current IN (0, 1)),
  created_at TEXT NOT NULL,
  FOREIGN KEY (project_id, asset_id) REFERENCES project_assets(project_id, asset_id)
);

CREATE UNIQUE INDEX lyric_documents_one_current
  ON lyric_documents(project_id, asset_id) WHERE is_current = 1;

CREATE TABLE lyric_segments (
  id TEXT PRIMARY KEY,
  document_id TEXT NOT NULL REFERENCES lyric_documents(id) ON DELETE CASCADE,
  ordinal INTEGER NOT NULL,
  source_cue TEXT,
  text TEXT NOT NULL,
  start_s REAL,
  end_s REAL,
  timing_origin TEXT NOT NULL CHECK (
    timing_origin IN ('unplaced', 'subtitle_supplied', 'manual_edit', 'manual_verified')
  ),
  artist_verified INTEGER NOT NULL CHECK (artist_verified IN (0, 1)),
  note TEXT NOT NULL DEFAULT '',
  UNIQUE (document_id, ordinal),
  CHECK ((start_s IS NULL) = (end_s IS NULL)),
  CHECK (artist_verified = 0 OR timing_origin = 'manual_verified'),
  CHECK (timing_origin != 'manual_verified' OR artist_verified = 1),
  CHECK (
    timing_origin NOT IN ('manual_edit', 'manual_verified')
    OR (start_s IS NOT NULL AND end_s > start_s)
  )
);

CREATE TABLE lyric_segment_revisions (
  id INTEGER PRIMARY KEY,
  segment_id TEXT NOT NULL REFERENCES lyric_segments(id) ON DELETE CASCADE,
  document_revision INTEGER NOT NULL,
  text TEXT NOT NULL,
  start_s REAL,
  end_s REAL,
  timing_origin TEXT NOT NULL,
  artist_verified INTEGER NOT NULL,
  note TEXT NOT NULL,
  UNIQUE (segment_id, document_revision)
);

CREATE TABLE lyric_validation (
  id INTEGER PRIMARY KEY,
  document_id TEXT NOT NULL REFERENCES lyric_documents(id) ON DELETE CASCADE,
  segment_id TEXT REFERENCES lyric_segments(id) ON DELETE CASCADE,
  code TEXT NOT NULL CHECK (
    code IN (
      'overlap', 'out_of_range', 'empty_cue',
      'reversed_time', 'malformed_time', 'unparsed'
    )
  ),
  detail TEXT NOT NULL
);

CREATE TABLE annotations (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  asset_id TEXT NOT NULL,
  segment_id TEXT REFERENCES lyric_segments(id) ON DELETE SET NULL,
  start_s REAL NOT NULL,
  end_s REAL NOT NULL,
  text TEXT NOT NULL CHECK (length(text) > 0),
  created_at TEXT NOT NULL,
  CHECK (end_s > start_s),
  FOREIGN KEY (project_id, asset_id) REFERENCES project_assets(project_id, asset_id)
);
