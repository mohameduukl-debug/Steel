#!/usr/bin/env python3
"""PreToolUse (Bash) hook: block the connection sizing tools until a precedent gate has passed.

Allowed when .claude/state/precedent_gate.json holds a passed gate younger than MAX_AGE_H, when the command
only asks for --help, or when it carries PRECEDENTS_SKIP=1 (re-checking an existing design, or the user said
to skip the precedent step)."""
import datetime as dt
import json
import os
import re
import sys

TOOLS = re.compile(r"python3?\s+[^;&|\n]*?(pin_connection|corner_plate|steel_joint_checks|fatigue_check|steel_part_dxf)\.py")
MAX_AGE_H = 24
HERE = os.path.dirname(os.path.abspath(__file__))


def gate_ok(path, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    try:
        with open(path) as fh:
            state = json.load(fh)
    except (OSError, ValueError):
        return None
    for node, g in state.items():
        try:
            t = dt.datetime.fromisoformat(g["time"])
        except (KeyError, ValueError):
            continue
        if g.get("passed") and (now - t).total_seconds() <= MAX_AGE_H * 3600:
            return node
    return None


def decide(command, gate_file):
    m = TOOLS.search(command or "")
    if not m or "PRECEDENTS_SKIP=1" in command or re.search(r"\s(-h|--help)\b", command):
        return None
    if gate_ok(gate_file):
        return None
    return (f"{m.group(1)}.py sizes a connection, but no connection-precedents gate has passed in the last {MAX_AGE_H} h. "
            "Run the connection-precedents skill first (Pinterest search -> pinterest_fetch.py -> view images -> "
            "board -> 'precedent_search.py check <precedents.json>' = PASS). If the user explicitly asked to skip the "
            "precedent step, or this only re-checks an existing design, prefix the command with PRECEDENTS_SKIP=1 and say so.")


def main():
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return
    root = os.environ.get("CLAUDE_PROJECT_DIR") or os.path.dirname(os.path.dirname(HERE))
    reason = decide(data.get("tool_input", {}).get("command", ""),
                    os.path.join(root, ".claude", "state", "precedent_gate.json"))
    if reason:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                                 "permissionDecisionReason": reason}}))


if __name__ == "__main__":
    main()
