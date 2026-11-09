"""Timezone parsing, countdown formatting, and deadline colors."""

import re
from datetime import datetime, timezone, timedelta

def parse_timezone(tz_string: str):
    """
    Parse timezone strings used by ccfddl.

    Supported:
        UTC
        UTC+8
        UTC-12
        AoE
        PT
    """
    if not tz_string:
        return timezone.utc
    tz_string = str(tz_string).strip()
    if tz_string.upper() == 'AOE':
        return timezone(timedelta(hours=-12))
    if tz_string.upper() == 'PT':
        try:
            from zoneinfo import ZoneInfo
            return ZoneInfo('America/Los_Angeles')
        except Exception:
            return timezone(timedelta(hours=-8))
    if tz_string.upper() == 'UTC':
        return timezone.utc
    match = re.match('UTC([+-])(\\d+(?:\\.\\d+)?)$', tz_string.upper())
    if match:
        sign = 1 if match.group(1) == '+' else -1
        hours = float(match.group(2))
        return timezone(timedelta(hours=sign * hours))
    return timezone.utc

def parse_deadline(deadline_string: str, tz_string: str) -> datetime | None:
    """
    Convert a ccfddl deadline string into an aware datetime.
    """
    if not deadline_string:
        return None
    try:
        dt = datetime.strptime(str(deadline_string), '%Y-%m-%d %H:%M:%S')
        tz = parse_timezone(tz_string)
        return dt.replace(tzinfo=tz)
    except Exception:
        return None

def format_countdown(deadline: datetime, estimated: bool=False) -> tuple[str, int]:
    """
    Return:
        display string
        remaining minutes

    Countdown uses minute as the smallest unit. Each number occupies at least
    two monospace characters, with spaces rather than leading zeroes.
    """
    now = datetime.now(timezone.utc)
    deadline_utc = deadline.astimezone(timezone.utc)
    remaining_seconds = (deadline_utc - now).total_seconds()
    if remaining_seconds <= 0:
        return ('DEADLINE', 0)
    total_minutes = int(remaining_seconds // 60)
    if estimated:
        days = (total_minutes + 1439) // 1440
        return (f'~ {days:2d}d', total_minutes)
    days = total_minutes // 1440
    hours = total_minutes % 1440 // 60
    minutes = total_minutes % 60
    if days > 0:
        return (f'{days:2d}d {hours:2d}h {minutes:2d}m', total_minutes)
    if hours > 0:
        return (f'{hours:2d}h {minutes:2d}m', total_minutes)
    return (f'{minutes:2d}m', total_minutes)

def countdown_color(remaining_minutes: int, estimated: bool=False) -> str:
    """
    Color policy:

        estimated (CFP not open)  -> white
        open, > 14 days           -> green
        open, 5~14 days           -> yellow
        open, < 5 days            -> red
    """
    if estimated:
        return '#f2f5f8'
    if remaining_minutes <= 0:
        return '#ff4d4d'
    five_days = 5 * 24 * 60
    two_weeks = 14 * 24 * 60
    if remaining_minutes < five_days:
        return '#ff5555'
    if remaining_minutes <= two_weeks:
        return '#ffd84d'
    return '#5fd68a'
