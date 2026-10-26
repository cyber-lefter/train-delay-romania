# Train delay Romania

Shows Romanian train times on a station-board style screen and predicts delays from history.
Working name only; the app name gets picked before launch. Not affiliated with CFR.

## Status

Phase 0: the **collector**, which builds the delay history the predictions will come from.

- Timetable import: done, from the open data.gov.ro timetable.
- Delay log and history stats: done, tested.
- Live delay source: **not connected yet** (see "Live data").
- API and Android app: later.

## Quick start

Needs Python 3.11+, no other dependencies (`pytest` for tests).

```sh
git clone --depth 1 https://github.com/vasile/data.gov.ro-gtfs-exporter /tmp/gtfs
python -m collector import-timetable /tmp/gtfs/gtfs-out
python -m collector today            # how many trains run today
python -m collector history 1621     # delay history for a train (needs live data)
python -m pytest
```

The database goes to `data/delays.sqlite` by default (`--db` to change it).

## Data

- **Timetable**: published by Informatica Feroviară on data.gov.ro under the Romanian open
  government licence (OGL-ROU-1.0), converted to GTFS by
  [data.gov.ro-gtfs-exporter](https://github.com/vasile/data.gov.ro-gtfs-exporter) (MIT; please
  credit it). The current file covers 14 Dec 2025 to 12 Dec 2026 and about 2,100 trains.
- **Live data**: a source implements `LiveSource.fetch(train_no, date)` in `collector/sources/`
  and returns per-stop delays by station name; `live.record` matches names to the timetable,
  keeps the raw response gzipped, and freezes a stop's delay once the train has passed it.
  No source is registered yet. Infofer's public pages forbid copying without written consent,
  and EU Regulation 2017/1926 requires an official real-time feed for main lines since Dec 2025,
  so the plan is to ask Informatica Feroviară for access first.

## Layout

| Path | What |
| --- | --- |
| `collector/db.py` | SQLite schema |
| `collector/timetable.py` | GTFS import, which trains run on a date |
| `collector/live.py` | live source interface, recording, which trains to poll now |
| `collector/stats.py` | per-train delay history |
| `collector/__main__.py` | command line |
