"""Live delay collection: a source reports per-stop delays, we log them against the timetable."""
import gzip
import sqlite3
import time
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Protocol
from zoneinfo import ZoneInfo

from .timetable import trains_running_on

RO = ZoneInfo("Europe/Bucharest")


@dataclass
class LiveStop:
    station_name: str
    arr_delay: int | None   # minutes
    dep_delay: int | None
    passed: bool


class LiveSource(Protocol):
    name: str

    def fetch(self, train_no: str, service_date: date) -> tuple[bytes, list[LiveStop]]:
        """Return the raw response and the parsed stops for one train run."""


def normalize(name: str) -> str:
    """'Ploieşti Vest' and 'Ploiești  Vest' -> 'ploiesti vest'."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return " ".join(ascii_name.lower().replace(".", " ").split())


def match_station(name: str, by_name: dict[str, str]) -> str | None:
    """Exact match, else the timetable name with a suffix: 'buftea' -> 'buftea hm'."""
    if name in by_name:
        return by_name[name]
    hits = [sid for full, sid in by_name.items() if full.startswith(name + " ")]
    return hits[0] if len(hits) == 1 else None


def record(conn: sqlite3.Connection, source: str, train_no: str, service_date: date,
           raw: bytes, stops: list[LiveStop]) -> int:
    """Store the raw response and upsert one observation per stop matched to the timetable."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    by_name = {
        normalize(r["name"]): r["station_id"]
        for r in conn.execute(
            "SELECT st.station_id, st.name FROM scheduled_stops s "
            "JOIN stations st USING (station_id) WHERE s.train_no = ?", (train_no,))
    }
    rows = []
    for s in stops:
        station_id = match_station(normalize(s.station_name), by_name)
        if station_id:
            rows.append((service_date.isoformat(), train_no, station_id,
                         s.arr_delay, s.dep_delay, int(s.passed), source, now))
    with conn:
        conn.execute("INSERT INTO raw_snapshots (fetched_at, source, key, body_gz) VALUES (?, ?, ?, ?)",
                     (now, source, f"{service_date}/{train_no}", gzip.compress(raw)))
        conn.executemany(
            "INSERT INTO observations VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (service_date, train_no, station_id) DO UPDATE SET "
            "arr_delay = excluded.arr_delay, dep_delay = excluded.dep_delay, "
            "passed = excluded.passed, source = excluded.source, observed_at = excluded.observed_at "
            "WHERE observations.passed = 0",  # once a stop is passed its delay is final
            rows)
    return len(rows)


def active_trains(conn: sqlite3.Connection, now: datetime, before: int = 30, after: int = 180) -> list[str]:
    """Trains whose run today is between `before` min before departure and `after` min past arrival."""
    local = now.astimezone(RO)
    minute = local.hour * 60 + local.minute
    running = set(trains_running_on(conn, local.date()))
    rows = conn.execute(
        "SELECT train_no, MIN(COALESCE(dep_min, arr_min)) AS start, MAX(COALESCE(arr_min, dep_min)) AS end "
        "FROM scheduled_stops GROUP BY train_no")
    return sorted(r["train_no"] for r in rows
                  if r["train_no"] in running and r["start"] - before <= minute <= r["end"] + after)


def collect_once(conn: sqlite3.Connection, source: LiveSource, trains: list[str] | None = None,
                 delay_between: float = 2.0) -> dict[str, int]:
    """Poll each active train once, politely spaced. Returns stops recorded per train."""
    now = datetime.now(timezone.utc)
    service_date = now.astimezone(RO).date()
    result = {}
    for train_no in trains or active_trains(conn, now):
        try:
            raw, stops = source.fetch(train_no, service_date)
        except Exception as exc:  # one failing train must not stop the round
            print(f"{train_no}: {exc}")
            continue
        result[train_no] = record(conn, source.name, train_no, service_date, raw, stops)
        time.sleep(delay_between)
    return result
