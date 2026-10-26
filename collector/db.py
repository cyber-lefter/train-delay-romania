import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS stations (
    station_id TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    lat        REAL,
    lon        REAL
);

CREATE TABLE IF NOT EXISTS trains (
    train_no   TEXT PRIMARY KEY,
    category   TEXT,            -- R, R-E, IR, IC, ...
    operator   TEXT,
    route_name TEXT,
    service_id TEXT
);

CREATE TABLE IF NOT EXISTS service_dates (
    service_id TEXT NOT NULL,
    date       TEXT NOT NULL,   -- YYYY-MM-DD
    PRIMARY KEY (service_id, date)
);

-- Scheduled times are minutes after midnight of the service day (can exceed 1440).
CREATE TABLE IF NOT EXISTS scheduled_stops (
    train_no   TEXT NOT NULL,
    seq        INTEGER NOT NULL,
    station_id TEXT NOT NULL,
    arr_min    INTEGER,
    dep_min    INTEGER,
    PRIMARY KEY (train_no, seq)
);

-- One row per train run per station: the latest delay seen for that stop.
CREATE TABLE IF NOT EXISTS observations (
    service_date TEXT NOT NULL,
    train_no     TEXT NOT NULL,
    station_id   TEXT NOT NULL,
    arr_delay    INTEGER,       -- minutes, negative = early
    dep_delay    INTEGER,
    passed       INTEGER NOT NULL DEFAULT 0,  -- 1 once the train has left the stop
    source       TEXT NOT NULL,
    observed_at  TEXT NOT NULL,
    PRIMARY KEY (service_date, train_no, station_id)
);

-- Raw responses, compressed, so we can re-parse if a parser was wrong.
CREATE TABLE IF NOT EXISTS raw_snapshots (
    id         INTEGER PRIMARY KEY,
    fetched_at TEXT NOT NULL,
    source     TEXT NOT NULL,
    key        TEXT NOT NULL,
    body_gz    BLOB NOT NULL
);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    return conn
