"""
Review Analysis Workflow — Streamlit Dashboard
PM Fellowship Final Project: Spotify Music Discovery

Run locally:
    pip install streamlit
    streamlit run app.py

Deploy: Push to GitHub, connect to share.streamlit.io (free)
"""

import json
import subprocess
import sys
from pathlib import Path
from collections import Counter

import streamlit as st

BASE = Path(__file__).parent
INPUT_DIR = BASE / "input"
OUTPUT_DIR = BASE / "output"

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Spotify Review Analyser",
    page_icon="🎵",
    layout="wide",
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def run_pipeline():
    """Run parse + analyse scripts and reload data."""
    with st.spinner("Parsing review files..."):
        result = subprocess.run(
            [sys.executable, str(BASE / "parse_reviews.py")],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            st.error(f"Parser failed:\n{result.stderr}")
            return False

    with st.spinner("Analysing reviews..."):
        result = subprocess.run(
            [sys.executable, str(BASE / "analyse_reviews.py")],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            st.error(f"Analyser failed:\n{result.stderr}")
            return False

    st.success("Pipeline complete!")
    return True


@st.cache_data
def load_insights():
    path = OUTPUT_DIR / "insights_report.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@st.cache_data
def load_reviews():
    path = OUTPUT_DIR / "reviews_categorised.json"
    if not path.exists():
        path = OUTPUT_DIR / "reviews_unified.json"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def clear_cache():
    load_insights.clear()
    load_reviews.clear()


def sentiment_color(s):
    return {"positive": "#2ecc71", "negative": "#e74c3c", "mixed": "#f39c12"}.get(s, "#95a5a6")


def theme_label(t):
    return {
        "ads": "Ads",
        "premium_upsell": "Premium Upsell",
        "shuffle_repetition": "Shuffle / Repeat",
        "recommendation_quality": "Recommendation Quality",
        "music_discovery": "Music Discovery",
        "app_performance": "App Performance",
        "personalization_overreach": "Personalization Overreach",
        "missing_features": "Missing Features",
        "positive": "Positive Feedback",
    }.get(t, t.replace("_", " ").title())


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("🎵 Spotify Review Analyser")
    st.caption("PM Fellowship · Music Discovery Project")
    st.divider()

    st.markdown("**Pipeline**")
    if st.button("▶  Run Full Pipeline", use_container_width=True, type="primary"):
        ok = run_pipeline()
        if ok:
            clear_cache()
            st.rerun()

    st.divider()
    st.markdown("**Data Sources**")
    for f in ["apple ios.txt", "google play store review.txt",
              "google playstore review 2.txt", "reddit.txt"]:
        exists = (INPUT_DIR / f).exists()
        icon = "✅" if exists else "❌"
        st.caption(f"{icon} {f}")

    st.divider()
    output_exists = (OUTPUT_DIR / "insights_report.json").exists()
    if output_exists:
        st.success("Output files ready")
    else:
        st.warning("Run pipeline to generate output")

# ── Load data ─────────────────────────────────────────────────────────────────

insights = load_insights()
reviews = load_reviews()

if not insights:
    st.title("🎵 Spotify Review Analysis Workflow")
    st.info("No output found. Click **Run Full Pipeline** in the sidebar to get started.")
    st.stop()

# ── Header ────────────────────────────────────────────────────────────────────

st.title("🎵 Spotify Review Analysis Workflow")
st.caption("Automated analysis of App Store, Play Store & Reddit reviews · PM Fellowship Final Project")

# ── KPI row ───────────────────────────────────────────────────────────────────

q_data = {q["question"]: q for q in insights["questions"]}
src = insights["source_breakdown"]

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Reviews", f"{insights['total_reviews_analysed']:,}")
c2.metric("Apple iOS", src.get("apple_ios", 0))
c3.metric("Google Play", src.get("google_play", 0))
c4.metric("Reddit", src.get("reddit", 0))

discovery_count = next(
    (q.get("total_relevant_reviews", 0) for q in insights["questions"]
     if "discover" in q["question"].lower()), 0
)
c5.metric("Discovery-related", discovery_count)

st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "❓ Q1: Discovery Struggles",
    "🔁 Q2: Repeat Listening",
    "😤 Q3: Recommendation Frustrations",
    "👥 Q4: User Segments",
    "🔍 Explore Reviews",
])


# ── Q1 ────────────────────────────────────────────────────────────────────────
with tab1:
    q = next(q for q in insights["questions"] if "discover" in q["question"].lower())
    st.subheader(q["question"])
    st.caption(f"Based on {q['total_relevant_reviews']} relevant reviews")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown("**Theme Frequency**")
        tf = q.get("theme_frequency", {})
        if tf:
            labels = [theme_label(k) for k in tf]
            values = list(tf.values())
            chart_data = {"Theme": labels, "Count": values}
            import pandas as pd
            df = pd.DataFrame(chart_data).sort_values("Count", ascending=False)
            st.bar_chart(df.set_index("Theme"))

    with col2:
        st.markdown("**Top User Quotes**")
        for i, quote in enumerate(q.get("top_quotes", []), 1):
            st.markdown(f"> *\"{quote}\"*")
            if i < len(q.get("top_quotes", [])):
                st.caption("—")


# ── Q2 ────────────────────────────────────────────────────────────────────────
with tab2:
    q = next(q for q in insights["questions"] if "repeat" in q["question"].lower())
    st.subheader(q["question"])
    st.caption(f"Based on {q['total_relevant_reviews']} relevant reviews")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown("**By Platform**")
        by_src = q.get("by_source", {})
        if by_src:
            import pandas as pd
            df = pd.DataFrame({
                "Platform": [k.replace("_", " ").title() for k in by_src],
                "Reviews": list(by_src.values())
            })
            st.bar_chart(df.set_index("Platform"))

    with col2:
        st.markdown("**Top User Quotes**")
        for i, quote in enumerate(q.get("top_quotes", []), 1):
            st.markdown(f"> *\"{quote}\"*")
            if i < len(q.get("top_quotes", [])):
                st.caption("—")


# ── Q3 ────────────────────────────────────────────────────────────────────────
with tab3:
    q = next(q for q in insights["questions"] if "frustration" in q["question"].lower() or "recommendation" in q["question"].lower())
    st.subheader(q["question"])
    st.caption(f"Based on {q['total_relevant_reviews']} relevant reviews")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown("**Sentiment Breakdown**")
        senti = q.get("sentiment_breakdown", {})
        if senti:
            import pandas as pd
            df = pd.DataFrame({
                "Sentiment": [k.title() for k in senti],
                "Count": list(senti.values())
            })
            st.bar_chart(df.set_index("Sentiment"))

        cross = q.get("cross_platform_signal", False)
        platforms = q.get("platforms_with_complaint", [])
        if cross:
            st.success(f"Cross-platform signal detected across: {', '.join(p.replace('_', ' ').title() for p in platforms)}")
        else:
            st.info(f"Found on: {', '.join(platforms)}")

    with col2:
        st.markdown("**Top User Quotes**")
        for i, quote in enumerate(q.get("top_quotes", []), 1):
            st.markdown(f"> *\"{quote}\"*")
            if i < len(q.get("top_quotes", [])):
                st.caption("—")


# ── Q4 ────────────────────────────────────────────────────────────────────────
with tab4:
    q = next(q for q in insights["questions"] if "segment" in q["question"].lower())
    st.subheader(q["question"])

    worst = q.get("worst_affected_segment", "unknown")
    if worst:
        st.error(f"Most affected segment: **{worst.replace('_', ' ').title()}**")

    segments = q.get("segments", {})
    if segments:
        import pandas as pd
        rows = []
        for seg, data in segments.items():
            total = data["review_count"]
            neg = data["sentiment"].get("negative", 0)
            pos = data["sentiment"].get("positive", 0)
            rows.append({
                "Segment": seg.replace("_", " ").title(),
                "Total Reviews": total,
                "Negative": neg,
                "Positive": pos,
                "Mixed": data["sentiment"].get("mixed", 0),
                "Top Issue": next(iter(data.get("top_themes", {})), "—").replace("_", " ").title(),
            })
        df = pd.DataFrame(rows).set_index("Segment")
        st.dataframe(df, use_container_width=True)

    st.markdown("**Evidence Quotes from Worst-Affected Segment**")
    for quote in q.get("evidence_quotes", []):
        st.markdown(f"> *\"{quote}\"*")


# ── Explore ───────────────────────────────────────────────────────────────────
with tab5:
    st.subheader("Explore Raw Reviews")

    col1, col2, col3 = st.columns(3)
    source_filter = col1.selectbox("Source", ["All", "Apple iOS", "Google Play", "Reddit"])
    sentiment_filter = col2.selectbox("Sentiment", ["All", "Negative", "Positive", "Mixed"])
    search_term = col3.text_input("Search text", placeholder="e.g. shuffle, discover, ads...")

    filtered = reviews
    if source_filter != "All":
        src_map = {"Apple iOS": "apple_ios", "Google Play": "google_play", "Reddit": "reddit"}
        filtered = [r for r in filtered if r["source"] == src_map[source_filter]]
    if sentiment_filter != "All":
        filtered = [r for r in filtered if r.get("sentiment", "").lower() == sentiment_filter.lower()]
    if search_term:
        filtered = [r for r in filtered if search_term.lower() in r.get("text", "").lower()]

    st.caption(f"Showing {len(filtered)} of {len(reviews)} reviews")

    for r in filtered[:50]:
        with st.expander(f"[{r['source'].replace('_', ' ').title()}] {r.get('author', 'unknown')} · {r.get('date', '')}"):
            if "rating" in r:
                st.caption(f"{'⭐' * r['rating']} ({r['rating']}/5)")
            themes = r.get("themes", [])
            if themes:
                st.caption("Themes: " + " · ".join(theme_label(t) for t in themes))
            senti = r.get("sentiment", "")
            if senti:
                color = sentiment_color(senti)
                st.markdown(f"<span style='color:{color}'>● {senti.title()}</span>", unsafe_allow_html=True)
            st.write(r.get("text", ""))

    if len(filtered) > 50:
        st.caption(f"… and {len(filtered) - 50} more. Use filters to narrow down.")
