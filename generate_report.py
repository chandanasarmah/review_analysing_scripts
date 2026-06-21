"""
generate_report.py

Reads all output files and produces a single, self-contained, beautiful
HTML report: output/report.html

Just open report.html in any browser — no server needed, data is embedded.

Usage:
    py generate_report.py
"""

import json
import html
from pathlib import Path
from collections import Counter

BASE = Path(__file__).parent
OUTPUT = BASE / "output"

INSIGHTS = OUTPUT / "insights_report.json"
CATEGORISED = OUTPUT / "reviews_categorised.json"
RESEARCH = OUTPUT / "research_compiled.json"
PARSE_LOG = OUTPUT / "parse_log.txt"
REPORT_HTML = OUTPUT / "report.html"

SOURCE_LABELS = {
    "apple_ios": "Apple iOS",
    "google_play": "Google Play",
    "reddit": "Reddit",
    "medium": "Medium",
    "substack": "Substack",
    "spotify_official": "Spotify Forum",
    "spotify_research": "Spotify Research",
}

THEME_LABELS = {
    "ads": "Ads",
    "premium_upsell": "Premium Upsell",
    "shuffle_repetition": "Shuffle / Repeat",
    "recommendation_quality": "Recommendation Quality",
    "music_discovery": "Music Discovery",
    "app_performance": "App Performance",
    "personalization_overreach": "Personalization Overreach",
    "missing_features": "Missing Features",
    "positive": "Positive Feedback",
}

SEGMENT_LABELS = {
    "free_tier_user": "Free Tier User",
    "premium_user": "Premium User",
    "power_listener": "Power Listener",
    "casual_user": "Casual User",
    "unknown": "Unclassified",
}


def esc(s):
    return html.escape(str(s))


def load_json(path, default=None):
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def label(key, mapping):
    return mapping.get(key, key.replace("_", " ").title())


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

insights = load_json(INSIGHTS, {})
reviews = load_json(CATEGORISED, [])
research = load_json(RESEARCH, {})
research_articles = research.get("articles", []) if isinstance(research, dict) else []

parse_log_lines = []
if PARSE_LOG.exists():
    parse_log_lines = [l for l in PARSE_LOG.read_text(encoding="utf-8").splitlines() if l.strip()]

total_reviews = insights.get("total_reviews_analysed", len(reviews))
source_breakdown = insights.get("source_breakdown", {})
questions = insights.get("questions", [])
research_backing = insights.get("research_backing", {})

# Derived stats from categorised reviews
sentiment_counts = Counter(r.get("sentiment", "unknown") for r in reviews)
theme_counts = Counter(t for r in reviews for t in r.get("themes", []))
segment_counts = Counter(r.get("user_segment", "unknown") for r in reviews)
discovery_related = sum(1 for r in reviews if r.get("discovery_related"))
rated_reviews = [r for r in reviews if "rating" in r]
avg_rating = round(sum(r["rating"] for r in rated_reviews) / len(rated_reviews), 2) if rated_reviews else None


# ---------------------------------------------------------------------------
# HTML building blocks
# ---------------------------------------------------------------------------

def stat_card(value, label_text, sub=""):
    sub_html = f'<div class="stat-sub">{esc(sub)}</div>' if sub else ""
    return f'''<div class="stat-card">
      <div class="stat-value">{esc(value)}</div>
      <div class="stat-label">{esc(label_text)}</div>
      {sub_html}
    </div>'''


def bar_chart(counts_dict, label_map, max_items=10):
    if not counts_dict:
        return '<p class="muted">No data.</p>'
    items = sorted(counts_dict.items(), key=lambda kv: kv[1], reverse=True)[:max_items]
    top = items[0][1] if items else 1
    rows = []
    for key, val in items:
        pct = (val / top) * 100 if top else 0
        rows.append(f'''<div class="bar-row">
          <div class="bar-label">{esc(label(key, label_map))}</div>
          <div class="bar-track"><div class="bar-fill" style="width:{pct:.1f}%"></div></div>
          <div class="bar-value">{val}</div>
        </div>''')
    return '<div class="bar-chart">' + "".join(rows) + "</div>"


def quote_list(quotes):
    if not quotes:
        return '<p class="muted">No quotes.</p>'
    items = "".join(f'<li>{esc(q)}</li>' for q in quotes)
    return f'<ul class="quote-list">{items}</ul>'


def research_block(corroboration):
    if not corroboration:
        return '<p class="muted">No research sources matched this question.</p>'
    cards = []
    for c in corroboration:
        stype = label(c.get("source_type", ""), SOURCE_LABELS)
        title = esc(c.get("source_title", "Unknown"))
        url = esc(c.get("url", "#"))
        quotes = "".join(f'<li>{esc(q)}</li>' for q in c.get("supporting_quotes", []))
        cards.append(f'''<div class="research-card">
          <div class="research-head">
            <span class="badge badge-{c.get("source_type","")}">{stype}</span>
            <a href="{url}" target="_blank" rel="noopener">{title}</a>
          </div>
          <ul class="research-quotes">{quotes}</ul>
        </div>''')
    return '<div class="research-grid">' + "".join(cards) + "</div>"


# ---------------------------------------------------------------------------
# Question sections
# ---------------------------------------------------------------------------

QUESTION_EXPLAIN = {
    "Why do users struggle to discover new music?":
        "Reviews flagged as discovery-related with non-positive sentiment. The chart shows which "
        "themes appear most often in these complaints — revealing what blocks discovery.",
    "What causes repeat listening?":
        "Reviews mentioning shuffle, repeats, or 'same songs'. Broken down by platform to show where "
        "the frustration is loudest.",
    "What are the most common recommendation frustrations?":
        "Reviews about recommendation quality or over-personalization. The sentiment split shows how "
        "polarising the algorithm is, and the cross-platform flag confirms whether it's a universal pain point.",
    "Which user segments experience the most discovery challenges?":
        "Every review grouped by inferred user segment. Compares review volume and sentiment to identify "
        "which type of user is most underserved.",
}


def render_question(q, idx):
    title = q.get("question", "")
    explain = QUESTION_EXPLAIN.get(title, "")
    relevant = q.get("total_relevant_reviews", "")

    body_parts = []

    # Q1: theme frequency
    if "theme_frequency" in q:
        body_parts.append('<h4>Theme Breakdown</h4>')
        body_parts.append(bar_chart(q["theme_frequency"], THEME_LABELS))

    # Q2: by source
    if "by_source" in q:
        body_parts.append('<h4>By Platform</h4>')
        body_parts.append(bar_chart(q["by_source"], SOURCE_LABELS))

    # Q3: sentiment + cross-platform
    if "sentiment_breakdown" in q:
        body_parts.append('<h4>Sentiment Split</h4>')
        body_parts.append(bar_chart(q["sentiment_breakdown"], {}))
        if q.get("cross_platform_signal"):
            plats = ", ".join(label(p, SOURCE_LABELS) for p in q.get("platforms_with_complaint", []))
            body_parts.append(f'<div class="signal-flag">⚑ Cross-platform signal — appears on {esc(plats)}</div>')

    # Q4: segments
    if "segments" in q:
        body_parts.append('<h4>Segment Comparison</h4>')
        rows = []
        for seg, data in sorted(q["segments"].items(), key=lambda kv: kv[1]["review_count"], reverse=True):
            sent = data.get("sentiment", {})
            tot = data.get("review_count", 0)
            neg = sent.get("negative", 0)
            pos = sent.get("positive", 0)
            mix = sent.get("mixed", 0)
            top_theme = next(iter(data.get("top_themes", {})), "")
            is_worst = seg == q.get("worst_affected_segment")
            worst_tag = ' <span class="worst-tag">Most affected</span>' if is_worst else ""
            rows.append(f'''<tr class="{'worst-row' if is_worst else ''}">
              <td><strong>{esc(label(seg, SEGMENT_LABELS))}</strong>{worst_tag}</td>
              <td>{tot}</td>
              <td class="neg">{neg}</td>
              <td class="mix">{mix}</td>
              <td class="pos">{pos}</td>
              <td>{esc(label(top_theme, THEME_LABELS))}</td>
            </tr>''')
        body_parts.append(f'''<table class="seg-table">
          <thead><tr><th>Segment</th><th>Reviews</th><th>Neg</th><th>Mixed</th><th>Pos</th><th>Top Theme</th></tr></thead>
          <tbody>{"".join(rows)}</tbody>
        </table>''')

    # Quotes (top_quotes or evidence_quotes)
    quotes = q.get("top_quotes") or q.get("evidence_quotes") or []
    if quotes:
        body_parts.append('<h4>Representative User Voices</h4>')
        body_parts.append(quote_list(quotes))

    # Research corroboration
    corr = q.get("research_corroboration", [])
    body_parts.append(f'<h4>Backed by Research <span class="count-chip">{len(corr)} sources</span></h4>')
    body_parts.append(research_block(corr))

    return f'''<section class="question-section" id="q{idx}">
      <div class="q-header">
        <div class="q-number">Q{idx}</div>
        <div>
          <h3>{esc(title)}</h3>
          <div class="q-meta">{esc(relevant)} relevant reviews analysed</div>
        </div>
      </div>
      <p class="explain">{esc(explain)}</p>
      {"".join(body_parts)}
    </section>'''


questions_html = "".join(render_question(q, i + 1) for i, q in enumerate(questions))


# ---------------------------------------------------------------------------
# Output files section
# ---------------------------------------------------------------------------

OUTPUT_FILES = [
    ("reviews_unified.json", "Normalised reviews", "All raw reviews from every platform converted into one consistent schema: source, rating, text, date, author.", f"{total_reviews} records"),
    ("reviews_categorised.json", "Tagged reviews", "Each review enriched with themes, sentiment, user segment, a discovery flag and a key quote.", f"{len(reviews)} records"),
    ("insights_report.json", "Insights report", "The four product questions answered with theme frequencies, sentiment splits and research backing. (This page is built from it.)", f"{len(questions)} questions"),
    ("research_compiled.json", "Compiled research", "Plain text extracted from external articles, Reddit threads and Spotify research papers.", f"{len(research_articles)} articles"),
    ("RESEARCH_ARTICLES_FULL.txt", "Research (readable)", "The same research content in a human-readable text file for quick skimming.", "text"),
    ("parse_log.txt", "Parse log", "Every record the parser skipped, with the reason — useful for auditing data quality.", f"{len(parse_log_lines)} entries"),
]

files_html = "".join(f'''<div class="file-card">
    <div class="file-name">{esc(name)}</div>
    <div class="file-title">{esc(title)}</div>
    <p class="file-desc">{esc(desc)}</p>
    <div class="file-tag">{esc(tag)}</div>
  </div>''' for name, title, desc, tag in OUTPUT_FILES)


# ---------------------------------------------------------------------------
# Research library section
# ---------------------------------------------------------------------------

research_rows = []
for a in research_articles:
    stype = label(a.get("source_type", ""), SOURCE_LABELS)
    title = esc(a.get("title", "Unknown"))
    url = esc(a.get("url", "#"))
    topics = ", ".join(a.get("topics", [])[:3])
    research_rows.append(f'''<tr>
      <td><span class="badge badge-{a.get("source_type","")}">{stype}</span></td>
      <td><a href="{url}" target="_blank" rel="noopener">{title}</a></td>
      <td class="muted">{esc(topics)}</td>
    </tr>''')
research_table = "".join(research_rows)

# Source breakdown for research
research_source_chips = "".join(
    f'<span class="chip">{label(k, SOURCE_LABELS)}: <strong>{v}</strong></span>'
    for k, v in research_backing.get("by_source_type", {}).items()
)


# ---------------------------------------------------------------------------
# Parse log preview
# ---------------------------------------------------------------------------

log_reason_counts = Counter()
for line in parse_log_lines:
    # lines look like: [source] reason ...
    if "]" in line:
        reason = line.split("]", 1)[1].strip()
    else:
        reason = line
    # bucket by first few words
    key = " ".join(reason.split()[:4])
    log_reason_counts[key] += 1

log_preview = "".join(
    f'<li><span class="log-count">{v}×</span> {esc(k)}</li>'
    for k, v in log_reason_counts.most_common(8)
)


# ---------------------------------------------------------------------------
# Assemble page
# ---------------------------------------------------------------------------

source_chips = "".join(
    f'<span class="chip">{label(k, SOURCE_LABELS)}: <strong>{v}</strong></span>'
    for k, v in source_breakdown.items()
)

page = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Spotify Review Analyser — Insights Report</title>
<style>
  :root {{
    --green: #1DB954;
    --green-dark: #169c45;
    --bg: #0b0e0f;
    --bg-2: #14181a;
    --card: #1a2024;
    --card-2: #20272b;
    --text: #e8eef0;
    --muted: #8a979d;
    --border: #2a3338;
    --neg: #e74c3c;
    --mix: #f0a020;
    --pos: #1DB954;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    -webkit-font-smoothing: antialiased;
  }}
  a {{ color: var(--green); text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .muted {{ color: var(--muted); }}

  /* Hero */
  .hero {{
    background: radial-gradient(1200px 400px at 20% -10%, rgba(29,185,84,0.18), transparent),
                linear-gradient(180deg, #0e1416, var(--bg));
    border-bottom: 1px solid var(--border);
    padding: 64px 24px 48px;
    text-align: center;
  }}
  .hero .eyebrow {{
    text-transform: uppercase; letter-spacing: 3px; font-size: 12px;
    color: var(--green); font-weight: 700; margin-bottom: 14px;
  }}
  .hero h1 {{ font-size: 44px; font-weight: 800; letter-spacing: -1px; margin-bottom: 12px; }}
  .hero p {{ color: var(--muted); max-width: 640px; margin: 0 auto; font-size: 17px; }}

  .wrap {{ max-width: 1080px; margin: 0 auto; padding: 0 24px; }}

  /* Stats */
  .stats-grid {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 16px; margin: -32px auto 0; position: relative; z-index: 2;
  }}
  .stat-card {{
    background: var(--card); border: 1px solid var(--border); border-radius: 14px;
    padding: 22px 18px; text-align: center;
  }}
  .stat-value {{ font-size: 34px; font-weight: 800; color: var(--green); }}
  .stat-label {{ font-size: 13px; color: var(--muted); margin-top: 4px; }}
  .stat-sub {{ font-size: 11px; color: var(--muted); margin-top: 2px; opacity: 0.7; }}

  section {{ margin: 48px 0; }}
  .section-head {{ margin-bottom: 16px; }}
  .section-head h2 {{ font-size: 26px; font-weight: 800; display: flex; align-items: center; gap: 10px; }}
  .section-head .dot {{ width: 10px; height: 10px; border-radius: 50%; background: var(--green); }}
  .section-head p {{ color: var(--muted); margin-top: 6px; max-width: 760px; }}

  .chip {{
    display: inline-block; background: var(--card-2); border: 1px solid var(--border);
    border-radius: 20px; padding: 5px 14px; font-size: 13px; margin: 4px 6px 4px 0;
  }}

  /* Pipeline */
  .pipeline {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px,1fr)); gap: 12px; }}
  .pipe-step {{
    background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 18px;
    position: relative;
  }}
  .pipe-step .n {{ font-size: 12px; font-weight: 700; color: var(--green); }}
  .pipe-step h4 {{ font-size: 15px; margin: 6px 0; }}
  .pipe-step p {{ font-size: 12.5px; color: var(--muted); }}

  /* Question sections */
  .question-section {{
    background: var(--card); border: 1px solid var(--border); border-radius: 16px;
    padding: 28px; margin-bottom: 22px;
  }}
  .q-header {{ display: flex; gap: 16px; align-items: center; margin-bottom: 8px; }}
  .q-number {{
    flex-shrink: 0; width: 52px; height: 52px; border-radius: 12px;
    background: linear-gradient(135deg, var(--green), var(--green-dark));
    color: #04210f; font-weight: 800; font-size: 18px;
    display: flex; align-items: center; justify-content: center;
  }}
  .q-header h3 {{ font-size: 20px; font-weight: 700; }}
  .q-meta {{ font-size: 13px; color: var(--muted); }}
  .explain {{
    background: var(--bg-2); border-left: 3px solid var(--green); border-radius: 0 8px 8px 0;
    padding: 12px 16px; color: var(--muted); font-size: 14px; margin: 14px 0 20px;
  }}
  .question-section h4 {{
    font-size: 14px; text-transform: uppercase; letter-spacing: 1px; color: var(--text);
    margin: 24px 0 12px; display: flex; align-items: center; gap: 10px;
  }}
  .count-chip {{
    font-size: 11px; background: var(--card-2); border: 1px solid var(--border);
    border-radius: 12px; padding: 2px 10px; letter-spacing: 0; text-transform: none; color: var(--muted);
  }}

  /* Bar chart */
  .bar-chart {{ display: flex; flex-direction: column; gap: 8px; }}
  .bar-row {{ display: grid; grid-template-columns: 170px 1fr 44px; align-items: center; gap: 12px; }}
  .bar-label {{ font-size: 13px; color: var(--muted); text-align: right; }}
  .bar-track {{ background: var(--bg-2); border-radius: 6px; height: 22px; overflow: hidden; }}
  .bar-fill {{
    height: 100%; background: linear-gradient(90deg, var(--green-dark), var(--green));
    border-radius: 6px; transition: width 0.6s ease;
  }}
  .bar-value {{ font-size: 13px; font-weight: 700; }}

  /* Quotes */
  .quote-list {{ list-style: none; display: flex; flex-direction: column; gap: 10px; }}
  .quote-list li {{
    background: var(--bg-2); border-radius: 10px; padding: 12px 16px 12px 38px; position: relative;
    font-style: italic; color: #d4dde0; font-size: 14px;
  }}
  .quote-list li::before {{
    content: '\\201C'; position: absolute; left: 12px; top: 4px; font-size: 28px;
    color: var(--green); font-style: normal; font-family: Georgia, serif;
  }}

  /* Signal flag */
  .signal-flag {{
    background: rgba(29,185,84,0.12); border: 1px solid var(--green); color: var(--green);
    border-radius: 8px; padding: 10px 14px; font-weight: 600; font-size: 14px; margin-top: 8px;
  }}

  /* Segment table */
  .seg-table, .data-table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
  .seg-table th, .seg-table td, .data-table th, .data-table td {{
    text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--border);
  }}
  .seg-table th, .data-table th {{ font-size: 12px; text-transform: uppercase; letter-spacing: 1px; color: var(--muted); }}
  .seg-table .neg {{ color: var(--neg); }}
  .seg-table .mix {{ color: var(--mix); }}
  .seg-table .pos {{ color: var(--pos); }}
  .worst-row {{ background: rgba(231,76,60,0.07); }}
  .worst-tag {{ font-size: 10px; background: var(--neg); color: #fff; border-radius: 10px; padding: 2px 8px; margin-left: 6px; text-transform: uppercase; letter-spacing: 0.5px; }}

  /* Research */
  .research-grid {{ display: grid; gap: 12px; }}
  .research-card {{ background: var(--bg-2); border: 1px solid var(--border); border-radius: 10px; padding: 14px 16px; }}
  .research-head {{ display: flex; align-items: center; gap: 10px; margin-bottom: 8px; flex-wrap: wrap; }}
  .research-head a {{ font-weight: 600; font-size: 14px; }}
  .research-quotes {{ list-style: none; display: flex; flex-direction: column; gap: 6px; }}
  .research-quotes li {{ font-size: 13px; color: var(--muted); padding-left: 14px; position: relative; }}
  .research-quotes li::before {{ content: '—'; position: absolute; left: 0; color: var(--green); }}

  .badge {{
    font-size: 10px; font-weight: 700; padding: 3px 9px; border-radius: 10px;
    text-transform: uppercase; letter-spacing: 0.5px; background: var(--card-2); color: var(--muted);
    border: 1px solid var(--border); white-space: nowrap;
  }}
  .badge-medium {{ background: rgba(255,255,255,0.08); color: #eee; }}
  .badge-reddit {{ background: rgba(255,69,0,0.15); color: #ff7a3d; border-color: rgba(255,69,0,0.3); }}
  .badge-substack {{ background: rgba(255,103,55,0.15); color: #ff8a5c; border-color: rgba(255,103,55,0.3); }}
  .badge-spotify_official {{ background: rgba(29,185,84,0.15); color: var(--green); border-color: rgba(29,185,84,0.3); }}
  .badge-spotify_research {{ background: rgba(80,150,255,0.15); color: #6aa6ff; border-color: rgba(80,150,255,0.3); }}

  /* Files */
  .files-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px,1fr)); gap: 14px; }}
  .file-card {{ background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 18px; }}
  .file-name {{ font-family: "Courier New", monospace; font-size: 13px; color: var(--green); margin-bottom: 6px; }}
  .file-title {{ font-weight: 700; font-size: 15px; margin-bottom: 6px; }}
  .file-desc {{ font-size: 13px; color: var(--muted); margin-bottom: 10px; }}
  .file-tag {{ display: inline-block; font-size: 11px; background: var(--bg-2); border: 1px solid var(--border); border-radius: 10px; padding: 3px 10px; color: var(--muted); }}

  /* Log */
  .log-box {{ background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 18px; }}
  .log-box ul {{ list-style: none; display: flex; flex-direction: column; gap: 6px; }}
  .log-box li {{ font-size: 13px; color: var(--muted); }}
  .log-count {{ display: inline-block; min-width: 34px; color: var(--mix); font-weight: 700; }}

  footer {{ text-align: center; padding: 40px 24px; color: var(--muted); font-size: 13px; border-top: 1px solid var(--border); margin-top: 48px; }}

  @media (max-width: 640px) {{
    .hero h1 {{ font-size: 32px; }}
    .bar-row {{ grid-template-columns: 110px 1fr 36px; }}
    .bar-label {{ font-size: 11px; }}
  }}
</style>
</head>
<body>

<div class="hero">
  <div class="eyebrow">PM Fellowship · Music Discovery</div>
  <h1>Spotify Review Analyser</h1>
  <p>An AI-assisted pipeline that turns {total_reviews} raw user reviews across three platforms into structured product insights — corroborated by {len(research_articles)} external research sources.</p>
</div>

<div class="wrap">

  <div class="stats-grid">
    {stat_card(f"{total_reviews:,}", "Reviews Analysed")}
    {stat_card(source_breakdown.get("google_play", 0), "Google Play")}
    {stat_card(source_breakdown.get("apple_ios", 0), "Apple iOS")}
    {stat_card(source_breakdown.get("reddit", 0), "Reddit")}
    {stat_card(discovery_related, "Discovery-Related")}
    {stat_card(avg_rating if avg_rating else "—", "Avg Rating", "Apple only")}
  </div>

  <section>
    <div class="section-head">
      <h2><span class="dot"></span>How It Works</h2>
      <p>A five-stage pipeline. Each stage writes a file that the next stage reads — so the whole thing is reproducible and auditable end to end.</p>
    </div>
    <div class="pipeline">
      <div class="pipe-step"><div class="n">STAGE 1</div><h4>Parse</h4><p>Reads 4 raw text files and normalises every review into one schema.</p></div>
      <div class="pipe-step"><div class="n">STAGE 2</div><h4>Tag</h4><p>Adds themes, sentiment, user segment & a key quote to each review.</p></div>
      <div class="pipe-step"><div class="n">STAGE 3</div><h4>Fetch Research</h4><p>Pulls text from external articles, Reddit & Spotify research papers.</p></div>
      <div class="pipe-step"><div class="n">STAGE 4</div><h4>Aggregate</h4><p>Answers 4 product questions & cross-references each with research.</p></div>
      <div class="pipe-step"><div class="n">STAGE 5</div><h4>Report</h4><p>This page — plus a live Streamlit dashboard for interactive exploration.</p></div>
    </div>
  </section>

  <section>
    <div class="section-head">
      <h2><span class="dot"></span>Data Sources</h2>
      <p>Reviews were collected from three platforms. Volume is dominated by Google Play, with Reddit adding qualitative depth and Apple iOS contributing the only star-rated records.</p>
    </div>
    <div>{source_chips}</div>
  </section>

  <section>
    <div class="section-head">
      <h2><span class="dot"></span>The Four Questions</h2>
      <p>The core of the analysis. Each question is answered with quantitative breakdowns from user reviews, the actual voices behind the numbers, and supporting passages pulled from independent research.</p>
    </div>
    {questions_html}
  </section>

  <section>
    <div class="section-head">
      <h2><span class="dot"></span>Research Library</h2>
      <p>External sources fetched and mined for corroborating evidence. These ground the review findings in independent reporting and Spotify's own published research.</p>
    </div>
    <div style="margin-bottom:14px">{research_source_chips}</div>
    <table class="data-table">
      <thead><tr><th>Type</th><th>Title</th><th>Topics</th></tr></thead>
      <tbody>{research_table}</tbody>
    </table>
  </section>

  <section>
    <div class="section-head">
      <h2><span class="dot"></span>Output Files</h2>
      <p>Everything the pipeline produces, saved in the <code>output/</code> folder. Each file feeds the next stage and can be inspected independently.</p>
    </div>
    <div class="files-grid">{files_html}</div>
  </section>

  <section>
    <div class="section-head">
      <h2><span class="dot"></span>Data Quality Log</h2>
      <p>The parser skipped {len(parse_log_lines)} records it couldn't confidently structure. Transparency about what was dropped — and why — keeps the dataset honest.</p>
    </div>
    <div class="log-box">
      <ul>{log_preview if log_preview else '<li class="muted">No skipped records.</li>'}</ul>
    </div>
  </section>

</div>

<footer>
  Generated from <code>insights_report.json</code> · Spotify Review Analyser · PM Fellowship Project
</footer>

</body>
</html>'''

REPORT_HTML.write_text(page, encoding="utf-8")
print(f"Report generated: {REPORT_HTML}")
print(f"Open it in your browser:  output/report.html")
