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
INPUT = BASE / "input"

INSIGHTS = OUTPUT / "insights_report.json"
CATEGORISED = OUTPUT / "reviews_categorised.json"
# prefer freshly-fetched copy in output/, fall back to committed copy in input/
RESEARCH = OUTPUT / "research_compiled.json" if (OUTPUT / "research_compiled.json").exists() else INPUT / "research_compiled.json"
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

# Per-theme review sets — embedded in the page for JS drill-down
theme_data = {}
for r in reviews:
    for t in r.get("themes", []):
        theme_data.setdefault(t, []).append({
            "source":    r.get("source", ""),
            "text":      r.get("text", "")[:700],
            "date":      r.get("date", ""),
            "author":    r.get("author", "unknown"),
            "sentiment": r.get("sentiment", ""),
            "key_quote": r.get("key_quote", ""),
        })
theme_data_json = json.dumps(theme_data, ensure_ascii=False)


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


def bar_chart(counts_dict, label_map, max_items=10, clickable_themes=False):
    if not counts_dict:
        return '<p class="muted">No data.</p>'
    items = sorted(counts_dict.items(), key=lambda kv: kv[1], reverse=True)[:max_items]
    top = items[0][1] if items else 1
    rows = []
    for key, val in items:
        pct = (val / top) * 100 if top else 0
        click = f' onclick="showTheme(\'{key}\')" title="Explore {esc(label(key, label_map))} reviews"' if clickable_themes else ''
        cls = 'bar-row clickable' if clickable_themes else 'bar-row'
        rows.append(f'''<div class="{cls}"{click}>
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
    "What listening behaviors are users trying to achieve?":
        "Reviews categorised by the listening context users describe — study, workout, commute, mood, "
        "social, and background listening. Reveals the use-cases Spotify must serve well.",
    "What unmet needs emerge consistently across reviews?":
        "Reviews expressing unmet needs, wishes, or feature requests with non-positive sentiment. "
        "Theme breakdown shows which gaps appear most frequently across all platforms.",
}


def render_question(q, idx):
    title = q.get("question", "")
    explain = QUESTION_EXPLAIN.get(title, "")
    relevant = q.get("total_relevant_reviews", "")

    body_parts = []

    # Q1: theme frequency
    if "theme_frequency" in q:
        body_parts.append('<h4>Theme Breakdown <span class="click-hint">Click a bar to explore reviews</span></h4>')
        body_parts.append(bar_chart(q["theme_frequency"], THEME_LABELS, clickable_themes=True))

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
            neg_rate = data.get("negative_rate", (neg / tot if tot else 0))
            top_theme = next(iter(data.get("top_themes", {})), "")
            is_worst = seg == q.get("worst_affected_segment")
            worst_tag = ' <span class="worst-tag">Most affected</span>' if is_worst else ""
            rows.append(f'''<tr class="{'worst-row' if is_worst else ''}">
              <td><strong>{esc(label(seg, SEGMENT_LABELS))}</strong>{worst_tag}</td>
              <td>{tot}</td>
              <td class="neg">{neg}</td>
              <td class="neg"><strong>{neg_rate * 100:.1f}%</strong></td>
              <td class="mix">{mix}</td>
              <td class="pos">{pos}</td>
              <td>{esc(label(top_theme, THEME_LABELS))}</td>
            </tr>''')
        body_parts.append(f'''<table class="seg-table">
          <thead><tr><th>Segment</th><th>Reviews</th><th>Neg</th><th>Neg %</th><th>Mixed</th><th>Pos</th><th>Top Theme</th></tr></thead>
          <tbody>{"".join(rows)}</tbody>
        </table>''')
        worst_lbl = label(q.get("worst_affected_segment", ""), SEGMENT_LABELS)
        body_parts.append(f'''<div class="method-note">
          <strong>How "most affected" is chosen:</strong> We rank by <em>negative rate</em>
          (% of a segment's reviews that are negative), not raw count — raw count just rewards
          the biggest bucket. Segments need ≥200 reviews to qualify (so tiny samples can't win on
          noise), and the unclassified catch-all is excluded since it's a tagging gap, not a real
          audience. Among the segments that are statistically tied on pain, we prioritise by Growth
          lever and real reach. <strong>{esc(worst_lbl)}</strong> tops the list: near-highest negative
          rate, by far the largest genuine audience, and a direct conversion-to-Premium revenue lever.
        </div>''')

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


_NUM_WORDS = {1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five",
              6: "Six", 7: "Seven", 8: "Eight", 9: "Nine", 10: "Ten"}

questions_html = "".join(render_question(q, i + 1) for i, q in enumerate(questions))


# ---------------------------------------------------------------------------
# Theme Explorer cards (clickable overview grid)
# ---------------------------------------------------------------------------

def theme_explorer_cards():
    cards = []
    for theme_key in THEME_LABELS:
        count = theme_counts.get(theme_key, 0)
        if count == 0:
            continue
        theme_revs = theme_data.get(theme_key, [])
        sent = Counter(r["sentiment"] for r in theme_revs)
        total = len(theme_revs) or 1
        neg_pct = round(sent.get("negative", 0) / total * 100)
        pos_pct = round(sent.get("positive", 0) / total * 100)
        mix_pct = 100 - neg_pct - pos_pct
        top_q = next((r["key_quote"] for r in theme_revs if r.get("key_quote")), "")
        quote_html = f'<div class="tc-quote">{esc(top_q[:120])}…</div>' if top_q else ""
        cards.append(f'''<div class="theme-card" onclick="showTheme('{theme_key}')">
          <div class="tc-header">
            <span class="tc-label">{esc(THEME_LABELS[theme_key])}</span>
            <span class="tc-count">{count}</span>
          </div>
          <div class="tc-sent-bar">
            <div class="ts-neg" style="width:{neg_pct}%" title="{neg_pct}% negative"></div>
            <div class="ts-pos" style="width:{pos_pct}%" title="{pos_pct}% positive"></div>
            <div class="ts-mix" style="width:{mix_pct}%" title="{mix_pct}% mixed"></div>
          </div>
          <div class="tc-meta">{neg_pct}% negative · {pos_pct}% positive</div>
          {quote_html}
        </div>''')
    return '<div class="theme-grid">' + "".join(cards) + "</div>"

theme_cards_html = theme_explorer_cards()


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

# Build a dynamic description based on what sources were actually uploaded
_active_sources = {k: v for k, v in source_breakdown.items() if v > 0}
_source_names = [label(k, SOURCE_LABELS) for k in _active_sources]
_dominant = max(_active_sources, key=_active_sources.get) if _active_sources else None
_platform_count = len(_active_sources)
if _platform_count == 0:
    data_sources_desc = "No reviews loaded."
elif _platform_count == 1:
    data_sources_desc = f"Reviews were collected from {_source_names[0]}."
else:
    _parts = ", ".join(_source_names[:-1]) + f" and {_source_names[-1]}"
    _dominant_label = label(_dominant, SOURCE_LABELS) if _dominant else ""
    _extras = []
    if "apple_ios" in _active_sources:
        _extras.append("Apple iOS contributes star-rated records")
    if "reddit" in _active_sources:
        _extras.append("Reddit adds qualitative depth")
    _extra_str = (" — " + "; ".join(_extras) + ".") if _extras else "."
    data_sources_desc = (
        f"Reviews were collected from {_parts}. "
        f"Volume is dominated by {_dominant_label}{_extra_str}"
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
  .method-note {{
    background: rgba(29,185,84,0.06); border-left: 3px solid var(--green);
    border-radius: 6px; padding: 12px 16px; margin-top: 14px;
    font-size: 13px; line-height: 1.65; color: var(--muted);
  }}
  .method-note strong {{ color: var(--text); }}
  .method-note em {{ color: var(--green); font-style: normal; }}

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

  /* Clickable bars */
  .bar-row.clickable {{ cursor: pointer; border-radius: 8px; padding: 2px 4px; margin: 0 -4px; transition: background 0.15s; }}
  .bar-row.clickable:hover {{ background: rgba(29,185,84,0.08); }}
  .bar-row.clickable:hover .bar-label {{ color: var(--green); }}
  .click-hint {{ font-size: 11px; font-weight: 400; color: var(--muted); letter-spacing: 0; text-transform: none; }}

  /* Theme explorer cards */
  .theme-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 14px; }}
  .theme-card {{
    background: var(--card); border: 1px solid var(--border); border-radius: 14px;
    padding: 18px; cursor: pointer; transition: border-color 0.15s, background 0.15s;
  }}
  .theme-card:hover {{ border-color: var(--green); background: var(--card-2); }}
  .tc-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }}
  .tc-label {{ font-weight: 700; font-size: 14px; }}
  .tc-count {{ font-size: 22px; font-weight: 800; color: var(--green); }}
  .tc-sent-bar {{ display: flex; height: 6px; border-radius: 4px; overflow: hidden; background: var(--bg-2); margin-bottom: 6px; }}
  .ts-neg {{ background: var(--neg); }}
  .ts-pos {{ background: var(--pos); }}
  .ts-mix {{ background: var(--mix); }}
  .tc-meta {{ font-size: 11px; color: var(--muted); margin-bottom: 8px; }}
  .tc-quote {{ font-size: 12px; color: var(--muted); font-style: italic; line-height: 1.5; border-top: 1px solid var(--border); padding-top: 8px; margin-top: 4px; }}

  /* Detail panel */
  #detail-panel {{
    position: fixed; top: 0; right: 0; width: 620px; max-width: 100vw; height: 100vh;
    background: var(--bg-2); border-left: 1px solid var(--border);
    transform: translateX(100%); transition: transform 0.28s cubic-bezier(.4,0,.2,1);
    overflow: hidden; z-index: 1000; display: flex; flex-direction: column;
  }}
  #detail-panel.open {{ transform: translateX(0); }}
  #panel-overlay {{
    position: fixed; inset: 0; background: rgba(0,0,0,0.55); z-index: 999;
    opacity: 0; pointer-events: none; transition: opacity 0.28s;
  }}
  #panel-overlay.open {{ opacity: 1; pointer-events: all; }}

  .panel-head {{
    background: var(--bg-2); border-bottom: 1px solid var(--border); padding: 20px 24px;
    display: flex; justify-content: space-between; align-items: flex-start;
    flex-shrink: 0;
  }}
  .panel-title {{ font-size: 22px; font-weight: 800; }}
  .panel-subtitle {{ font-size: 13px; color: var(--muted); margin-top: 4px; }}
  .panel-close {{
    background: var(--card); border: 1px solid var(--border); color: var(--text);
    font-size: 18px; cursor: pointer; border-radius: 8px; padding: 4px 12px;
    flex-shrink: 0; line-height: 1.6;
  }}
  .panel-close:hover {{ border-color: var(--green); color: var(--green); }}

  .panel-body {{ padding: 20px 24px; flex: 1; overflow-y: auto; min-height: 0; }}
  .panel-sent {{
    display: flex; height: 10px; border-radius: 6px; overflow: hidden;
    background: var(--bg); margin-bottom: 6px;
  }}
  .panel-sent-labels {{ display: flex; gap: 14px; margin-bottom: 20px; }}
  .psl {{ font-size: 12px; color: var(--muted); display: flex; align-items: center; gap: 5px; }}
  .psl-dot {{ width: 9px; height: 9px; border-radius: 50%; }}

  .panel-quotes {{ margin-bottom: 22px; }}
  .panel-quotes h4 {{ font-size: 13px; text-transform: uppercase; letter-spacing: 1px; color: var(--muted); margin-bottom: 10px; }}

  .review-list {{ display: flex; flex-direction: column; gap: 12px; }}
  .review-list h4 {{ font-size: 13px; text-transform: uppercase; letter-spacing: 1px; color: var(--muted); margin-bottom: 10px; }}
  .review-item {{
    background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 14px;
  }}
  .review-item-meta {{ display: flex; align-items: center; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; }}
  .review-item-text {{ font-size: 13.5px; line-height: 1.6; color: #d4dde0; }}
  .review-item-text.collapsed {{ display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }}
  .expand-btn {{ font-size: 12px; color: var(--green); cursor: pointer; background: none; border: none; padding: 4px 0; }}
  .sent-dot {{ width: 9px; height: 9px; border-radius: 50%; display: inline-block; flex-shrink: 0; }}
  .sent-dot-negative {{ background: var(--neg); }}
  .sent-dot-positive {{ background: var(--pos); }}
  .sent-dot-mixed {{ background: var(--mix); }}
  .load-more-btn {{
    width: 100%; margin-top: 16px; padding: 12px; background: var(--card);
    border: 1px solid var(--border); border-radius: 10px; color: var(--green);
    font-weight: 600; font-size: 14px; cursor: pointer;
  }}
  .load-more-btn:hover {{ border-color: var(--green); }}

  @media (max-width: 640px) {{
    .hero h1 {{ font-size: 32px; }}
    .bar-row {{ grid-template-columns: 110px 1fr 36px; }}
    .bar-label {{ font-size: 11px; }}
    #detail-panel {{ width: 100vw; }}
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
    {"".join(stat_card(v, label(k, SOURCE_LABELS)) for k, v in source_breakdown.items() if v > 0)}
    {stat_card(discovery_related, "Discovery-Related")}
    {stat_card(avg_rating if avg_rating else "—", "Avg Rating", "Apple only") if source_breakdown.get("apple_ios", 0) > 0 else ""}
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
      <p>{data_sources_desc}</p>
    </div>
    <div>{source_chips}</div>
  </section>

  <section>
    <div class="section-head">
      <h2><span class="dot"></span>Theme Explorer</h2>
      <p>Every review is tagged with one or more themes. Click any card to see all the reviews behind it — sentiment breakdown, key quotes, and full review text.</p>
    </div>
    {theme_cards_html}
  </section>

  <section>
    <div class="section-head">
      <h2><span class="dot"></span>The {_NUM_WORDS.get(len(questions), str(len(questions)))} Questions</h2>
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

<!-- Detail panel overlay -->
<div id="panel-overlay" onclick="closePanel()"></div>
<div id="detail-panel">
  <div class="panel-head">
    <div>
      <div class="panel-title" id="panel-title"></div>
      <div class="panel-subtitle" id="panel-subtitle"></div>
    </div>
    <button class="panel-close" onclick="closePanel()">✕</button>
  </div>
  <div class="panel-body">
    <div class="panel-sent" id="panel-sent-bar"></div>
    <div class="panel-sent-labels" id="panel-sent-labels"></div>
    <div class="panel-quotes" id="panel-quotes"></div>
    <div class="review-list" id="panel-reviews"></div>
    <button class="load-more-btn" id="load-more-btn" onclick="loadMore()" style="display:none">Load more reviews</button>
  </div>
</div>

<script>
const THEME_DATA = {theme_data_json};
const THEME_LABELS = {json.dumps(THEME_LABELS)};
const SOURCE_LABELS = {json.dumps(SOURCE_LABELS)};

console.log('[SpotifyRA] Report loaded.');
console.log('[SpotifyRA] Themes available:', Object.keys(THEME_DATA));
console.log('[SpotifyRA] Total theme-tagged entries:', Object.values(THEME_DATA).reduce((s,a)=>s+a.length,0));

let _currentReviews = [];
let _shownCount = 0;
const PAGE_SIZE = 20;

function showTheme(key) {{
  console.log('[SpotifyRA] showTheme:', key);
  const reviews = THEME_DATA[key] || [];
  const label = THEME_LABELS[key] || key;
  console.log('[SpotifyRA]', label, '— review count:', reviews.length);

  _currentReviews = reviews;
  _shownCount = 0;

  document.getElementById('panel-title').textContent = label;
  document.getElementById('panel-subtitle').textContent = reviews.length + ' reviews tagged with this theme';

  // Sentiment bar
  const counts = {{negative:0, positive:0, mixed:0}};
  reviews.forEach(r => {{ if (counts[r.sentiment] !== undefined) counts[r.sentiment]++; }});
  const total = reviews.length || 1;
  const negP = (counts.negative / total * 100).toFixed(1);
  const posP = (counts.positive / total * 100).toFixed(1);
  const mixP = (100 - negP - posP).toFixed(1);
  console.log('[SpotifyRA] Sentiment — neg:', negP+'%', 'pos:', posP+'%', 'mix:', mixP+'%');
  document.getElementById('panel-sent-bar').innerHTML =
    `<div class="ts-neg" style="width:${{negP}}%"></div>` +
    `<div class="ts-pos" style="width:${{posP}}%"></div>` +
    `<div class="ts-mix" style="width:${{mixP}}%"></div>`;
  document.getElementById('panel-sent-labels').innerHTML =
    `<span class="psl"><span class="psl-dot" style="background:var(--neg)"></span>${{negP}}% negative (${{counts.negative}})</span>` +
    `<span class="psl"><span class="psl-dot" style="background:var(--pos)"></span>${{posP}}% positive (${{counts.positive}})</span>` +
    `<span class="psl"><span class="psl-dot" style="background:var(--mix)"></span>${{mixP}}% mixed</span>`;

  // Top quotes
  const quotes = reviews.filter(r => r.key_quote).slice(0, 5);
  console.log('[SpotifyRA] Key quotes found:', quotes.length);
  const qDiv = document.getElementById('panel-quotes');
  if (quotes.length) {{
    qDiv.innerHTML = '<h4>Key Quotes</h4><ul class="quote-list">' +
      quotes.map(r => `<li>${{escHtml(r.key_quote)}}</li>`).join('') + '</ul>';
  }} else {{
    qDiv.innerHTML = '';
  }}

  // Reviews
  document.getElementById('panel-reviews').innerHTML = '<h4>All Reviews</h4>';
  appendReviews();

  document.getElementById('detail-panel').classList.add('open');
  document.getElementById('panel-overlay').classList.add('open');
  document.querySelector('.panel-body').scrollTop = 0;
  console.log('[SpotifyRA] Panel opened for:', label);
}}

function appendReviews() {{
  const slice = _currentReviews.slice(_shownCount, _shownCount + PAGE_SIZE);
  console.log('[SpotifyRA] appendReviews — shownCount:', _shownCount, 'slice:', slice.length, 'total:', _currentReviews.length);
  if (!slice.length) {{ console.warn('[SpotifyRA] No more reviews to load.'); return; }}
  const container = document.getElementById('panel-reviews');
  let firstNew = null;
  slice.forEach((r, i) => {{
    const idx = _shownCount + i;
    const srcLabel = SOURCE_LABELS[r.source] || r.source;
    const sentClass = r.sentiment ? 'sent-dot-' + r.sentiment : '';
    const authorDate = [r.author !== 'unknown' ? r.author : '', r.date !== 'unknown' ? r.date : ''].filter(Boolean).join(' · ');
    const itemEl = document.createElement('div');
    itemEl.className = 'review-item';
    itemEl.innerHTML =
      `<div class="review-item-meta">` +
        `<span class="badge badge-${{r.source}}">${{escHtml(srcLabel)}}</span>` +
        `<span class="sent-dot ${{sentClass}}" title="${{r.sentiment}}"></span>` +
        (authorDate ? `<span class="muted" style="font-size:12px">${{escHtml(authorDate)}}</span>` : '') +
      `</div>` +
      `<div class="review-item-text collapsed" id="rt-${{idx}}">${{escHtml(r.text)}}</div>` +
      `<button class="expand-btn" onclick="toggleText(${{idx}})">Show more</button>`;
    container.appendChild(itemEl);
    if (i === 0) firstNew = itemEl;
  }});
  _shownCount += slice.length;
  const btn = document.getElementById('load-more-btn');
  const hasMore = _shownCount < _currentReviews.length;
  btn.style.display = hasMore ? 'block' : 'none';
  console.log('[SpotifyRA] After append — shownCount:', _shownCount, 'hasMore:', hasMore, 'btn visible:', hasMore);
  if (firstNew) firstNew.scrollIntoView({{ behavior: 'smooth', block: 'nearest' }});
}}

function loadMore() {{
  console.log('[SpotifyRA] loadMore clicked');
  appendReviews();
}}

function toggleText(idx) {{
  const el = document.getElementById('rt-' + idx);
  const btn = el.nextElementSibling;
  if (el.classList.contains('collapsed')) {{
    el.classList.remove('collapsed');
    btn.textContent = 'Show less';
  }} else {{
    el.classList.add('collapsed');
    btn.textContent = 'Show more';
  }}
}}

function closePanel() {{
  console.log('[SpotifyRA] Panel closed');
  document.getElementById('detail-panel').classList.remove('open');
  document.getElementById('panel-overlay').classList.remove('open');
}}

function escHtml(s) {{
  return String(s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}}

document.addEventListener('keydown', e => {{ if (e.key === 'Escape') closePanel(); }});
</script>

</body>
</html>'''

REPORT_HTML.write_text(page, encoding="utf-8")
print(f"Report generated: {REPORT_HTML}")
print(f"Open it in your browser:  output/report.html")
