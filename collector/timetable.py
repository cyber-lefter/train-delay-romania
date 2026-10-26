"""Imports the GTFS timetable built from data.gov.ro (Informatica Feroviara, OGL-ROU-1.0).

Feed: https://github.com/vasile/data.gov.ro-gtfs-exporter (gtfs-out/). In that feed the
trip_id is the train number and trip_short_name is the category (R, IR, IC, ...).
"""
import csv
import io
import sqlite3
import zipfile
from datetime import date, timedelta
from pathlib import Path


def parse_time(value: str) -> int | None:
    """'24:12:00' -> 1452 minutes. Seconds round to the nearest minute, half up."""
    if not value:
        return None
    h, m, s = (int(x) for x in value.split(":"))
    return h * 60 + m + (s + 30) // 60


def _reader(source: Path, name: str):
    if source.suffix == ".zip":
        zf = zipfile.ZipFile(source)
        return csv.DictReader(io.TextIOWrapper(zf.open(name), encoding="utf-8-sig"))
    return csv.DictReader(open(source / name, encoding="utf-8-sig", newline=""))


def _parse_date(s: str) -> date:
    return date(int(s[:4]), int(s[4:6]), int(s[6:]))


def import_gtfs(conn: sqlite3.Connection, source: str | Path) -> dict[str, int]:
    source = Path(source)
    agencies = {r["agency_id"]: r["agency_name"] for r in _reader(source, "agency.txt")}
    routes = {r["route_id"]: r for r in _reader(source, "routes.txt")}

    with conn:
        for table in ("stations", "trains", "service_dates", "scheduled_stops"):
            conn.execute(f"DELETE FROM {table}")

        conn.executemany(
            "INSERT INTO stations VALUES (?, ?, ?, ?)",
            ((r["stop_id"], r["stop_name"].strip(" ,"), float(r["stop_lat"]), float(r["stop_lon"]))
             for r in _reader(source, "stops.txt")),
        )

        trains = []
        for t in _reader(source, "trips.txt"):
            route = routes[t["route_id"]]
            trains.append((t["trip_id"], t["trip_short_name"], agencies.get(route["agency_id"]),
                           route["route_long_name"], t["service_id"]))
        conn.executemany("INSERT INTO trains VALUES (?, ?, ?, ?, ?)", trains)

        conn.executemany(
            "INSERT INTO scheduled_stops VALUES (?, ?, ?, ?, ?)",
            ((r["trip_id"], int(r["stop_sequence"]), r["stop_id"],
              parse_time(r["arrival_time"]), parse_time(r["departure_time"]))
             for r in _reader(source, "stop_times.txt")),
        )

        conn.executemany("INSERT OR IGNORE INTO service_dates VALUES (?, ?)", _expand_calendar(source))

    return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ("stations", "trains", "scheduled_stops", "service_dates")}


def _expand_calendar(source: Path):
    weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    removed = set()
    added = []
    for r in _reader(source, "calendar_dates.txt"):
        key = (r["service_id"], _parse_date(r["date"]).isoformat())
        (added.append(key) if r["exception_type"] == "1" else removed.add(key))

    for r in _reader(source, "calendar.txt"):
        day, end = _parse_date(r["start_date"]), _parse_date(r["end_date"])
        while day <= end:
            key = (r["service_id"], day.isoformat())
            if r[weekdays[day.weekday()]] == "1" and key not in removed:
                yield key
            day += timedelta(days=1)
    yield from added


def trains_running_on(conn: sqlite3.Connection, day: date) -> list[str]:
    rows = conn.execute(
        "SELECT t.train_no FROM trains t JOIN service_dates s USING (service_id) "
        "WHERE s.date = ? ORDER BY t.train_no", (day.isoformat(),))
    return [r[0] for r in rows]
