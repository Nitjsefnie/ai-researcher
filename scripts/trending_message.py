"""The commit message for a moved top-10 list."""
from __future__ import annotations


def message(old: list[dict[str, str]], new: list[dict[str, str]],
            key: str, prefix: str, entered_label: str) -> str:
    """Name entries, departures and rank changes."""
    before = {item[key]: rank for rank, item in enumerate(old, 1)}
    after = {item[key]: rank for rank, item in enumerate(new, 1)}
    entered = [item[key] for item in new if item[key] not in before]
    left = [item[key] for item in old if item[key] not in after]
    moved = [item[key] for item in new
             if item[key] in before and before[item[key]] != after[item[key]]]
    if entered:
        subject = f"{prefix} {len(entered)} {entered_label}: " + ", ".join(entered)
    elif moved:
        subject = f"{prefix} {len(moved)} rank change(s)"
    else:
        subject = f"{prefix} order updated"
    # Ranks never carry "#": GitHub links "#N" in a commit message to issue N.
    body = [f"NEW  rank {after[name]} {name}" for name in entered]
    body += [f"OUT  {name} (was rank {before[name]})" for name in left]
    body += [f"MOVE {name} rank {before[name]} -> {after[name]}" for name in moved]
    return subject + ("\n\n" + "\n".join(body) if body else "") + "\n"
