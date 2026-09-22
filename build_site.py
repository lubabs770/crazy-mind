#!/usr/bin/env python3
"""Render data/status.json as a kanban board.

Deliberately not a history of the product. The columns are the actual pipeline
an issue travels: an owner reports it, the maker acknowledges it, it gets
queued, it gets worked on, it ships.

Styling follows the design system published at mindphone.co (lavender ground,
Poppins with tight display tracking, glassy cards, violet glow) so the board
reads as part of the same world. It is not an official page and says so in the
masthead and the footer; none of the company's own marks are used.
"""

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
D = json.loads((ROOT / "data" / "status.json").read_text())
e = lambda s: html.escape(str(s), quote=True)

# Readers here are US-based, so dates read "Sept 15, 2026" rather than
# 2026-09-15. The ISO value still goes in the datetime attribute for machines.
MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]
SHORT = ["Jan", "Feb", "Mar", "Apr", "May", "June", "July",
         "Aug", "Sept", "Oct", "Nov", "Dec"]


def fmt_date(iso: str, long: bool = False) -> str:
    y, m, d = iso.split("-")
    return f"{(MONTHS if long else SHORT)[int(m) - 1]} {int(d)}, {y}"


def by_state(state):
    return [i for i in D["in_progress"] if i["state"] == state]


# Left to right: how far an issue has travelled.
COLUMNS = [
    {
        "key": "reports", "title": "Owner reports",
        "note": "Raised on the forum, no reply from the maker yet",
        "items": [dict(i, eta="Awaiting reply") for i in D["unacknowledged"]],
    },
    {
        "key": "ack", "title": "Acknowledged",
        "note": "Seen and confirmed, no work committed",
        "items": by_state("reported"),
    },
    {
        "key": "queued", "title": "Queued",
        "note": "Accepted, scheduled behind other work",
        "items": by_state("queued"),
    },
    {
        "key": "active", "title": "In progress",
        "note": "Actively being fixed right now",
        "items": by_state("active"),
    },
    {
        "key": "shipped", "title": "Shipped",
        "note": "Out to devices, from the maker's release notes",
        "items": D["shipped"],
    },
]


def card(i, key):
    badge = '<span class="auto" title="Written by the classifier, not yet checked by a person">unreviewed</span>' if i.get("review") else ""
    if key == "shipped":
        ticks = "".join(f"<li>{e(x)}</li>" for x in i["items"])
        return f'''<article class="card">
  <header class="card__top">{badge}<time datetime="{e(i['date'])}">{e(fmt_date(i['date']))}</time></header>
  <h3>{e(i['title'])}</h3>
  <ul class="ticks">{ticks}</ul>
  <footer class="card__foot">
    <a class="perma" href="{e(i['url'])}" target="_blank" rel="noopener">Release notes<span aria-hidden="true">&#8599;</span></a>
  </footer>
</article>'''
    return f'''<article class="card">
  <header class="card__top">{badge}<time datetime="{e(i['date'])}">{e(fmt_date(i['date']))}</time></header>
  <h3>{e(i['title'])}</h3>
  <p>{e(i['detail'])}</p>
  <footer class="card__foot">
    <span class="eta">{e(i['eta'])}</span>
    <a class="perma" href="{e(i['url'])}" target="_blank" rel="noopener">Source<span aria-hidden="true">&#8599;</span></a>
  </footer>
</article>'''


HINT_JS = """<script>
(function () {
  var board = document.querySelector('.board'), hint = document.getElementById('hint');
  if (!board || !hint) return;
  function sync() {
    hint.classList.toggle('is-on', board.scrollWidth - board.clientWidth > 4);
  }
  sync();
  addEventListener('resize', sync);
})();
</script>"""


def board():
    out = []
    for c in COLUMNS:
        cards = "\n".join(card(i, c["key"]) for i in c["items"])
        out.append(f'''<section class="col col--{e(c['key'])}" aria-labelledby="h-{e(c['key'])}">
  <header class="col__head">
    <h2 id="h-{e(c['key'])}">{e(c['title'])}<span class="count">{len(c['items'])}</span></h2>
    <p class="col__note">{e(c['note'])}</p>
  </header>
  <div class="col__cards">
{cards}
  </div>
</section>''')
    return "\n".join(out)


page = f'''<title>MindPhone Status Board</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=swap">
<style>
:root {{
  --lav-50:#f5f1ff; --lav-100:#eae3ff; --lav-200:#d8cdff; --lav-300:#baa7ef;
  --lav-400:#9c84dc; --lav-500:#7c5fc9; --lav-600:#5f42a8; --lav-700:#422a7f;
  --lav-800:#271957; --lav-900:#140a33;

  --ground:#f4efff;
  --wash-1:rgba(186,167,239,.55); --wash-2:rgba(216,205,255,.5);
  --card:rgba(255,255,255,.72); --card-strong:rgba(255,255,255,.82);
  --lane:rgba(255,255,255,.34);
  --ink:#130b2b; --ink-2:rgba(19,11,43,.82); --ink-3:rgba(19,11,43,.62); --ink-4:rgba(19,11,43,.46);
  --line:rgba(124,95,201,.18); --line-2:rgba(124,95,201,.3);
  --accent:#7c5fc9; --accent-deep:#422a7f; --accent-soft:rgba(124,95,201,.14);
  --grad-text:linear-gradient(92deg,#4b2fa0 0%,#7c5fc9 45%,#baa7ef 100%);
  --glow:0 30px 80px -20px rgba(99,71,196,.45);
  --glow-sm:0 18px 40px -24px rgba(66,42,127,.35);
  --live:#0bb44a;
  --warn:#a8631c; --warn-soft:rgba(214,146,58,.18); --crit:#b8355c;
  --stage-1:rgba(19,11,43,.34); --stage-2:#a8631c; --stage-3:#7c5fc9;
  --stage-4:#b8355c; --stage-5:#0bb44a;
  --blur:blur(10px);
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --ground:#140a33;
    --wash-1:rgba(46,25,104,.85); --wash-2:rgba(66,42,127,.55);
    --card:rgba(255,255,255,.06); --card-strong:rgba(255,255,255,.09);
    --lane:rgba(255,255,255,.03);
    --ink:#f3efff; --ink-2:rgba(243,239,255,.8); --ink-3:rgba(243,239,255,.6); --ink-4:rgba(243,239,255,.44);
    --line:rgba(186,167,239,.2); --line-2:rgba(186,167,239,.32);
    --accent:#baa7ef; --accent-deep:#d8cdff; --accent-soft:rgba(156,132,220,.2);
    --grad-text:linear-gradient(92deg,#ffffff 0%,#d8cdff 55%,#baa7ef 100%);
    --glow:0 30px 80px -20px rgba(0,0,0,.6);
    --glow-sm:0 18px 40px -24px rgba(0,0,0,.7);
    --live:#3ddb7c;
    --warn:#e0b060; --warn-soft:rgba(224,176,96,.16); --crit:#f2879f;
    --stage-1:rgba(243,239,255,.34); --stage-2:#e0b060; --stage-3:#baa7ef;
    --stage-4:#f2879f; --stage-5:#3ddb7c;
  }}
}}
:root[data-theme="dark"] {{
  --ground:#140a33;
  --wash-1:rgba(46,25,104,.85); --wash-2:rgba(66,42,127,.55);
  --card:rgba(255,255,255,.06); --card-strong:rgba(255,255,255,.09);
  --lane:rgba(255,255,255,.03);
  --ink:#f3efff; --ink-2:rgba(243,239,255,.8); --ink-3:rgba(243,239,255,.6); --ink-4:rgba(243,239,255,.44);
  --line:rgba(186,167,239,.2); --line-2:rgba(186,167,239,.32);
  --accent:#baa7ef; --accent-deep:#d8cdff; --accent-soft:rgba(156,132,220,.2);
  --grad-text:linear-gradient(92deg,#ffffff 0%,#d8cdff 55%,#baa7ef 100%);
  --glow:0 30px 80px -20px rgba(0,0,0,.6);
  --glow-sm:0 18px 40px -24px rgba(0,0,0,.7);
  --live:#3ddb7c;
  --warn:#e0b060; --warn-soft:rgba(224,176,96,.16); --crit:#f2879f;
  --stage-1:rgba(243,239,255,.34); --stage-2:#e0b060; --stage-3:#baa7ef;
  --stage-4:#f2879f; --stage-5:#3ddb7c;
}}

* {{ box-sizing:border-box; }}
body {{
  margin:0; color:var(--ink); background:var(--ground);
  background-image:
    radial-gradient(1100px 620px at 82% -8%, var(--wash-1), transparent 62%),
    radial-gradient(900px 520px at -10% 8%, var(--wash-2), transparent 60%);
  background-attachment:fixed;
  font-family:Poppins, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  font-size:16px; line-height:1.55; -webkit-font-smoothing:antialiased;
}}
a {{ color:var(--accent); }}
a:focus-visible {{ outline:2px solid var(--accent); outline-offset:3px; border-radius:6px; }}
time {{ font-variant-numeric:tabular-nums; }}

/* ---------- masthead ---------- */
.top {{ max-width:1500px; margin:0 auto; padding:52px 28px 0; }}
.live {{ display:inline-flex; align-items:center; gap:10px; padding:8px 16px 8px 12px;
  border-radius:999px; background:var(--card-strong); border:1px solid var(--line);
  backdrop-filter:var(--blur); -webkit-backdrop-filter:var(--blur);
  box-shadow:var(--glow-sm); font-size:12px; font-weight:600; letter-spacing:.1em;
  text-transform:uppercase; color:var(--ink-3); }}
.live b {{ color:var(--ink-2); font-weight:700; }}
.dot {{ width:8px; height:8px; border-radius:50%; background:var(--live); flex:none;
  box-shadow:0 0 0 4px color-mix(in srgb, var(--live) 22%, transparent); }}
h1 {{ font-size:clamp(46px,8vw,96px); line-height:.93; margin:20px 0 0; font-weight:700;
  letter-spacing:-.045em; text-wrap:balance;
  background:var(--grad-text); -webkit-background-clip:text; background-clip:text;
  color:transparent; }}
.tagline {{ font-size:clamp(17px,2vw,21px); color:var(--ink-3); margin:16px 0 0;
  max-width:46ch; font-weight:400; }}
.status {{ margin-top:30px; padding:20px 24px; border-radius:22px;
  background:var(--card); border:1px solid var(--line);
  backdrop-filter:var(--blur); -webkit-backdrop-filter:var(--blur);
  box-shadow:var(--glow); display:flex; flex-wrap:wrap; gap:12px 24px; align-items:center; }}
.status__h {{ font-weight:700; font-size:18px; letter-spacing:-.015em; }}
.status__d {{ color:var(--ink-3); font-size:15px; flex:1 1 320px; min-width:0; }}
.asof {{ font-size:12px; color:var(--ink-4); white-space:nowrap; font-weight:500; }}
.facts {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(195px,1fr));
  gap:14px; margin-top:14px; }}
.fact {{ background:var(--card); border:1px solid var(--line); border-radius:18px;
  padding:16px 20px; backdrop-filter:var(--blur); -webkit-backdrop-filter:var(--blur);
  box-shadow:var(--glow-sm); }}
.fact__k {{ font-size:10.5px; letter-spacing:.12em; text-transform:uppercase;
  color:var(--ink-4); margin:0; font-weight:600; }}
.fact__v {{ font-size:25px; font-weight:700; letter-spacing:-.035em; margin:5px 0 3px; }}
.fact__n {{ font-size:13px; color:var(--ink-3); margin:0; line-height:1.45; }}

/* ---------- board ---------- */
.board-wrap {{ max-width:1500px; margin:56px auto 0; padding:0 28px; }}
.board-hint {{ font-size:12.5px; color:var(--ink-4); margin:0 0 14px; font-weight:500; display:none; }}
.board-hint.is-on {{ display:block; }}
.board {{
  display:grid; grid-auto-flow:column; grid-auto-columns:minmax(268px,1fr);
  gap:16px; align-items:start; overflow-x:auto; overscroll-behavior-x:contain;
  padding-bottom:14px; scroll-snap-type:x proximity;
}}
.col {{ display:flex; flex-direction:column; min-width:0; scroll-snap-align:start;
  background:var(--lane); border:1px solid var(--line); border-radius:22px; padding:16px 14px; }}
.col__head {{ padding:2px 6px 14px; border-bottom:1px solid var(--line); margin-bottom:14px;
  position:relative; }}
.col__head::after {{ content:""; position:absolute; left:6px; bottom:-1px; width:44px; height:2px;
  border-radius:2px; background:var(--stage-1); }}
.col--ack .col__head::after {{ background:var(--stage-2); }}
.col--queued .col__head::after {{ background:var(--stage-3); }}
.col--active .col__head::after {{ background:var(--stage-4); }}
.col--shipped .col__head::after {{ background:var(--stage-5); }}
.col h2 {{ font-size:13px; font-weight:700; letter-spacing:.14em; text-transform:uppercase;
  color:var(--ink-2); margin:0; display:flex; align-items:center; gap:9px; }}
.count {{ font-size:11px; font-weight:700; letter-spacing:0; color:var(--ink-3);
  background:var(--accent-soft); border-radius:999px; padding:2px 9px; }}
.col__note {{ font-size:12.5px; color:var(--ink-4); margin:7px 0 0; line-height:1.45; }}
.col__cards {{ display:flex; flex-direction:column; gap:12px; }}

.card {{ background:var(--card); border:1px solid var(--line); border-radius:18px;
  padding:16px 18px; backdrop-filter:var(--blur); -webkit-backdrop-filter:var(--blur);
  box-shadow:var(--glow-sm); display:flex; flex-direction:column;
  transition:transform .2s ease, box-shadow .2s ease; }}
.card:hover {{ transform:translateY(-2px); box-shadow:var(--glow); }}
@media (prefers-reduced-motion:reduce) {{ .card {{ transition:none; }} .card:hover {{ transform:none; }} }}
.card__top {{ display:flex; justify-content:space-between; align-items:center;
  gap:8px; margin-bottom:7px; min-height:16px; }}
.card__top time {{ margin-left:auto; }}
.auto {{ font-size:9.5px; font-weight:700; letter-spacing:.09em; text-transform:uppercase;
  color:var(--warn); background:var(--warn-soft); border-radius:999px; padding:2px 8px; }}
.card__top time {{ font-size:11px; color:var(--ink-4); font-weight:500; }}
.card h3 {{ margin:0 0 8px; font-size:16px; font-weight:600; letter-spacing:-.02em;
  line-height:1.32; text-wrap:balance; }}
.card p {{ margin:0 0 14px; color:var(--ink-3); font-size:14px; line-height:1.55; }}
.card__foot {{ margin-top:auto; display:flex; justify-content:space-between;
  align-items:baseline; gap:10px; border-top:1px solid var(--line); padding-top:11px; }}
.eta {{ font-size:12.5px; font-weight:600; color:var(--ink-2); }}
.perma {{ font-size:11px; font-weight:600; text-decoration:none; white-space:nowrap;
  border-bottom:1px solid var(--line-2); padding-bottom:2px; }}
.perma span {{ margin-left:3px; }}
.ticks {{ list-style:none; margin:0 0 14px; padding:0; display:flex; flex-direction:column; gap:7px; }}
.ticks li {{ position:relative; padding-left:22px; color:var(--ink-3); font-size:13.5px; line-height:1.5; }}
.ticks li::before {{ content:""; position:absolute; left:2px; top:.5em; width:9px; height:5px;
  border-left:2px solid var(--live); border-bottom:2px solid var(--live);
  transform:rotate(-45deg); border-radius:1px; }}

@media (max-width:900px) {{
  .board {{ grid-auto-flow:row; grid-auto-columns:auto; scroll-snap-type:none; overflow-x:visible; }}
  .board-hint {{ display:none; }}
}}

/* ---------- footer blocks ---------- */
.tail {{ max-width:1500px; margin:64px auto 0; padding:0 28px 96px;
  display:grid; grid-template-columns:1fr 1fr; gap:24px; align-items:start; }}
@media (max-width:820px) {{ .tail {{ grid-template-columns:1fr; }} }}
.panel {{ background:var(--card); border:1px solid var(--line); border-radius:22px;
  padding:22px 24px; backdrop-filter:var(--blur); -webkit-backdrop-filter:var(--blur);
  box-shadow:var(--glow-sm); }}
.panel h2 {{ font-size:13px; font-weight:700; letter-spacing:.14em; text-transform:uppercase;
  color:var(--ink-4); margin:0 0 12px; }}
.panel ol {{ margin:0 0 14px; padding-left:20px; color:var(--ink-3); font-size:14.5px; }}
.panel li {{ margin-bottom:9px; }}
.panel p {{ margin:0; font-size:13.5px; color:var(--ink-4); }}
.note {{ background:var(--accent-soft); border:1px solid var(--line); border-radius:18px;
  padding:18px 20px; color:var(--ink-3); font-size:13.5px; }}
.note strong {{ color:var(--ink-2); }}
.note + .note {{ margin-top:14px; }}
</style>

<header class="top">
  <span class="live"><span class="dot"></span>Unofficial MindPhone tracker &middot; <b>translated from iVelt</b></span>
  <h1>Status Board.</h1>
  <p class="tagline">Every open issue on the Phone 2 Pro, tracked from the owner who first reported it to the update that fixed it.</p>

  <div class="status">
    <span class="status__h">{e(D['status']['headline'])}</span>
    <span class="status__d">{e(D['status']['detail'])}</span>
    <span class="asof">as of {e(fmt_date(D['as_of'], long=True))}</span>
  </div>

  <div class="facts">
    {''.join(f"""<div class="fact"><p class="fact__k">{e(f['k'])}</p>
      <p class="fact__v">{e(f['v'])}</p><p class="fact__n">{e(f['note'])}</p></div>""" for f in D['facts'])}
  </div>
</header>

<div class="board-wrap">
  <p class="board-hint" id="hint">Scroll sideways for later stages &rarr;</p>
  <div class="board">
{board()}
  </div>
</div>

<div class="tail">
  <div class="panel">
    <h2>Installing an update</h2>
    <ol>{''.join(f"<li>{e(s)}</li>" for s in D['how_to_update']['steps'])}</ol>
    <p>{e(D['how_to_update']['stuck'])}</p>
  </div>
  <div>
    <p class="note">{e(D['calendar_note'])}</p>
    <p class="note"><strong>About this page.</strong> An independent tracker, not affiliated with MindPhone, Greentouch or Ari Greenfield, and not an official source. Every card is summarised and translated from public posts on ivelt.com and links back to the original. Anything short of the Shipped column is a plan, not a guarantee. Yiddish-to-English wording is mine, so follow a source link for the exact words.</p>
  </div>
</div>

{HINT_JS}'''

out = ROOT / "site"
out.mkdir(exist_ok=True)
(out / "index.html").write_text(page, encoding="ascii", errors="xmlcharrefreplace")
print(f"wrote {out/'index.html'} ({len(page):,} bytes)")
for c in COLUMNS:
    print(f"  {c['title']:<16} {len(c['items'])}")
