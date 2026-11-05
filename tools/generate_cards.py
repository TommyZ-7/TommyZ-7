#!/usr/bin/env python3
"""Generate profile cards (SVG) in the header theme, from live GitHub data via gh."""
import json, subprocess, sys, math
from datetime import datetime, timedelta, timezone

USER = "TommyZ-7"
OUT = sys.argv[1] if len(sys.argv) > 1 else "assets"

def gh(path, jq=None):
    cmd = ["gh", "api", path]
    if jq:
        cmd += ["--jq", jq]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"gh api {path}: {r.stderr.strip()}")
    return r.stdout.strip()

def ghj(path):
    return json.loads(gh(path))

# ---------- fetch data ----------
user = ghj(f"users/{USER}")
repos = ghj(f"users/{USER}/repos?per_page=100")
own = [r for r in repos]
total_stars = sum(r["stargazers_count"] for r in own)
total_forks = sum(r["forks_count"] for r in own)
joined = user["created_at"][:4]

lang_bytes = {}
commit_lang = {}
for r in own:
    if r.get("fork"):
        continue  # language stats follow github-readme-stats convention: own repos only
    name = r["name"]
    langs = ghj(f"repos/{USER}/{name}/languages")
    for k, v in langs.items():
        lang_bytes[k] = lang_bytes.get(k, 0) + v
    # commit count via Link header (per_page=1)
    out = subprocess.run(["gh", "api", "-i", f"repos/{USER}/{name}/commits?per_page=1"],
                         capture_output=True, text=True).stdout
    n = 1
    for line in out.splitlines():
        if line.lower().startswith("link:") and 'rel="last"' in line:
            try:
                n = int(line.split("page=")[-1].split(">")[0])
            except Exception:
                pass
    if r.get("language"):
        commit_lang[r["language"]] = commit_lang.get(r["language"], 0) + n

def top(data, n=5):
    items = sorted(data.items(), key=lambda kv: -kv[1])
    total = sum(data.values()) or 1
    head, rest = items[:n], items[n:]
    out = [(k, v / total * 100) for k, v in head]
    if rest:
        out.append(("Other", sum(v for _, v in rest) / total * 100))
    return out

repo_langs = top(lang_bytes)
commit_langs = top(commit_lang)

one_year_ago = (datetime.now(timezone.utc) - timedelta(days=365)).strftime("%Y-%m-%d")
commits_1y = gh(f"search/commits?q=author:{USER}+author-date:>={one_year_ago}", ".total_count")
prs = gh(f"search/issues?q=author:{USER}+type:pr", ".total_count")
issues = gh(f"search/issues?q=author:{USER}+type:issue", ".total_count")

print(json.dumps({
    "stars": total_stars, "forks": total_forks, "repos": user["public_repos"],
    "followers": user["followers"], "following": user["following"], "joined": joined,
    "commits_1y": commits_1y, "prs": prs, "issues": issues,
    "repo_langs": repo_langs, "commit_langs": commit_langs,
}, ensure_ascii=False, indent=1))

# ---------- svg helpers ----------
LANG_COLORS = {
    "Rust": "#dea584", "TypeScript": "#3178c6", "C++": "#f34b7d", "C": "#a8b9cc",
    "Python": "#3572A5", "HTML": "#e34c26", "Shell": "#89e051", "JavaScript": "#f1e05a",
    "CSS": "#663399", "Vue": "#41b883", "Other": "#565f89",
}
CSS = """
    .r { opacity: 0; animation: rise .6s ease-out forwards; }
    @keyframes rise { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
    .bar { transform-box: fill-box; transform-origin: left center; transform: scaleX(0); animation: grow .9s ease-out forwards; }
    @keyframes grow { to { transform: scaleX(1); } }
    text { font-family: 'Segoe UI', 'Hiragino Kaku Gothic ProN', 'Noto Sans CJK JP', sans-serif; }
    .title { font-size: 12px; letter-spacing: 2.5px; fill: #565f89; font-weight: 700; }
    .label { font-size: 13px; fill: #9aa5ce; }
    .pct { font-size: 12.5px; fill: #565f89; }
    .num { font-size: 30px; font-weight: 700; fill: #c0caf5; }
    .cap { font-size: 11.5px; letter-spacing: 1.5px; fill: #565f89; }
"""
BG = """
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#1a1b27"/>
      <stop offset="1" stop-color="#24283b"/>
    </linearGradient>
  </defs>
"""

def delay(ms):
    return f'style="animation-delay:{ms}ms"'

def lang_card(fname, title, data, w=392):
    rows = []
    y = 58
    for i, (name, pct) in enumerate(data):
        color = LANG_COLORS.get(name, "#7aa2f7")
        rows.append(f"""
  <g class="r" {delay(120 + i * 110)}>
    <circle cx="30" cy="{y - 4}" r="5" fill="{color}"/>
    <text class="label" x="46" y="{y}">{name}</text>
    <text class="pct" x="{w - 24}" y="{y}" text-anchor="end">{pct:.1f}%</text>
    <rect x="24" y="{y + 8}" width="{w - 48}" height="7" rx="3.5" fill="#292e42"/>
    <rect class="bar" {delay(260 + i * 110)} x="24" y="{y + 8}" width="{(w - 48) * pct / 100:.1f}" height="7" rx="3.5" fill="{color}"/>
  </g>""")
        y += 42
    h = y - 42 + 34
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="{title}">
{BG}  <style>{CSS}  </style>
  <rect width="{w}" height="{h}" rx="12" fill="url(#bg)"/>
  <text class="title r" {delay(0)} x="24" y="32">{title}</text>
{''.join(rows)}
</svg>
"""
    open(f"{OUT}/{fname}", "w").write(svg)
    print("wrote", fname, f"{w}x{h}")

def stat_block(x, w, num, cap, d):
    return f"""
  <g class="r" {delay(d)} text-anchor="middle">
    <text class="num" x="{x + w / 2}" y="76">{num}</text>
    <text class="cap" x="{x + w / 2}" y="102">{cap}</text>
  </g>"""

# ---------- profile details (800 wide) ----------
facts = [
    (str(user["public_repos"]), "REPOSITORIES"),
    (str(total_stars), "STARS"),
    (str(total_forks), "FORKS"),
    (str(user["followers"]), "FOLLOWERS"),
    (str(user["following"]), "FOLLOWING"),
]
blocks = "".join(stat_block(24 + i * 152, 140, n, c, 150 + i * 100) for i, (n, c) in enumerate(facts))
svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 150" width="800" height="150" role="img" aria-label="Profile details">
{BG}  <style>{CSS}  </style>
  <rect width="800" height="150" rx="12" fill="url(#bg)"/>
  <text class="title r" {delay(0)} x="24" y="32">PROFILE — GITHUB SINCE {joined}</text>
{blocks}
</svg>
"""
open(f"{OUT}/profile-details.svg", "w").write(svg)
print("wrote profile-details.svg 800x150")

# ---------- language cards ----------
lang_card("repos-per-language.svg", "REPOS PER LANGUAGE", repo_langs)
lang_card("most-commit-language.svg", "COMMITS PER LANGUAGE", commit_langs)

# ---------- stats (800 wide) ----------
stats = [
    (str(total_stars), "TOTAL STARS"),
    (str(commits_1y), "COMMITS (1Y)"),
    (str(prs), "PULL REQUESTS"),
    (str(issues), "ISSUES"),
    (str(user["public_repos"]), "REPOSITORIES"),
]
blocks = "".join(stat_block(24 + i * 152, 140, n, c, 150 + i * 100) for i, (n, c) in enumerate(stats))
svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 150" width="800" height="150" role="img" aria-label="Stats">
{BG}  <style>{CSS}  </style>
  <rect width="800" height="150" rx="12" fill="url(#bg)"/>
  <text class="title r" {delay(0)} x="24" y="32">STATS</text>
{blocks}
</svg>
"""
open(f"{OUT}/stats.svg", "w").write(svg)
print("wrote stats.svg 800x150")
