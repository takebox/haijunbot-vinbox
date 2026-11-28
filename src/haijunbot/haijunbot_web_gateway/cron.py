# -*- coding: utf-8 -*-
"""Lightweight 5-field cron expression parsing and next-match time calculation (zero third-party dependencies).

Supports the standard 5-field format: ``minute hour day month weekday``

- minute: 0-59
- hour: 0-23
- day: 1-31
- month: 1-12
- weekday: 0-7 (both 0 and 7 mean Sunday)

Field syntax support:

- ``*``: any value
- Number: e.g. ``5``
- Range: e.g. ``1-5``
- Step: e.g. ``*/15``, ``1-59/2``
- List: e.g. ``1,15,30`` (may mix the above forms)

Semantics: **the day and weekday fields have an OR relationship** (consistent with standard cron), i.e. the schedule triggers if either the day-of-month field or the weekday field matches.
"""

from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from typing import List, Optional


# Value ranges for each field (used for validation)
_FIELD_RANGES = {
    "minute": (0, 59),
    "hour": (0, 23),
    "day": (1, 31),
    "month": (1, 12),
    "weekday": (0, 7),
}

# Scan limit: scan forward at most 5 years (at minute granularity), enough to cover the next match point of any cron expression.
_MAX_SCAN_MINUTES = 5 * 366 * 24 * 60


class CronParseError(ValueError):
    """cron expression parse error."""


def _parse_field(field: str, field_name: str) -> List[int]:
    """Parse a single cron field and return the set of matching values (sorted, deduplicated)."""
    lo, hi = _FIELD_RANGES[field_name]
    values: set[int] = set()

    for part in field.split(","):
        part = part.strip()
        if not part:
            raise CronParseError(f"empty field part in '{field_name}'")
        step = 1
        if "/" in part:
            base, step_str = part.split("/", 1)
            try:
                step = int(step_str)
            except ValueError:
                raise CronParseError(f"invalid step '{step_str}' in '{field_name}'")
            if step <= 0:
                raise CronParseError(f"step must be > 0 in '{field_name}'")
        else:
            base = part

        if base == "*":
            start, end = lo, hi
        elif "-" in base:
            start_str, end_str = base.split("-", 1)
            try:
                start = int(start_str)
                end = int(end_str)
            except ValueError:
                raise CronParseError(f"invalid range '{base}' in '{field_name}'")
        else:
            try:
                start = int(base)
            except ValueError:
                raise CronParseError(f"invalid value '{base}' in '{field_name}'")
            end = start

        if start < lo or end > hi:
            raise CronParseError(
                f"value out of range in '{field_name}': {base} (allowed {lo}-{hi})"
            )
        if start > end:
            raise CronParseError(f"range start > end in '{field_name}': {base}")

        values.update(range(start, end + 1, step))

    if not values:
        raise CronParseError(f"no valid values in '{field_name}'")
    return sorted(values)


class CronSchedule:
    """A parsed cron expression."""

    def __init__(self, expression: str) -> None:
        self.expression = expression
        fields = expression.split()
        if len(fields) != 5:
            raise CronParseError(
                f"cron expression must have 5 fields (minute hour day month weekday), got {len(fields)}: {expression!r}"
            )
        self.minutes = _parse_field(fields[0], "minute")
        self.hours = _parse_field(fields[1], "hour")
        self.days = _parse_field(fields[2], "day")
        self.months = _parse_field(fields[3], "month")
        # Weekday field 0-7: both 0 and 7 mean Sunday. Convert to Python weekday (0=Monday..6=Sunday):
        # cron value w -> (w - 1) % 7, i.e. 1->0(Mon) ... 7->6(Sun), 0->6(Sun).
        self.weekdays = sorted(
            {(w - 1) % 7 for w in _parse_field(fields[4], "weekday")}
        )
        # Record whether the day/weekday fields are restricted (not *), for Vixie cron day-vs-weekday semantics:
        # If one field is * and the other is restricted, the * field is ignored and only the restricted field is matched;
        # If both are restricted, OR is used (either match triggers); if both are *, then every day.
        self._day_restricted = fields[2].strip() != "*"
        self._weekday_restricted = fields[4].strip() != "*"

    def matches(self, dt: datetime) -> bool:
        """Determine whether the given time matches this cron expression."""
        if dt.minute not in self.minutes:
            return False
        if dt.hour not in self.hours:
            return False
        if dt.month not in self.months:
            return False
        day_match = dt.day in self.days
        weekday_match = dt.weekday() in self.weekdays
        if self._day_restricted and self._weekday_restricted:
            # Both restricted: OR semantics
            return day_match or weekday_match
        if self._day_restricted:
            # Only the day field is restricted: match by day only
            return day_match
        if self._weekday_restricted:
            # Only the weekday field is restricted: match by weekday only
            return weekday_match
        # Both are *: every day
        return True

    def _day_matches(self, dt: datetime) -> bool:
        """Determine whether the given date (ignoring minute/hour) satisfies the cron's day-level condition.

        Consistent with the decision logic in :meth:`matches` excluding minute/hour.
        """
        if dt.month not in self.months:
            return False
        day_match = dt.day in self.days
        weekday_match = dt.weekday() in self.weekdays
        if self._day_restricted and self._weekday_restricted:
            return day_match or weekday_match
        if self._day_restricted:
            return day_match
        if self._weekday_restricted:
            return weekday_match
        return True

    def _first_match_in_day(
        self, day: datetime, from_candidate: datetime
    ) -> Optional[datetime]:
        """Return the first matching time within ``day`` that is ``>= from_candidate``; or None if there is none.

        Precondition: ``day``'s day-level condition is satisfied (``_day_matches(day)`` is True).
        """
        for hour in self.hours:
            for minute in self.minutes:
                dt = day.replace(hour=hour, minute=minute)
                if dt >= from_candidate and self.matches(dt):
                    return dt
        return None

    def next_match(self, from_ts: float) -> float:
        """Return the next matching timestamp strictly greater than from_ts."""
        base = datetime.fromtimestamp(from_ts)
        # Start scanning from the next whole minute after from_ts
        candidate = (base + timedelta(minutes=1)).replace(second=0, microsecond=0)

        # Scan by jumping in days: within the same day, month/day/weekday do not change, only minute/hour change.
        # For each day whose "day-level condition is satisfied", directly compute that day's first matching time, avoiding minute-by-minute scanning;
        # For days whose "day-level condition is not satisfied" (e.g. February 30), skip the whole span to avoid scanning for 5 years.
        scanned = 0
        while scanned < _MAX_SCAN_MINUTES:
            if not self._day_matches(candidate):
                next_day = (candidate + timedelta(days=1)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                scanned += int((next_day - candidate).total_seconds() // 60)
                candidate = next_day
                continue
            # Day-level condition satisfied: compute the day's first matching time
            day_start = candidate.replace(hour=0, minute=0, second=0, microsecond=0)
            first = self._first_match_in_day(day_start, candidate)
            if first is not None and first >= candidate:
                return first.timestamp()
            # No match for the day or the match time has passed; jump to the next day
            next_day = (day_start + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            scanned += int((next_day - candidate).total_seconds() // 60)
            candidate = next_day
        raise CronParseError(
            f"no matching time found within scan window for cron: {self.expression!r}"
        )


def parse_cron(expression: str) -> CronSchedule:
    """Parse a cron expression; raises :class:`CronParseError` when invalid."""
    if not isinstance(expression, str) or not expression.strip():
        raise CronParseError("cron expression must be a non-empty string")
    return CronSchedule(expression)


def cron_next_match(expression: str, from_ts: float) -> float:
    """Convenience function: return the next matching timestamp of the cron expression after from_ts."""
    return parse_cron(expression).next_match(from_ts)
