# Productivity Assistant: how priorities are scored

Status: implemented in M2 (`productivity_assistant/priorities.py`). The worked
example below is checked by `tests/test_priorities.py`.

Every open task gets a score. The Today page shows each factor's points, so the
reason for every rank is visible. No AI is involved.

| Factor | Points | Label shown |
| --- | --- | --- |
| Due date | Overdue: 60 + 2 per day overdue (up to 10 days, so at most 80). Today 50, tomorrow 40, in 2 days 30, in 3–7 days 15, in 8–14 days 5, later or none 0 | "Overdue by 1 day", "Due tomorrow" |
| Importance | Low 0, Normal 15, High 30 | "High importance" |
| Blocking others | 10 per open task waiting on this one, at most 30 | "Blocks 1 open task" |
| Effort | 30 minutes or less 5; 31–60 minutes 2; otherwise 0 | "Quick win (15 min)" |
| Age | 1 per full week since the task was last changed, at most 10 | "Untouched for 5 weeks" |
| Waiting on another task | −25 while any task it depends on is open | "Waiting on: Budget review" |
| Your Up / Down | +20 / −20 | "You raised it" |

- **Weights.** The first five factors are multiplied by a weight from 0 to 3
  (default 1), set in Settings and resettable there.
- **Pins come first,** oldest pin first, regardless of score.
- **Ties** are broken by earliest due date, then by creation order.
- **Snoozed tasks** are hidden until their snooze date.
- **Feedback is recorded, not applied.** Every Up, Down, pin, unpin and snooze is
  stored with the task's rank and score at that moment. A later milestone may use
  it to *propose* weight changes, which you accept or dismiss.

## Worked example

On 2026-09-28, with default weights:

| Rank | Task | Facts | Points | Score |
| --- | --- | --- | --- | --- |
| 1 | Call dentist | Normal importance, **pinned** | 15 | 15 (pinned) |
| 2 | Pay invoice | Due 2026-09-27, Normal, 15 min | 62 + 15 + 5 | 82 |
| 3 | Budget review | Due 2026-10-02, High, the Q3 report waits on it | 15 + 30 + 10 | 55 |
| 4 | Q3 report | Due 2026-09-29, High, waiting on Budget review | 40 + 30 − 25 | 45 |
| 5 | Tidy notes | No due date, Low, last changed 2026-08-24 | 5 | 5 |

If Budget review is completed, Q3 report no longer waits and scores 70.
