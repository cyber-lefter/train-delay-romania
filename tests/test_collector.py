from datetime import date
from pathlib import Path

import pytest

from collector import db, live, stats, timetable
from collector.live import LiveStop

GTFS = Path(__file__).parent / "fixtures" / "gtfs"


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "t.sqlite")
    timetable.import_gtfs(c, GTFS)
    return c


def test_parse_time_handles_after_midnight_and_seconds():
    assert timetable.parse_time("25:40:00") == 1540
    assert timetable.parse_time("23:50:30") == 1431
    assert timetable.parse_time("") is None


def test_calendar_exceptions(conn):
    assert timetable.trains_running_on(conn, date(2026, 10, 26)) == ["1621"]
    assert timetable.trains_running_on(conn, date(2026, 10, 27)) == []  # removed
    assert timetable.trains_running_on(conn, date(2026, 10, 31)) == ["1621"]  # added Saturday
    assert timetable.trains_running_on(conn, date(2026, 11, 1)) == []  # Sunday


def test_station_names_cleaned(conn):
    assert conn.execute("SELECT name FROM stations WHERE station_id = '10018'").fetchone()[0] == "Ploieşti Vest"


def test_record_matches_names_and_freezes_passed_stops(conn):
    day = date(2026, 10, 26)
    stops = [LiveStop("Bucuresti Nord Gr. A", None, 5, True),
             LiveStop("Ploiești Vest", 12, 14, False),
             LiveStop("Nowhere", 1, 1, False)]
    assert live.record(conn, "test", "1621", day, b"raw", stops) == 2

    live.record(conn, "test", "1621", day, b"raw", [LiveStop("Bucuresti Nord Gr. A", None, 99, True),
                                                    LiveStop("Ploiesti Vest", 20, 22, True)])
    rows = dict(conn.execute("SELECT station_id, dep_delay FROM observations").fetchall())
    assert rows == {"10017": 5, "10018": 22}
    assert conn.execute("SELECT COUNT(*) FROM raw_snapshots").fetchone()[0] == 2


def test_history(conn):
    for day, delay in [(26, 10), (28, 40), (29, 20)]:
        live.record(conn, "test", "1621", date(2026, 10, day), b"", [LiveStop("Brasov", delay, None, True)])
    h = stats.train_history(conn, "1621")
    assert h["runs"] == 3 and h["median_delay"] == 20 and h["late_30"] == 1
