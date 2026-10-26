"""Parser for the 'Trenul meu' train page on mersultrenurilor.infofer.ro.

The page's live data comes from a POST to /ro-RO/Trains/TrainsResult that is guarded by a
Cloudflare Turnstile check, so we do not fetch it automatically. This parser reads pages a
person saved from their browser (Ctrl+S), or the same HTML from an official source later.
"""
import html
import re
from datetime import date

from ..live import LiveStop

_ITEM = re.compile(r'<li class="list-group-item">(.*?)</li>', re.S)
_STATION = re.compile(r'/Statie/[^"]*">([^<]+)</a>')
# A time cell: the scheduled time, then a status line such as "+2 min (întârziere)",
# "la timp", or a grey "*" value when the delay is only estimated.
_CELL = re.compile(r'<div class="text-1-3rem[^"]*">\s*\d{1,2}:\d{2}\s*</div>\s*'
                   r'<div class="text-0-8rem([^"]*)">\s*([^<]*?)\s*</div>', re.S)
_DELAY = re.compile(r'([+-]?\d+)\s*min')
_INPUT = r'id="{}" name="{}"'


def _hidden(page: str, name: str) -> str | None:
    m = re.search(r'value="([^"]*)"[^>]*' + _INPUT.format(name, name), page)
    return m and m.group(1)


def _delay(css: str, text: str) -> tuple[int | None, bool]:
    """Return (minutes, estimated)."""
    estimated = "gray" in css or "*" in text
    if "la timp" in text:
        return 0, estimated
    m = _DELAY.search(text)
    return (int(m.group(1)) if m else None), estimated


def parse_train_page(page: str) -> tuple[str | None, date | None, list[LiveStop]]:
    """Return (train number, service date, stops) from a saved train page."""
    raw_date = _hidden(page, "Date")
    service_date = None
    if raw_date:
        d, m, y = (int(x) for x in raw_date.split("."))
        service_date = date(y, m, d)

    stops = []
    for item in _ITEM.findall(page):
        station = _STATION.search(item)
        if not station:
            continue
        # Left column holds the arrival, right column the departure. A first stop has no
        # arrival and a last stop no departure, so tell them apart by position.
        left, _, right = item.partition(station.group(0))
        arr = _CELL.search(left)
        dep = _CELL.search(right)
        arr_delay, arr_est = _delay(*arr.groups()) if arr else (None, False)
        dep_delay, dep_est = _delay(*dep.groups()) if dep else (None, False)
        reported = (arr or dep) is not None and not (arr_est or dep_est)
        stops.append(LiveStop(html.unescape(station.group(1)).strip(), arr_delay, dep_delay,
                              passed=reported))
    return _hidden(page, "TrainRunningNumber"), service_date, stops
