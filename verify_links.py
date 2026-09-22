#!/usr/bin/env python3
"""Check that every card on the board cites a post that actually exists.

Written after 11 of 18 hand-written source links turned out to point at
unrelated posts. A card whose link is wrong is worse than a missing card: it
looks sourced. This fails the build rather than publishing one.

Checks per card: the cited post is in the scraped corpus, it has text, and its
date matches the card's. Exits non-zero on any failure.

  ./.venv/bin/python verify_links.py          # pass/fail
  ./.venv/bin/python verify_links.py --show   # also print each cited post
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"


def corpus():
    posts = {}
    for name in ("posts.json", "author_ari_greenfield.json"):
        f = DATA / name
        if not f.exists():
            continue
        for p in json.loads(f.read_text()):
            posts.setdefault(p["post_id"], p)
    return posts


def main():
    show = "--show" in sys.argv
    status = json.loads((DATA / "status.json").read_text())
    posts = corpus()
    if not posts:
        sys.exit("no scraped posts to verify against")

    bad, checked = [], 0
    for sec in ("in_progress", "shipped", "unacknowledged"):
        for it in status.get(sec, []):
            checked += 1
            m = re.search(r"p=(\d+)", it["url"])
            if not m:
                bad.append((it["title"], "url has no post id"))
                continue
            pid = m.group(1)
            if it.get("post_id") and it["post_id"] != pid:
                bad.append((it["title"], f"post_id {it['post_id']} != url {pid}"))
            p = posts.get(pid)
            if p is None:
                bad.append((it["title"], f"p={pid} not in the scrape"))
                continue
            if not p["text"].strip():
                bad.append((it["title"], f"p={pid} has no text (image-only post)"))
                continue
            if p["datetime"][:10] != it["date"]:
                bad.append((it["title"],
                            f"card dated {it['date']} but p={pid} is {p['datetime'][:10]}"))
            if show:
                print(f"\n[{sec}] {it['title']}  ->  p={pid}  {p['datetime'][:10]}")
                print("   " + p["text"][:180].replace("\n", " "))

    print(f"\nchecked {checked} card(s)")
    if bad:
        print(f"FAILED - {len(bad)} bad link(s):")
        for t, why in bad:
            print(f"  - {t}: {why}")
        sys.exit(1)
    print("all source links resolve to a real post with matching date")


if __name__ == "__main__":
    main()
