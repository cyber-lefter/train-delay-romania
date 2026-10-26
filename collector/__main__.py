import argparse
import json
from datetime import date

from . import db, live, stats, timetable
from .sources import SOURCES


def main() -> None:
    p = argparse.ArgumentParser(prog="collector")
    p.add_argument("--db", default="data/delays.sqlite")
    sub = p.add_subparsers(dest="cmd", required=True)

    imp = sub.add_parser("import-timetable", help="load a GTFS folder or zip")
    imp.add_argument("path")

    today = sub.add_parser("today", help="list trains scheduled today")
    today.add_argument("--date", type=date.fromisoformat, default=date.today())

    col = sub.add_parser("collect", help="poll live delays once")
    col.add_argument("--source", choices=sorted(SOURCES), required=True)
    col.add_argument("--train", action="append", help="limit to these trains")

    hist = sub.add_parser("history", help="delay history for a train")
    hist.add_argument("train_no")

    args = p.parse_args()
    conn = db.connect(args.db)

    if args.cmd == "import-timetable":
        print(timetable.import_gtfs(conn, args.path))
    elif args.cmd == "today":
        trains = timetable.trains_running_on(conn, args.date)
        print(f"{len(trains)} trains on {args.date}")
    elif args.cmd == "collect":
        print(live.collect_once(conn, SOURCES[args.source](), args.train))
    elif args.cmd == "history":
        print(json.dumps(stats.train_history(conn, args.train_no), indent=2))


if __name__ == "__main__":
    main()
