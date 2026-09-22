#!/usr/bin/env python3
"""
Pull everything on iVelt related to the MindPhone (Ari Greenfield / Greentouch).

iVelt sits behind Cloudflare, so plain requests get a 403 challenge page.
Firecrawl renders the page and returns the HTML, which we then parse as
ordinary phpBB markup.

Every fetch is cached under data/cache/ keyed by URL, so re-runs are nearly
free and only new pages cost a Firecrawl credit.

  export FIRECRAWL_API_KEY=...
  ./.venv/bin/python scrape_ivelt.py            # incremental
  ./.venv/bin/python scrape_ivelt.py --refresh  # ignore cache
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
CACHE = DATA / "cache"
BASE = "https://www.ivelt.com/forum/"
API = "https://api.firecrawl.dev/v2/scrape"
KEY = os.environ.get("FIRECRAWL_API_KEY")

# Yiddish spellings vary; cast a wide net. "גרינטאטש" = Greentouch, the
# company; "גרינפעלד" = Greenfield.
SEARCH_TERMS = [
    "mindphone",
    "mind phone",
    "מיינדפאון",
    "מיינד פאון",
    "גרינטאטש",
    "greentouch",
    "גרינפעלד",
]

# A thread whose *title* matches is about the product -> scrape it end to end.
TOPIC_IS_DEDICATED = re.compile(
    r"(mindphone|mind\s*phone|מיינד\s*פאון|מיינדפאון)", re.I
)

SID = re.compile(r"[&?]sid=[0-9a-f]{32}")


def clean(url: str) -> str:
    """Drop the session id so the cache key is stable across runs."""
    url = SID.sub("", url)
    url = url.replace("viewtopic.php&", "viewtopic.php?")
    return url


def fetch(url: str, refresh: bool = False) -> str:
    url = clean(url)
    key = hashlib.sha1(url.encode()).hexdigest()[:16]
    blob = CACHE / f"{key}.html"
    if blob.exists() and not refresh:
        return blob.read_text()

    if not KEY:
        sys.exit("FIRECRAWL_API_KEY is not set")

    for attempt in range(4):
        try:
            r = requests.post(
                API,
                headers={"Authorization": f"Bearer {KEY}"},
                json={"url": url, "formats": ["html"], "onlyMainContent": False},
                timeout=120,
            )
            if r.status_code == 429:
                time.sleep(10 * (attempt + 1))
                continue
            r.raise_for_status()
            html = (r.json().get("data") or {}).get("html") or ""
            if html:
                blob.write_text(html)
                print(f"  fetched {url}", file=sys.stderr)
                time.sleep(1)
                return html
        except requests.RequestException as e:
            print(f"  retry ({e}) {url}", file=sys.stderr)
        time.sleep(5 * (attempt + 1))
    print(f"  FAILED {url}", file=sys.stderr)
    return ""


def absolute(href: str) -> str:
    if href.startswith("http"):
        return clean(href)
    return clean(BASE + href.lstrip("./"))


def discover(refresh=False):
    """Walk every search term's result pages; return topics + matching posts."""
    topics, post_hits = {}, {}
    for term in SEARCH_TERMS:
        start, seen_pages = 0, 0
        while seen_pages < 12:  # safety stop
            url = f"{BASE}search.php?keywords={requests.utils.quote(term)}&sr=posts&sk=t&sd=d&start={start}"
            html = fetch(url, refresh)
            if not html:
                break
            soup = BeautifulSoup(html, "html.parser")
            blocks = soup.select("div.search-result, div.post")
            found = 0
            for a in soup.select('a[href*="viewtopic.php"]'):
                href = absolute(a.get("href", ""))
                tm = re.search(r"[?&]t=(\d+)", href)
                pm = re.search(r"[?&#]p=(\d+)", href) or re.search(r"#p(\d+)", href)
                title = a.get_text(strip=True)
                if tm and title and title.lower() != "jump to post":
                    tid = tm.group(1)
                    topics.setdefault(tid, re.sub(r"^Re:\s*", "", title))
                    found += 1
                if pm:
                    post_hits.setdefault(pm.group(1), term)
            # resolve post-only hits to their topic later
            nxt = soup.select_one('a[rel="next"]')
            print(f"[search] {term} start={start} links={found}", file=sys.stderr)
            if not nxt or found == 0:
                break
            start += 25
            seen_pages += 1
    return topics, post_hits


def topic_of(html: str):
    """Read the real topic id/title from the page heading, not from whatever
    viewtopic link happens to come first (that one is a global announcement)."""
    soup = BeautifulSoup(html, "html.parser")
    h = soup.select_one("h2.topic-title a, h2 a[href*='viewtopic.php']")
    if not h:
        return None, None
    m = re.search(r"[?&]t=(\d+)", h.get("href", ""))
    return (m.group(1) if m else None), h.get_text(strip=True)


def parse_posts(html: str, topic_id: str, topic_title: str):
    soup = BeautifulSoup(html, "html.parser")
    tid2, ttitle2 = topic_of(html)
    if tid2:
        topic_id, topic_title = tid2, (ttitle2 or topic_title)
    out = []
    for div in soup.select("div.post"):
        pid = (div.get("id") or "").lstrip("p")
        if not pid.isdigit():
            continue
        author_el = div.select_one("a.username, span.username, a.username-coloured")
        time_el = div.select_one("time")
        body = div.select_one("div.content")
        if body is None:
            continue
        # strip quoted-reply blocks so we keep each author's own words
        for q in body.select("blockquote"):
            q.decompose()
        text = re.sub(r"\n{3,}", "\n\n", body.get_text("\n", strip=True))
        title_el = div.select_one("h3 a")
        out.append(
            {
                "post_id": pid,
                "topic_id": topic_id,
                "topic_title": topic_title,
                "post_title": title_el.get_text(strip=True) if title_el else "",
                "author": author_el.get_text(strip=True) if author_el else "",
                "datetime": (time_el.get("datetime") if time_el else "") or "",
                "date_text": time_el.get_text(strip=True) if time_el else "",
                "url": f"{BASE}viewtopic.php?p={pid}#p{pid}",
                "text": text,
            }
        )
    return out


def page_count(html: str) -> int:
    soup = BeautifulSoup(html, "html.parser")
    n = 1
    for a in soup.select(".pagination a, .pagination-inner a"):
        m = re.search(r"[?&]start=(\d+)", a.get("href", ""))
        if m:
            n = max(n, int(m.group(1)) // 25 + 1)
    return n


# phpBB will list every post by one account, which beats keyword-guessing for
# the maker's own announcements. Found on any of his posts: the "username"
# link carries u=<id>, and profile-posts links to search.php?author_id=<id>.
AUTHORS = {"ari_greenfield": 23857}


# iVelt spells some months differently than you would guess (מארטש not מערץ,
# אוגוסט not אויגוסט); both variants are accepted so a spelling change upstream
# degrades to one missing date rather than a silent gap.
YI_MONTHS = {
    "יאנואר": 1, "פעברואר": 2, "מערץ": 3, "מארטש": 3, "אפריל": 4, "מאי": 5,
    "יוני": 6, "יולי": 7, "אויגוסט": 8, "אוגוסט": 8, "סעפטעמבער": 9,
    "אקטאבער": 10, "אקטובער": 10, "נאוועמבער": 11, "דעצעמבער": 12,
}


def yi_date(txt: str) -> str:
    """'מיטוואך סעפטעמבער 16, 2026 2:11 pm' -> '2026-09-16T14:11'.

    Search results print a localised date string instead of the <time> tag
    that topic pages carry, so we parse it ourselves.
    """
    m = re.search(r"([\u05d0-\u05ea]+)\s+(\d{1,2}),\s*(\d{4})(?:\s+(\d{1,2}):(\d{2})\s*(am|pm))?", txt)
    if not m:
        return ""
    mon = YI_MONTHS.get(m.group(1))
    if not mon:
        return ""
    day, year = int(m.group(2)), int(m.group(3))
    hh, mm = int(m.group(4) or 0), int(m.group(5) or 0)
    if m.group(6) == "pm" and hh != 12:
        hh += 12
    if m.group(6) == "am" and hh == 12:
        hh = 0
    return f"{year:04d}-{mon:02d}-{day:02d}T{hh:02d}:{mm:02d}"


def scrape_author(author_id: int, refresh=False, max_pages=40):
    """Every post by one account, newest first, straight from phpBB's own
    author search. Search hits carry no id attribute and no <time> tag, so the
    post id comes from the h3 permalink and the date from the localised text."""
    posts, start, page = {}, 0, 0
    while page < max_pages:
        url = f"{BASE}search.php?author_id={author_id}&sr=posts&start={start}"
        html = fetch(url, refresh)
        if not html:
            break
        soup = BeautifulSoup(html, "html.parser")
        found = 0
        for div in soup.select("div.search.post, div.post"):
            h = div.select_one("h3 a")
            if not h:
                continue
            pm = re.search(r"[?&]p=(\d+)", h.get("href", ""))
            if not pm:
                continue
            pid = pm.group(1)
            body = div.select_one("div.content")
            if body is None:
                continue
            for q in body.select("blockquote"):
                q.decompose()
            tl = div.select_one('dd a[href*="viewtopic.php?t="]')
            tm = re.search(r"[?&]t=(\d+)", tl.get("href", "")) if tl else None
            dt_el = div.select_one("dd.search-result-date") or div.select_one("time")
            raw = (dt_el.get_text(strip=True) if dt_el else "")
            posts[pid] = {
                "post_id": pid,
                "topic_id": tm.group(1) if tm else "",
                "topic_title": tl.get_text(strip=True) if tl else "",
                "author_id": author_id,
                "datetime": yi_date(raw),
                "date_text": raw,
                "url": f"{BASE}viewtopic.php?p={pid}#p{pid}",
                "text": re.sub(r"\n{3,}", "\n\n", body.get_text("\n", strip=True)),
            }
            found += 1
        print(f"[author {author_id}] start={start} posts={found}", file=sys.stderr)
        if found == 0:
            break
        start += 25
        page += 1
    return sorted(posts.values(), key=lambda p: p["datetime"], reverse=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--max-pages", type=int, default=40)
    ap.add_argument(
        "--author",
        help="pull every post by one account instead of keyword search "
        "(name from AUTHORS, or a raw phpBB user id)",
    )
    args = ap.parse_args()
    CACHE.mkdir(parents=True, exist_ok=True)

    if args.author:
        aid = AUTHORS.get(args.author, args.author)
        rows = scrape_author(int(aid), args.refresh, args.max_pages)
        DATA.mkdir(exist_ok=True)
        out = DATA / f"author_{args.author}.json"
        out.write_text(json.dumps(rows, ensure_ascii=False, indent=2))
        print(f"\nwrote {len(rows)} posts -> {out.name}", file=sys.stderr)
        return

    topics, post_hits = discover(args.refresh)
    print(f"\n{len(topics)} topics, {len(post_hits)} matching posts\n", file=sys.stderr)

    posts, seen = {}, set()

    # 1. Dedicated threads: scrape every page.
    for tid, title in sorted(topics.items()):
        if not TOPIC_IS_DEDICATED.search(title):
            continue
        first = fetch(f"{BASE}viewtopic.php?t={tid}", args.refresh)
        if not first:
            continue
        pages = min(page_count(first), args.max_pages)
        print(f"[topic {tid}] {title} -> {pages} page(s)", file=sys.stderr)
        for p in parse_posts(first, tid, title):
            posts[p["post_id"]] = p
        for i in range(1, pages):
            html = fetch(f"{BASE}viewtopic.php?t={tid}&start={i*25}", args.refresh)
            for p in parse_posts(html, tid, title):
                posts[p["post_id"]] = p
        seen.add(tid)

    # 2. Stray mentions inside big general threads: fetch only the page that
    #    actually holds the matching post.
    for pid in sorted(post_hits, key=int):
        if pid in posts:
            continue
        html = fetch(f"{BASE}viewtopic.php?p={pid}", args.refresh)
        if not html:
            continue
        tid, title = topic_of(html)
        tid = tid or "0"
        title = topics.get(tid, title or "")
        for p in parse_posts(html, tid, title):
            posts.setdefault(p["post_id"], p)

    # A post counts if it names the product itself, or if it sits in a thread
    # dedicated to the product (where "it" is the obvious referent).
    MENTION = re.compile(
        r"(mindphone|mind\s*phone|מיינד\s*פאון|מיינדפאון|greentouchstore)", re.I
    )
    relevant = [
        p for p in posts.values()
        if MENTION.search(p["text"]) or TOPIC_IS_DEDICATED.search(p["topic_title"])
    ]
    relevant.sort(key=lambda p: int(p["post_id"]))

    DATA.mkdir(exist_ok=True)
    (DATA / "posts.json").write_text(
        json.dumps(relevant, ensure_ascii=False, indent=2)
    )
    (DATA / "topics.json").write_text(json.dumps(topics, ensure_ascii=False, indent=2))
    print(
        f"\nwrote {len(relevant)} relevant posts (of {len(posts)} scraped) "
        f"-> data/posts.json",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
