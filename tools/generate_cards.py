#!/usr/bin/env python3
"""Generate profile cards (SVG) in the header theme, from live GitHub data via gh.

Scope: all repos owned by the user (public + private), forks excluded.
Language bytes are aggregated per-file from git trees with vendored paths
(node_modules, venv, ...) excluded, so dependency trees do not distort ratios.
"""
import json, subprocess, sys

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

EXT_LANG = {
    ".py": "Python", ".rs": "Rust", ".ts": "TypeScript", ".tsx": "TypeScript",
    ".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript",
    ".c": "C", ".h": "C", ".cpp": "C++", ".hpp": "C++", ".cc": "C++", ".cxx": "C++",
    ".css": "CSS", ".scss": "CSS", ".html": "HTML", ".htm": "HTML",
    ".sh": "Shell", ".bash": "Shell", ".ps1": "PowerShell", ".bat": "Batchfile",
    ".java": "Java", ".go": "Go", ".rb": "Ruby", ".php": "PHP", ".vue": "Vue",
    ".svelte": "Svelte", ".kt": "Kotlin", ".swift": "Swift", ".scala": "Scala",
    ".lua": "Lua", ".pl": "Perl", ".r": "R", ".sql": "SQL", ".toml": "TOML",
}
VENDOR_SEGMENTS = {"node_modules", "venv", ".venv", "vendor", "third_party", ".next",
                   "dist", ".git", "__pycache__", "site-packages"}

def repo_languages(owner, name, branch):
    """Per-file language byte sums with vendored paths excluded."""
    try:
        tree = ghj(f"repos/{owner}/{name}/git/trees/{branch}?recursive=1")
    except Exception:
        return {}
    sums = {}
    for node in tree.get("tree", []):
        if node.get("type") != "blob":
            continue
        path = node["path"]
        if any(seg in VENDOR_SEGMENTS for seg in path.split("/")):
            continue
        dot = path.rfind(".")
        if dot < 0:
            continue
        lang = EXT_LANG.get(path[dot:].lower())
        if lang:
            sums[lang] = sums.get(lang, 0) + node.get("size", 0)
    return sums

def commit_count(owner, name):
    out = subprocess.run(["gh", "api", "-i", f"repos/{owner}/{name}/commits?per_page=1"],
                         capture_output=True, text=True).stdout
    for line in out.splitlines():
        if line.lower().startswith("link:") and 'rel="last"' in line:
            try:
                return int(line.split("page=")[-1].split(">")[0])
            except Exception:
                pass
    return 1

# ---------- fetch data ----------
user = ghj(f"users/{USER}")
auth = ghj("user")
repos = ghj("user/repos?type=owner&per_page=100")
total_repos = len(repos)
total_stars = sum(r["stargazers_count"] for r in repos if not r["fork"])
total_forks = sum(r["forks_count"] for r in repos if not r["fork"])
joined = user["created_at"][:4]

lang_bytes = {}
commit_lang = {}
for r in repos:
    if r["fork"]:
        continue
    owner, name = r["owner"]["login"], r["name"]
    langs = repo_languages(owner, name, r["default_branch"])
    for k, v in langs.items():
        lang_bytes[k] = lang_bytes.get(k, 0) + v
    if langs:
        primary = max(langs.items(), key=lambda kv: kv[1])[0]
        commit_lang[primary] = commit_lang.get(primary, 0) + commit_count(owner, name)

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

from datetime import datetime, timedelta, timezone
one_year_ago = (datetime.now(timezone.utc) - timedelta(days=365)).strftime("%Y-%m-%d")
commits_1y = gh(f"search/commits?q=author:{USER}+author-date:>={one_year_ago}", ".total_count")
prs = gh(f"search/issues?q=author:{USER}+type:pr", ".total_count")
issues = gh(f"search/issues?q=author:{USER}+type:issue", ".total_count")

print(json.dumps({
    "stars": total_stars, "forks": total_forks, "repos": total_repos,
    "followers": user["followers"], "following": user["following"], "joined": joined,
    "commits_1y": commits_1y, "prs": prs, "issues": issues,
    "repo_langs": repo_langs, "commit_langs": commit_langs,
}, ensure_ascii=False, indent=1))

# ---------- svg helpers ----------
LANG_COLORS = {
    "Rust": "#dea584", "TypeScript": "#3178c6", "C++": "#f34b7d", "C": "#a8b9cc",
    "Python": "#3572A5", "HTML": "#e34c26", "Shell": "#89e051", "JavaScript": "#f1e05a",
    "CSS": "#663399", "Vue": "#41b883", "Other": "#565f89", "PowerShell": "#5391FE",
    "Batchfile": "#C1F12E", "Go": "#00ADD8", "Java": "#b07219",
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
    (str(total_repos), "REPOSITORIES"),
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
open(f"{OUT}/card-profile.svg", "w").write(svg)
print("wrote card-profile.svg 800x150")

# ---------- language cards ----------
lang_card("card-languages.svg", "REPOS PER LANGUAGE", repo_langs)
lang_card("card-commit-languages.svg", "COMMITS PER LANGUAGE", commit_langs)

# ---------- stats (800 wide) ----------
stats = [
    (str(total_stars), "TOTAL STARS"),
    (str(commits_1y), "COMMITS (1Y)"),
    (str(prs), "PULL REQUESTS"),
    (str(issues), "ISSUES"),
    (str(total_repos), "REPOSITORIES"),
]
blocks = "".join(stat_block(24 + i * 152, 140, n, c, 150 + i * 100) for i, (n, c) in enumerate(stats))
svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 150" width="800" height="150" role="img" aria-label="Stats">
{BG}  <style>{CSS}  </style>
  <rect width="800" height="150" rx="12" fill="url(#bg)"/>
  <text class="title r" {delay(0)} x="24" y="32">STATS</text>
{blocks}
</svg>
"""
open(f"{OUT}/card-stats.svg", "w").write(svg)
print("wrote card-stats.svg 800x150")
