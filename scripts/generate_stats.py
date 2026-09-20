#!/usr/bin/env python3
"""Builds assets/stats.svg (animated GitHub activity card) from real contribution data.
Usage: GH_TOKEN=... LOGIN=username python scripts/generate_stats.py
       python scripts/generate_stats.py --placeholder   (empty card, no network)
"""
import json, os, sys, math, urllib.request
from datetime import date, datetime, timedelta, timezone

OUT = os.path.join(os.path.dirname(__file__), "..", "assets", "stats.svg")
MONO = "font-family:'JetBrains Mono','SFMono-Regular',Consolas,'Courier New',monospace"
SANS = "font-family:'Segoe UI','Helvetica Neue',Arial,sans-serif"

def gql(token, query, variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json", "User-Agent": "stats-svg"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.load(r)
    if "errors" in d:
        raise RuntimeError(d["errors"])
    return d["data"]

def fetch(token, login):
    created = gql(token, "query($l:String!){user(login:$l){createdAt}}", {"l": login})["user"]["createdAt"]
    start_year = int(created[:4])
    now = datetime.now(timezone.utc)
    q = """query($l:String!,$f:DateTime!,$t:DateTime!){user(login:$l){contributionsCollection(from:$f,to:$t){
      contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}}}}"""
    days, total = {}, 0
    for y in range(start_year, now.year + 1):
        f = f"{y}-01-01T00:00:00Z"
        t = min(now, datetime(y, 12, 31, 23, 59, 59, tzinfo=timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
        cal = gql(token, q, {"l": login, "f": f, "t": t})["user"]["contributionsCollection"]["contributionCalendar"]
        total += cal["totalContributions"]
        for w in cal["weeks"]:
            for d in w["contributionDays"]:
                days[d["date"]] = d["contributionCount"]
    return {"days": days, "total": total, "since": start_year}

def streaks(days):
    """days: {'YYYY-MM-DD': count}. Returns (current, current_range, longest, longest_range)."""
    ds = sorted(date.fromisoformat(k) for k in days)
    longest = (0, None, None); run = 0; rs = None; prev = None
    for d in ds:
        if days[d.isoformat()] > 0:
            if prev is not None and (d - prev).days == 1 and run > 0:
                run += 1
            else:
                run, rs = 1, d
            if run > longest[0]:
                longest = (run, rs, d)
            prev = d
        else:
            run = 0; prev = d
    today = datetime.now(timezone.utc).date()
    d = today
    if days.get(d.isoformat(), 0) == 0:
        d -= timedelta(days=1)
    cur = 0; end = d
    while days.get(d.isoformat(), 0) > 0:
        cur += 1; d -= timedelta(days=1)
    cur_start = d + timedelta(days=1)
    return (cur, (cur_start, end) if cur else None, longest[0], (longest[1], longest[2]) if longest[0] else None)

def fmt(d): return d.strftime("%b %-d") if d else ""
def rng(r):
    if not r: return "no active streak"
    a, b = r
    return f"{fmt(a)} – {fmt(b)}, {b.year}" if a.year == b.year else f"{fmt(a)}, {a.year} – {fmt(b)}, {b.year}"

def render(data):
    W, H = 1000, 380
    ph = data is None
    if ph:
        total, cur, cur_r, lng, lng_r, since, days = "—", "—", "syncing · updates daily", "—", "syncing · updates daily", None, {}
        cur_n, lng_n = 0, 1
    else:
        days = data["days"]
        cur_n, cur_r_, lng_n, lng_r_ = streaks(days)
        total = f"{data['total']:,}"; cur = str(cur_n); lng = str(lng_n)
        cur_r, lng_r, since = rng(cur_r_), rng(lng_r_), data["since"]
    prog = 0 if ph else min(cur_n / max(lng_n, 1), 1)
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="GitHub activity: {total} contributions, current streak {cur} days, longest streak {lng} days">',
    '<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#060814"/><stop offset="1" stop-color="#0b1030"/></linearGradient>',
    '<pattern id="dots" width="20" height="20" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="0.9" fill="#3a4690" opacity="0.35"/></pattern>',
    '<filter id="g" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="2.5" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>',
    f'<clipPath id="frame"><rect width="{W}" height="{H}" rx="16"/></clipPath>',
    '<linearGradient id="shine" x1="0" x2="1"><stop offset="0" stop-color="#9ff4ff" stop-opacity="0"/><stop offset="0.5" stop-color="#9ff4ff" stop-opacity="0.35"/><stop offset="1" stop-color="#9ff4ff" stop-opacity="0"/></linearGradient>',
    '<clipPath id="hm"><rect x="52" y="236" width="896" height="112"/></clipPath></defs>',
    f'<g clip-path="url(#frame)"><rect width="{W}" height="{H}" fill="url(#bg)"/><rect width="{W}" height="{H}" fill="url(#dots)"/>']
    # heading + divider
    o.append(f'<text x="60" y="52" font-size="26" font-weight="800" fill="#eef3ff" style="{SANS}">GitHub activity</text>')
    o.append('<line x1="60" y1="70" x2="940" y2="70" stroke="#2e3a80" stroke-width="1.5"/>')
    o.append('<circle r="3.5" cy="70" fill="#9ff4ff" filter="url(#g)"><animate attributeName="cx" values="60;940;60" dur="6s" repeatCount="indefinite"/></circle>')
    # three stat blocks
    def label(x, t): return f'<text x="{x}" y="112" text-anchor="middle" font-size="12" fill="#7f8fd6" letter-spacing="1" style="{MONO}">{t}</text>'
    def big(x, v, delay): return (f'<text x="{x}" y="176" text-anchor="middle" font-size="46" font-weight="800" fill="#eef3ff" opacity="0" style="{SANS}">{v}'
        f'<animate attributeName="opacity" values="0;1" dur="0.8s" begin="{delay}s" fill="freeze"/></text>')
    def sub(x, t): return f'<text x="{x}" y="204" text-anchor="middle" font-size="12" fill="#5f6fb5" style="{MONO}">{t}</text>'
    o.append(label(200, "total contributions") + big(200, total, 0.1) + sub(200, f"since {since}" if since else "syncing · updates daily"))
    # streak ring
    cx, cy, r = 500, 160, 62
    o.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#1a2350" stroke-width="7"/>')
    o.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#9ff4ff" stroke-width="7" stroke-linecap="round" pathLength="100" stroke-dasharray="100" stroke-dashoffset="100" transform="rotate(-90 {cx} {cy})" filter="url(#g)">'
             f'<animate attributeName="stroke-dashoffset" values="100;{100 - prog * 100:.1f}" dur="1.8s" fill="freeze" calcMode="spline" keyTimes="0;1" keySplines="0.2 0.8 0.2 1"/></circle>')
    o.append(f'<circle cx="{cx}" cy="{cy}" r="{r + 12}" fill="none" stroke="#7b5cff" stroke-width="1.2" stroke-dasharray="3 9" opacity="0.7"><animateTransform attributeName="transform" type="rotate" from="0 {cx} {cy}" to="360 {cx} {cy}" dur="20s" repeatCount="indefinite"/></circle>')
    o.append(f'<text x="{cx}" y="{cy + 4}" text-anchor="middle" font-size="42" font-weight="800" fill="#ffffff" style="{SANS}">{cur}</text>')
    o.append(f'<text x="{cx}" y="{cy + 26}" text-anchor="middle" font-size="11" fill="#7f8fd6" style="{MONO}">day streak</text>')
    o.append(label(800, "longest streak") + big(800, lng, 0.4) + sub(800, lng_r))
    # heatmap (last 53 weeks)
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=(today.weekday() + 1) % 7) - timedelta(weeks=52)
    vals = [days.get((start + timedelta(days=i)).isoformat(), 0) for i in range(53 * 7)]
    mx = max(vals) if vals and max(vals) > 0 else 1
    cols = ["#131a3d", "#1d3d7a", "#2b6fb0", "#4fb3d9", "#9ff4ff"]
    o.append('<g clip-path="url(#hm)">')
    for i, v in enumerate(vals):
        wk, dy = divmod(i, 7)
        d = start + timedelta(days=i)
        if d > today: continue
        lvl = 0 if v == 0 else max(1, math.ceil(v / mx * 4))
        o.append(f'<rect x="{52 + wk * 17}" y="{238 + dy * 15.5:.1f}" width="13" height="13" rx="3" fill="{cols[lvl]}"/>')
    o.append('<rect x="-120" y="236" width="120" height="112" fill="url(#shine)"><animate attributeName="x" values="-120;1000" dur="5s" repeatCount="indefinite"/></rect></g>')
    o.append(f'<text x="948" y="366" text-anchor="end" font-size="11" fill="#5f6fb5" style="{MONO}">last 12 months</text>')
    o.append('</g>')
    o.append(f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="16" fill="none" stroke="#2e3a80" stroke-width="1.5"/></svg>')
    return "\n".join(x for x in o if x)

if __name__ == "__main__":
    if "--placeholder" in sys.argv:
        svg = render(None)
    else:
        svg = render(fetch(os.environ["GH_TOKEN"], os.environ.get("LOGIN", "sarthakwadhwa2005")))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w").write(svg)
    print("wrote", os.path.abspath(OUT))
