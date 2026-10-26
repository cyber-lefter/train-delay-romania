import sqlite3


def train_history(conn: sqlite3.Connection, train_no: str, station_id: str | None = None) -> dict:
    """Delay history for a train at one station (default: its final stop)."""
    if station_id is None:
        row = conn.execute("SELECT station_id FROM scheduled_stops WHERE train_no = ? "
                           "ORDER BY seq DESC LIMIT 1", (train_no,)).fetchone()
        if row is None:
            raise KeyError(f"unknown train {train_no}")
        station_id = row[0]
    delays = [r[0] for r in conn.execute(
        "SELECT COALESCE(arr_delay, dep_delay) FROM observations "
        "WHERE train_no = ? AND station_id = ? AND passed = 1 "
        "AND COALESCE(arr_delay, dep_delay) IS NOT NULL ORDER BY service_date", (train_no, station_id))]
    if not delays:
        return {"train_no": train_no, "station_id": station_id, "runs": 0}
    ordered = sorted(delays)
    return {
        "train_no": train_no,
        "station_id": station_id,
        "runs": len(delays),
        "median_delay": ordered[len(ordered) // 2],
        "late_15": sum(d >= 15 for d in delays),
        "late_30": sum(d >= 30 for d in delays),
        "last_runs": delays[-10:],
    }
