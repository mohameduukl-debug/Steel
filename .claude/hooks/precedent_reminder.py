#!/usr/bin/env python3
"""UserPromptSubmit hook: when the prompt is about designing a connection, remind Claude to run the
connection-precedents skill (Pinterest precedent search + gate) before sizing anything."""
import json
import re
import sys

PAT = re.compile(
    r"connection|joint|detail(?:ing)?|corner plate|mast ?head|base plate|lug|gusset|clevis|fork|keder|clamp|"
    r"turnbuckle|tensioner|bale ring|saddle|anchor|"
    r"وصل[ةه]|وصلات|تفصيل[ةه]?|تفاصيل|بليت[ةه]|ركن|كلامب|كيدر|شداد|مشد|قاعد[ةه] عمود|رأس عمود|فورك|أنكور|انكور",
    re.I)
DESIGN = re.compile(r"design|detail|size|draw|sketch|improve|propose|صمم|تصميم|ارسم|رسم|حسب|احسب|اقترح|حسن|طور", re.I)


def main():
    try:
        prompt = json.load(sys.stdin).get("prompt", "")
    except ValueError:
        return
    if PAT.search(prompt) and DESIGN.search(prompt):
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": (
            "Project rule (CLAUDE.md): this looks like connection design. Run the connection-precedents skill FIRST: "
            "Pinterest search (WebSearch allowed_domains pinterest.com, incl. a variant and an Arabic query), "
            "pinterest_fetch.py to download and view the images, precedent board, then "
            "'precedent_search.py check' must PASS before pin_connection.py / corner_plate.py / steel_joint_checks.py "
            "are run (a PreToolUse hook blocks them otherwise).")}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
