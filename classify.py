#!/usr/bin/env python3
"""Turn newly-scraped Yiddish posts into English board cards.

This is the judgement step the scraper deliberately does not do. scrape_ivelt.py
extracts structure (who, when, what thread, what text) with selectors and regex;
nothing in it understands what a post means. Without this file, re-running the
scraper redeploys an identical page forever.

Every card produced here is marked review=true so the board can show that a human
has not checked it. Promote a card by deleting that flag in data/status.json.

  export ANTHROPIC_API_KEY=...
  ./.venv/bin/python classify.py            # only unseen posts
  ./.venv/bin/python classify.py --limit 5  # cheap dry run
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Literal

import anthropic
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
AUTHOR = DATA / "author_ari_greenfield.json"
STATUS = DATA / "status.json"
SEEN = DATA / "seen_posts.json"

MODEL = "claude-opus-5"
BATCH = 12  # posts per request

LANES = {
    "reported": "the maker has seen it and confirmed it, but committed to no work",
    "queued": "accepted and scheduled, but explicitly behind other work or a holiday",
    "active": "actively being fixed right now",
    "shipped": "already went out to devices",
    "none": "not a product-status statement at all",
}

SYSTEM = f"""You triage forum posts written by Ari Greenfield, who makes the \
MindPhone (a kosher basic phone). The posts are in Yiddish, sometimes mixed with \
English. They are scraped from a public forum.

For each post, decide whether it says something concrete about the STATUS of the \
product: a bug being worked on, a fix shipping, a feature queued, a release note.

Lanes:
{chr(10).join(f'- {k}: {v}' for k, v in LANES.items())}

Rules:
- Chatter, thanks, prices, marketing, shop locations and arguments with \
competitors are NOT product status. Use lane "none" and relevant=false.
- Distinguish carefully between an acknowledgement ("we're looking into it") \
which is `reported`, and real committed work in flight ("we made progress today, \
testing soon") which is `active`. This distinction decides where a card lands, so \
do not inflate it.
- `title`: a short English noun phrase, max 8 words. No trailing period.
- `detail`: 1-2 plain English sentences, written for a reader who does not read \
Yiddish and has no context. Neutral and factual. Do not invent specifics that are \
not in the post.
- `eta`: quote any timing the post gives, in English ("after Sukkos", "next week"). \
If it gives none, use "No date given".
- If unsure whether a post is status, prefer relevant=false. A missing card is \
much cheaper than a wrong one."""


class Card(BaseModel):
    post_id: str
    relevant: bool
    lane: Literal["reported", "queued", "active", "shipped", "none"]
    title: str
    detail: str
    eta: str


class Batch(BaseModel):
    cards: List[Card]


def load(path, default):
    return json.loads(path.read_text()) if path.exists() else default


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, help="only classify N new posts")
    ap.add_argument("--all", action="store_true", help="ignore the seen ledger")
    args = ap.parse_args()

    posts = load(AUTHOR, [])
    if not posts:
        sys.exit("no scraped posts - run scrape_ivelt.py --author ari_greenfield first")
    status = load(STATUS, {})
    seen = set() if args.all else set(load(SEEN, []))

    # Anything already on the board counts as seen, so hand-written cards are
    # never duplicated by the classifier.
    for entry in status.get("in_progress", []) + status.get("shipped", []):
        if entry.get("post_id"):
            seen.add(entry["post_id"])

    fresh = [p for p in posts if p["post_id"] not in seen and p["text"].strip()]
    fresh.sort(key=lambda p: p["datetime"], reverse=True)
    if args.limit:
        fresh = fresh[: args.limit]
    if not fresh:
        print("nothing new to classify")
        return

    print(f"classifying {len(fresh)} post(s) with {MODEL}", file=sys.stderr)
    # Same trailing-newline hazard as the Firecrawl key.
    key = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    client = anthropic.Anthropic(api_key=key) if key else anthropic.Anthropic()
    added = 0

    for i in range(0, len(fresh), BATCH):
        chunk = fresh[i : i + BATCH]
        payload = [
            {"post_id": p["post_id"], "date": p["datetime"][:10],
             "thread": p["topic_title"], "text": p["text"][:2500]}
            for p in chunk
        ]
        try:
            resp = client.messages.parse(
                model=MODEL,
                max_tokens=16000,
                system=SYSTEM,
                thinking={"type": "adaptive"},
                messages=[{"role": "user", "content":
                           "Triage these posts. Return one card per post.\n\n"
                           + json.dumps(payload, ensure_ascii=False, indent=1)}],
                output_format=Batch,
            )
        except anthropic.RateLimitError:
            print("  rate limited - stopping early, rerun to continue", file=sys.stderr)
            break
        except anthropic.APIError as exc:
            print(f"  API error: {exc}", file=sys.stderr)
            break

        by_id = {p["post_id"]: p for p in chunk}
        for card in resp.parsed_output.cards:
            src = by_id.get(card.post_id)
            if src is None:
                continue
            seen.add(card.post_id)
            if not card.relevant or card.lane == "none":
                continue
            common = {
                "title": card.title,
                "date": src["datetime"][:10],
                "url": src["url"],
                "post_id": card.post_id,
                "review": True,
            }
            if card.lane == "shipped":
                status.setdefault("shipped", []).insert(
                    0, {**common, "items": [card.detail]})
            else:
                status.setdefault("in_progress", []).insert(
                    0, {**common, "detail": card.detail,
                        "eta": card.eta, "state": card.lane})
            added += 1
            print(f"  [{card.lane}] {card.title}", file=sys.stderr)

    status["shipped"] = sorted(
        status.get("shipped", []), key=lambda s: s["date"], reverse=True)
    STATUS.write_text(json.dumps(status, ensure_ascii=False, indent=2))
    SEEN.write_text(json.dumps(sorted(seen), indent=0))
    print(f"\nadded {added} card(s), {len(seen)} post(s) now triaged", file=sys.stderr)


if __name__ == "__main__":
    main()
