"""Rule-based reading of a capture note. No AI: dates, importance, effort and exact project names.

Code owns these fields because the model evaluation showed small models get them wrong
(docs/PRODUCTIVITY_MODEL_EVALUATION.md). Anything vague or contradictory is left empty.
"""
import calendar
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

MAX_EFFORT = 10080  # one week, the same limit as TaskIn
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
MONTHS = {name: number for number in range(1, 13)
          for name in (calendar.month_name[number].lower(), calendar.month_abbr[number].lower())}
MONTHS["sept"] = 9
CONNECTORS = {"by", "on", "due", "for", "the", "this", "about", "and", "at", "in", "before", "around", "until"}

_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_MONTH_DAY = re.compile(r"\b(" + "|".join(sorted(MONTHS, key=len, reverse=True)) + r")\.?\s+(\d{1,2})(?:st|nd|rd|th)?\b"
                        r"(?:,?\s*(\d{4})\b)?", re.I)
_RELATIVE = re.compile(r"\b(today|tonight|tomorrow|yesterday)\b", re.I)
_END_OF_MONTH = re.compile(r"\b(?:before\s+)?(?:the\s+)?end\s+of\s+(?:the\s+)?month\b", re.I)
_WEEKDAY = re.compile(r"\b(next\s+|this\s+)?(" + "|".join(WEEKDAYS) + r")\b", re.I)
_HIGH = re.compile(r"\b(urgent|asap|important|critical|high[ -]priority)\b", re.I)
_LOW = re.compile(r"\b(low[ -]priority|whenever|someday)\b", re.I)
_PHRASE_EFFORT = [(re.compile(r"\bhalf\s+an?\s+hour\b", re.I), 30), (re.compile(r"\b(?:an|one)\s+hour\b", re.I), 60),
                  (re.compile(r"\bhalf\s+a\s+day\b", re.I), 240)]
_NUMBER_EFFORT = re.compile(r"(-\s*)?(?<![\d.])(\d+(?:\.\d+)?)\s*(hours?|hrs?|h|minutes?|mins?|m)\b", re.I)


@dataclass
class Parsed:
    title: str
    due_date: Optional[date] = None
    importance: Optional[int] = None
    effort_minutes: Optional[int] = None
    project_id: Optional[int] = None
    notes: list = field(default_factory=list)  # what was ignored and why, shown to the user


def _resolve_dates(text: str, today: date, spans: list, notes: list) -> Optional[date]:
    explicit, relative = set(), set()
    for match in _ISO.finditer(text):
        spans.append(match.span())
        try:
            explicit.add(date(*map(int, match.groups())))
        except ValueError:
            notes.append(f"Ignored impossible date {match.group(0)}")
    for match in _MONTH_DAY.finditer(text):
        spans.append(match.span())
        month, day, year = MONTHS[match.group(1).lower()], int(match.group(2)), match.group(3)
        try:
            value = date(int(year) if year else today.year, month, day)
            if not year and value < today:
                value = value.replace(year=today.year + 1)
            explicit.add(value)
        except ValueError:
            notes.append(f"Ignored impossible date {match.group(0)}")
    for match in _RELATIVE.finditer(text):
        spans.append(match.span())
        offset = {"today": 0, "tonight": 0, "tomorrow": 1, "yesterday": -1}[match.group(1).lower()]
        relative.add(today + timedelta(days=offset))
    for match in _END_OF_MONTH.finditer(text):
        spans.append(match.span())
        relative.add(today.replace(day=calendar.monthrange(today.year, today.month)[1]))
    for match in _WEEKDAY.finditer(text):
        spans.append(match.span())
        if (match.group(1) or "").strip().lower() == "next":
            notes.append(f'"{match.group(0)}" is ambiguous; set the date yourself')
            continue
        ahead = (WEEKDAYS.index(match.group(2).lower()) - today.weekday()) % 7
        relative.add(today + timedelta(days=ahead))
    for found in (explicit, relative):  # an explicit date wins over a weekday ("Monday Oct 5")
        if len(found) == 1:
            return found.pop()
        if found:
            notes.append("The note names more than one date; set the date yourself")
            return None
    return None


def _effort(text: str, spans: list, notes: list) -> Optional[int]:
    values = set()
    for pattern, minutes in _PHRASE_EFFORT:
        for match in pattern.finditer(text):
            if not any(start <= match.start() < end for start, end in spans):
                spans.append(match.span())
                values.add(minutes)
    for match in _NUMBER_EFFORT.finditer(text):
        if any(start <= match.start() < end for start, end in spans):
            continue
        spans.append(match.span())
        amount = float(match.group(2)) * (60 if match.group(3).lower().startswith("h") else 1)
        if match.group(1) or not 1 <= amount <= MAX_EFFORT:
            notes.append(f"Ignored effort {match.group(0).strip()}")
            continue
        values.add(round(amount))
    if len(values) > 1:
        notes.append("The note names more than one duration; set the effort yourself")
        return None
    return values.pop() if values else None


def _importance(text: str, spans: list) -> Optional[int]:
    high, low = list(_HIGH.finditer(text)), list(_LOW.finditer(text))
    spans.extend(match.span() for match in high + low)
    if high and not low:
        return 3
    if low and not high:
        return 1
    return None


def _project(text: str, projects: list, spans: list, notes: list) -> Optional[int]:
    found = {}
    for project in projects:
        name = re.escape(project["name"])
        if re.search(rf"\b{name}\b", text, re.I):
            found[project["id"]] = project["name"]
            for pattern in (rf"\((?:the\s+)?{name}(?:\s+project)?\)", rf"\b(?:for|in)\s+(?:the\s+)?{name}\s+project\b",
                            rf"\bfor\s+(?:the\s+)?{name}\b(?=\s*(?:[,;.]|$))"):
                spans.extend(match.span() for match in re.finditer(pattern, text, re.I))
    if len(found) > 1:
        notes.append(f"The note mentions {' and '.join(sorted(found.values()))}; choose the project yourself")
        return None
    return next(iter(found), None)


def _title(text: str, spans: list, projects: list) -> str:
    chars = list(text)
    for start, end in spans:
        for index in range(start, end):
            chars[index] = ","
    names = {project["name"].lower() for project in projects}
    pieces = []
    for piece in re.split(r"[,;()]", "".join(chars)):
        words = piece.strip(" :.-").split()
        while words and words[0].lower() in CONNECTORS:
            words.pop(0)
        while words and words[-1].lower() in CONNECTORS:
            words.pop()
        cleaned = " ".join(words).strip(" :.-")
        if cleaned and cleaned.lower() not in names and cleaned.lower() not in {"project", "the project"}:
            pieces.append(cleaned)
    title = ", ".join(pieces) or text.strip()
    return (title[:1].upper() + title[1:])[:200]


def parse(text: str, today: date, projects: list) -> Parsed:
    """Read what the note states plainly. projects: rows with id and name."""
    text = " ".join(text.split())
    spans, notes = [], []
    due = _resolve_dates(text, today, spans, notes)
    importance = _importance(text, spans)
    effort = _effort(text, spans, notes)
    project_id = _project(text, projects, spans, notes)
    return Parsed(title=_title(text, spans, projects), due_date=due, importance=importance,
                  effort_minutes=effort, project_id=project_id, notes=notes)
