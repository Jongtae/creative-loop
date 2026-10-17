from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from .models import now


class Store:
    """One connection per operation. WAL + busy timeout for a local single-user app."""
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        (root / "assets").mkdir(exist_ok=True)
        self.path = root / "creative-loop.sqlite3"
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS assets (
                  id TEXT PRIMARY KEY, digest TEXT NOT NULL, features TEXT NOT NULL,
                  rights TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS observations (
                  id TEXT PRIMARY KEY, platform TEXT NOT NULL, source_id TEXT NOT NULL,
                  observed_at TEXT NOT NULL, payload TEXT NOT NULL,
                  UNIQUE(platform, source_id, observed_at));
                CREATE TABLE IF NOT EXISTS batches (
                  id TEXT PRIMARY KEY, request TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS designs (
                  id TEXT PRIMARY KEY, batch_id TEXT NOT NULL REFERENCES batches(id),
                  payload TEXT NOT NULL, selected INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS preferences (
                  id TEXT PRIMARY KEY, winner_id TEXT NOT NULL REFERENCES designs(id),
                  loser_id TEXT NOT NULL REFERENCES designs(id), payload TEXT NOT NULL,
                  created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS revisions (
                  id INTEGER PRIMARY KEY AUTOINCREMENT, design_id TEXT NOT NULL REFERENCES designs(id),
                  revision INTEGER NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS provider_calls (
                  id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, model TEXT NOT NULL,
                  status TEXT NOT NULL, usage TEXT NOT NULL, created_at TEXT NOT NULL);
                PRAGMA user_version=1;
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def get_design(self, design_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM designs WHERE id=?", (design_id,)).fetchone()
        if not row:
            return None
        item = json.loads(row["payload"])
        item["selected"] = bool(row["selected"])
        return item

    def designs(self, batch_id=None):
        with self.connect() as db:
            if batch_id:
                rows = db.execute("SELECT id FROM designs WHERE batch_id=? ORDER BY rowid", (batch_id,)).fetchall()
            else:
                rows = db.execute("SELECT id FROM designs ORDER BY rowid DESC LIMIT 500").fetchall()
        return [self.get_design(row["id"]) for row in rows]

    def observations(self):
        with self.connect() as db:
            rows = db.execute("SELECT id,payload FROM observations ORDER BY observed_at DESC LIMIT 10000").fetchall()
        return [{"id": r["id"], **json.loads(r["payload"])} for r in rows]

    def preferences(self, category, batch_ids=None):
        with self.connect() as db:
            rows = db.execute("SELECT payload FROM preferences ORDER BY created_at").fetchall()
        return [p for r in rows if (p := json.loads(r["payload"]))["category"] == category]

    def get_asset(self, asset_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM assets WHERE id=?", (asset_id,)).fetchone()
        if not row:
            return None
        return {"id": row["id"], "features": json.loads(row["features"]), "rights": json.loads(row["rights"])}

    def log_call(self, kind, model, status, usage=None):
        with self.connect() as db:
            db.execute("INSERT INTO provider_calls(kind,model,status,usage,created_at) VALUES(?,?,?,?,?)",
                       (kind, model, status, json.dumps(usage or {}), now()))
