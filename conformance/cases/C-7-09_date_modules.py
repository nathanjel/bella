# clause: C-7-09
# spec: section 7
# status: P1
# source: dialect specification section 7, Dates (datetime via _pydatetime, time, calendar)
"""Date modules on fixed instants and fixed offsets only (no local time zone, no clock)."""
import calendar
import datetime as dt
import time

d = dt.date(2024, 2, 28)
print(d + dt.timedelta(days=2), d.isoformat(), d.weekday(), d.isocalendar(), d.toordinal(), dt.date.fromordinal(738000))
print(d.strftime("%A %d %B %Y, day %j, week %U"), dt.date.fromisoformat("2026-11-01").replace(day=30))
t = dt.datetime(2026, 11, 1, 13, 45, 30, 123456)
print(t.isoformat(), t.isoformat(sep=" ", timespec="milliseconds"), repr(t), t.timestamp() if False else "-")
tz = dt.timezone(dt.timedelta(hours=2), "CEST")
aware = t.replace(tzinfo=tz)
print(aware.isoformat(), aware.utcoffset(), aware.tzname(), aware.astimezone(dt.UTC).isoformat(), aware.timestamp())
print(dt.datetime.fromtimestamp(0, dt.UTC), dt.datetime.fromisoformat("2026-11-01T10:00:00+05:30"), dt.datetime.fromisoformat("2026-11-01T10:00Z"))
delta = dt.timedelta(days=-1, seconds=3661, microseconds=5)
print(delta, repr(delta), delta.total_seconds(), dt.timedelta(hours=25) // dt.timedelta(hours=1), abs(delta))
print(dt.datetime.strptime("01/11/26 07:08", "%d/%m/%y %H:%M"), (dt.date(2026, 12, 25) - dt.date(2026, 11, 1)).days)
print(dt.datetime(2026, 1, 1) < dt.datetime(2026, 1, 2), dt.time(23, 59, 59, 999999).isoformat(), dt.date.max, dt.timedelta.max)

print(time.gmtime(0), time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(1_700_000_000)), calendar.timegm(time.gmtime(1_700_000_000)))
print(time.strptime("2026-11-01", "%Y-%m-%d")[:6], time.struct_time((2026, 11, 1, 0, 0, 0, 6, 305, 0)).tm_yday)
print(calendar.monthrange(2024, 2), calendar.isleap(2100), calendar.leapdays(2000, 2026), calendar.weekday(2026, 11, 1))
print(calendar.month(2026, 11))
print(calendar.monthcalendar(2026, 2)[0], list(calendar.day_abbr), calendar.month_name[11])
