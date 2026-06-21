"""
analyse_reviews.py

Reads reviews_unified.json and produces insights_report.json answering:
  1. Why do users struggle to discover new music?
  2. What causes repeat listening?
  3. What are recommendation frustrations?
  4. Which segments suffer most?

Two modes:
  - WITHOUT Claude API (default): keyword-based tagging, no external calls needed.
    Just run:  python analyse_reviews.py
  - WITH Claude API (optional, richer tags): set ANTHROPIC_API_KEY first, then:
    pip install anthropic
    set ANTHROPIC_API_KEY=sk-ant-...
    python analyse_reviews.py

If reviews_categorised.json already exists with manual/AI tags, those tags are
used directly and the tagging step is skipped entirely.
"""

import json
import os
import re
import time
from collections import Counter, defaultdict
from pathlib import Path

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

BASE = Path(__file__).parent
INPUT = BASE / "input"
OUTPUT = BASE / "output"
OUTPUT.mkdir(exist_ok=True)

UNIFIED_PATH = OUTPUT / "reviews_unified.json"
CATEGORISED_PATH = OUTPUT / "reviews_categorised.json"
INSIGHTS_PATH = OUTPUT / "insights_report.json"
RESEARCH_SOURCES_PATH = INPUT / "research_sources.json"
RESEARCH_COMPILED_PATH = OUTPUT / "research_compiled.json"

THEMES = [
    "ads",
    "premium_upsell",
    "shuffle_repetition",
    "recommendation_quality",
    "music_discovery",
    "app_performance",
    "personalization_overreach",
    "missing_features",
    "positive",
]

SEGMENTS = ["free_tier_user", "power_listener", "casual_user", "premium_user", "unknown"]

CATEGORISE_PROMPT = """You are analyzing Spotify user reviews for a product manager research project.

For each review in the JSON array below, return a JSON array with one object per review containing:
- "id": same integer id as in the input
- "themes": list of relevant themes from ONLY these options: {themes}
- "discovery_related": true if the review mentions music discovery, new music, recommendations, or repeat listening; false otherwise
- "user_segment": one of {segments}
- "sentiment": "positive", "negative", or "mixed"
- "key_quote": the single most expressive sentence (max 20 words) that best captures the user's feeling

Return ONLY valid JSON array. No explanation, no markdown, no extra text.

Reviews:
{reviews}"""


# ---------------------------------------------------------------------------
# Keyword-based fallback tagger (no API needed)
# ---------------------------------------------------------------------------

KEYWORD_RULES = {
    "ads":                    re.compile(r"\b(ad|ads|advert|advertisement|commercial)\b", re.I),
    "premium_upsell":         re.compile(r"\b(premium|subscription|paid|paywall|upgrade|free version)\b", re.I),
    "shuffle_repetition":     re.compile(r"\b(shuffle|same song|repeat|loop|over and over|again and again|repetiti)\b", re.I),
    "recommendation_quality": re.compile(r"\b(recommend|suggestion|discov|algorithm|playlist|radio)\b", re.I),
    "music_discovery":        re.compile(r"\b(new music|discover|explore|new artist|new song|find music|fresh)\b", re.I),
    "app_performance":        re.compile(r"\b(crash|bug|slow|lag|freeze|error|glitch|not working|broken)\b", re.I),
    "personalization_overreach": re.compile(r"\b(personali[sz]|made for me|echo chamber|only for me|customis)\b", re.I),
    "missing_features":       re.compile(r"\b(missing|feature|wish|should have|used to|bring back|cant|can't|unable)\b", re.I),
    "positive":               re.compile(r"\b(love|great|amazing|best|excellent|perfect|awesome|good|fantastic|wonderful)\b", re.I),
}

SENTIMENT_POS = re.compile(r"\b(love|great|amazing|best|excellent|perfect|awesome|good|fantastic|happy|enjoy)\b", re.I)
SENTIMENT_NEG = re.compile(r"\b(hate|terrible|worst|awful|bad|useless|broken|frustrat|annoying|disappoint|trash|garbage)\b", re.I)
DISCOVERY_KW  = re.compile(r"\b(discover|new music|new artist|recommend|algorithm|playlist|repeat|same song|shuffle|personali[sz]|echo chamber)\b", re.I)

SEGMENT_RULES = {
    "free_tier_user":  re.compile(r"\b(free|ad|ads|can't skip|shuffle|limited)\b", re.I),
    "premium_user":    re.compile(r"\b(premium|paid|subscription|subscriber)\b", re.I),
    "power_listener":  re.compile(r"\b(playlist|artist|album|discover|library|collection|track)\b", re.I),
}


def keyword_tag(review):
    text = review.get("text", "")
    themes = [t for t, pat in KEYWORD_RULES.items() if pat.search(text)]
    if not themes:
        themes = ["missing_features"]

    pos = bool(SENTIMENT_POS.search(text))
    neg = bool(SENTIMENT_NEG.search(text))
    sentiment = "positive" if (pos and not neg) else "negative" if (neg and not pos) else "mixed"

    discovery_related = bool(DISCOVERY_KW.search(text))

    segment = "unknown"
    for seg, pat in SEGMENT_RULES.items():
        if pat.search(text):
            segment = seg
            break

    # key_quote: first sentence up to 20 words
    sentences = re.split(r"[.!?]", text)
    key_quote = ""
    for s in sentences:
        words = s.strip().split()
        if 4 <= len(words) <= 20:
            key_quote = s.strip()
            break
    if not key_quote:
        key_quote = " ".join(text.split()[:20])

    return {
        "themes": themes,
        "discovery_related": discovery_related,
        "user_segment": segment,
        "sentiment": sentiment,
        "key_quote": key_quote,
    }


def keyword_tag_all(reviews):
    print("  Using keyword-based tagging (no API required)...")
    for r in reviews:
        tags = keyword_tag(r)
        r.update(tags)
    return reviews


# ---------------------------------------------------------------------------
# Claude API tagger (optional)
# ---------------------------------------------------------------------------

def batch_categorise(client, reviews, batch_size=50):
    categorised = {}

    for i in range(0, len(reviews), batch_size):
        batch = reviews[i: i + batch_size]
        batch_input = [{"id": r["_id"], "text": r["text"][:800]} for r in batch]

        prompt = CATEGORISE_PROMPT.format(
            themes=json.dumps(THEMES),
            segments=json.dumps(SEGMENTS),
            reviews=json.dumps(batch_input, ensure_ascii=False),
        )

        print(f"  Categorising batch {i // batch_size + 1} / {-(-len(reviews) // batch_size)} ...")

        for attempt in range(3):
            try:
                message = client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=4096,
                    messages=[{"role": "user", "content": prompt}],
                )
                raw = message.content[0].text.strip()
                # Strip markdown code fences if present
                raw = re.sub(r"^```[a-z]*\n?", "", raw)
                raw = re.sub(r"\n?```$", "", raw)
                results = json.loads(raw)
                for item in results:
                    categorised[item["id"]] = item
                break
            except (json.JSONDecodeError, KeyError) as e:
                print(f"    Attempt {attempt + 1} failed: {e}")
                if attempt == 2:
                    print("    Giving up on this batch — records will lack tags")
                time.sleep(2)

    return categorised


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------

def top_quotes(records, n=5):
    return [r.get("key_quote", r["text"][:120]) for r in records[:n]]


def answer_q1(records, research_articles):
    """Why do users struggle to discover new music?"""
    relevant = [r for r in records if r.get("discovery_related") and r.get("sentiment") != "positive"]
    theme_counts = Counter(t for r in relevant for t in r.get("themes", []))
    return {
        "question": "Why do users struggle to discover new music?",
        "total_relevant_reviews": len(relevant),
        "theme_frequency": dict(theme_counts.most_common()),
        "top_quotes": top_quotes(
            [r for r in relevant if "music_discovery" in r.get("themes", []) or
             "recommendation_quality" in r.get("themes", [])]
        ),
        "research_corroboration": corroborate_with_research(research_articles, "q1_discovery"),
    }


def answer_q2(records, research_articles):
    """What causes repeat listening?"""
    keywords = re.compile(r"\b(same songs?|repeat|over and over|again and again|shuffle|loop)\b", re.IGNORECASE)
    relevant = [r for r in records if "shuffle_repetition" in r.get("themes", []) or keywords.search(r.get("text", ""))]
    by_source = Counter(r["source"] for r in relevant)
    return {
        "question": "What causes repeat listening?",
        "total_relevant_reviews": len(relevant),
        "by_source": dict(by_source),
        "top_quotes": top_quotes(relevant),
        "research_corroboration": corroborate_with_research(research_articles, "q2_repeat"),
    }


def answer_q3(records, research_articles):
    """What are the recommendation frustrations?"""
    relevant = [r for r in records if any(
        t in r.get("themes", []) for t in ("recommendation_quality", "personalization_overreach")
    )]
    sentiment_counts = Counter(r.get("sentiment", "unknown") for r in relevant)
    sources_present = {r["source"] for r in relevant}
    cross_platform = len(sources_present) == 3
    return {
        "question": "What are the most common recommendation frustrations?",
        "total_relevant_reviews": len(relevant),
        "sentiment_breakdown": dict(sentiment_counts),
        "cross_platform_signal": cross_platform,
        "platforms_with_complaint": list(sources_present),
        "top_quotes": top_quotes(relevant),
        "research_corroboration": corroborate_with_research(research_articles, "q3_recommendation"),
    }


def answer_q4(records, research_articles):
    """Which user segments suffer most?"""
    by_segment = defaultdict(list)
    for r in records:
        seg = r.get("user_segment", "unknown")
        by_segment[seg].append(r)

    segment_summary = {}
    for seg, seg_records in by_segment.items():
        sentiment_dist = Counter(r.get("sentiment", "unknown") for r in seg_records)
        top_themes = Counter(t for r in seg_records for t in r.get("themes", []))
        segment_summary[seg] = {
            "review_count": len(seg_records),
            "sentiment": dict(sentiment_dist),
            "top_themes": dict(top_themes.most_common(5)),
        }

    worst = max(
        segment_summary.items(),
        key=lambda kv: kv[1]["sentiment"].get("negative", 0) / max(kv[1]["review_count"], 1),
        default=(None, {}),
    )

    return {
        "question": "Which user segments experience the most discovery challenges?",
        "total_relevant_reviews": len(records),
        "segments": segment_summary,
        "worst_affected_segment": worst[0],
        "evidence_quotes": top_quotes(
            [r for r in records if r.get("user_segment") == worst[0] and r.get("sentiment") == "negative"]
        ),
        "research_corroboration": corroborate_with_research(research_articles, "q4_segments"),
    }


# ---------------------------------------------------------------------------
# Research sources integration — with actual text corroboration
# ---------------------------------------------------------------------------

# Keywords per question used to find relevant sentences in research text
RESEARCH_QUESTION_KEYWORDS = {
    "q1_discovery": re.compile(
        r"\b(discover|discovery|new music|new artist|explore|find music|recommendation|algorithm|suggest)\b",
        re.I
    ),
    "q2_repeat": re.compile(
        r"\b(repeat|same song|shuffle|loop|over and over|predictable|familiar|habit|stuck)\b",
        re.I
    ),
    "q3_recommendation": re.compile(
        r"\b(recommend|algorithm|personali[sz]|playlist|echo chamber|taste|preference|curate|filter)\b",
        re.I
    ),
    "q4_segments": re.compile(
        r"\b(free.?tier|premium|casual|power.?user|listener|subscriber|segment|user.?type)\b",
        re.I
    ),
}

MIN_SENTENCE_WORDS = 8
MAX_SENTENCE_WORDS = 50


def load_research_sources():
    """Load research sources metadata."""
    if not RESEARCH_SOURCES_PATH.exists():
        return {}
    with open(RESEARCH_SOURCES_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_research_compiled():
    """Load compiled research articles with full text."""
    if not RESEARCH_COMPILED_PATH.exists():
        return []
    with open(RESEARCH_COMPILED_PATH, encoding="utf-8") as f:
        data = json.load(f)
        return data.get("articles", [])


def extract_relevant_sentences(text, pattern, n=3):
    """Pull up to n sentences from text that match a keyword pattern."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    results = []
    seen = set()
    for s in sentences:
        s = s.strip()
        words = s.split()
        if MIN_SENTENCE_WORDS <= len(words) <= MAX_SENTENCE_WORDS and pattern.search(s):
            key = s[:60]
            if key not in seen:
                seen.add(key)
                results.append(s)
        if len(results) >= n:
            break
    return results


def corroborate_with_research(articles, question_key):
    """Find research passages that back up a given question."""
    pattern = RESEARCH_QUESTION_KEYWORDS[question_key]
    corroboration = []
    for article in articles:
        text = article.get("preview_text", "")
        if not text:
            continue
        sentences = extract_relevant_sentences(text, pattern, n=2)
        if sentences:
            corroboration.append({
                "source_title": article.get("title", "Unknown"),
                "source_type": article.get("source_type", "unknown"),
                "url": article.get("url", ""),
                "supporting_quotes": sentences,
            })
    return corroboration


def summarize_research(articles):
    """Create research summary organized by topic and source type."""
    by_source_type = Counter(a.get("source_type", "unknown") for a in articles)
    by_topic = defaultdict(list)
    for article in articles:
        for topic in article.get("topics", []):
            by_topic[topic].append({
                "title": article.get("title", ""),
                "url": article.get("url", ""),
            })
    return {
        "total_articles": len(articles),
        "by_source_type": dict(by_source_type),
        "by_topic": dict(by_topic),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # Load unified reviews
    if not UNIFIED_PATH.exists():
        print(f"ERROR: {UNIFIED_PATH} not found.")
        print(f"Run parse_reviews.py first to generate output files in the output/ folder.")
        return

    # If categorised file already exists (manual or prior AI run), use it directly
    if CATEGORISED_PATH.exists():
        print(f"Found existing output/{CATEGORISED_PATH.name} — skipping tagging step.")
        with open(CATEGORISED_PATH, encoding="utf-8") as f:
            reviews = json.load(f)
        print(f"Loaded {len(reviews)} categorised reviews.")
    else:
        with open(UNIFIED_PATH, encoding="utf-8") as f:
            reviews = json.load(f)
        print(f"Loaded {len(reviews)} reviews from output/{UNIFIED_PATH.name}")

        api_key = os.environ.get("ANTHROPIC_API_KEY")

        print("\nStep 1: Categorising reviews...")
        if api_key and ANTHROPIC_AVAILABLE:
            print("  Claude API key found — using AI categorisation.")
            for idx, r in enumerate(reviews):
                r["_id"] = idx
            client = anthropic.Anthropic(api_key=api_key)
            categorised_map = batch_categorise(client, reviews)
            for r in reviews:
                tags = categorised_map.get(r["_id"], {})
                r["themes"] = tags.get("themes", [])
                r["discovery_related"] = tags.get("discovery_related", False)
                r["user_segment"] = tags.get("user_segment", "unknown")
                r["sentiment"] = tags.get("sentiment", "unknown")
                r["key_quote"] = tags.get("key_quote", "")
                del r["_id"]
        else:
            if api_key and not ANTHROPIC_AVAILABLE:
                print("  Note: ANTHROPIC_API_KEY set but 'anthropic' package not installed.")
                print("        Run: pip install anthropic  to enable AI tagging.")
            else:
                print("  No ANTHROPIC_API_KEY found.")
            keyword_tag_all(reviews)

        with open(CATEGORISED_PATH, "w", encoding="utf-8") as f:
            json.dump(reviews, f, ensure_ascii=False, indent=2)
        print(f"  Categorised reviews saved to output/{CATEGORISED_PATH.name}")

    # Step 2: Load research articles for corroboration
    print("\nStep 2: Loading research articles...")
    research_articles = load_research_compiled()
    if research_articles:
        print(f"  Found {len(research_articles)} compiled research articles — will corroborate answers.")
    else:
        print("  No compiled research found. Run fetch_research.py first for richer insights.")

    # Step 3: Aggregate insights with research corroboration
    print("\nStep 3: Aggregating insights...")
    insights = {
        "total_reviews_analysed": len(reviews),
        "source_breakdown": dict(Counter(r["source"] for r in reviews)),
        "questions": [
            answer_q1(reviews, research_articles),
            answer_q2(reviews, research_articles),
            answer_q3(reviews, research_articles),
            answer_q4(reviews, research_articles),
        ],
    }

    insights["research_backing"] = summarize_research(research_articles)

    with open(INSIGHTS_PATH, "w", encoding="utf-8") as f:
        json.dump(insights, f, ensure_ascii=False, indent=2)

    print(f"\nInsights report saved to output/{INSIGHTS_PATH.name}")
    print("\n--- QUICK SUMMARY ---")
    for q in insights["questions"]:
        print(f"\n{q['question']}")
        relevant_key = next((k for k in q if "total_relevant" in k), None)
        if relevant_key:
            print(f"  Relevant reviews : {q[relevant_key]}")
        if "top_quotes" in q and q["top_quotes"]:
            print(f"  Top quote        : \"{q['top_quotes'][0]}\"")
        corr = q.get("research_corroboration", [])
        print(f"  Research sources : {len(corr)} articles corroborate this")
        if corr:
            print(f"  Research quote   : \"{corr[0]['supporting_quotes'][0][:120]}\"")

    rb = insights.get("research_backing", {})
    if rb.get("total_articles"):
        print(f"\n--- RESEARCH BACKING ---")
        print(f"Total compiled articles: {rb['total_articles']}")
        for src_type, count in rb.get("by_source_type", {}).items():
            print(f"  {src_type}: {count}")


if __name__ == "__main__":
    main()
