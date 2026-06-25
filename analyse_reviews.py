"""
analyse_reviews.py

Reads reviews_unified.json and produces insights_report.json answering:
  1. Why do users struggle to discover new music?
  2. What causes repeat listening?
  3. What are recommendation frustrations?
  4. Which segments suffer most?

Three modes (checked in order):
  1. OpenCode AI (open-source models, recommended):
       pip install openai
       set OPENCODE_API_KEY=your_key
       python analyse_reviews.py

  2. Claude API (Anthropic):
       pip install anthropic
       set ANTHROPIC_API_KEY=sk-ant-...
       python analyse_reviews.py

  3. Keyword-based fallback (default, no API needed):
       python analyse_reviews.py

If reviews_categorised.json already exists with manual/AI tags, those tags are
used directly and the tagging step is skipped entirely.
"""

import argparse
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

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# OpenCode AI config — reads from st.secrets (Streamlit) first, then env vars
def _get_secret(key, default=""):
    try:
        import streamlit as st
        return st.secrets.get(key, os.environ.get(key, default))
    except Exception:
        return os.environ.get(key, default)

OPENCODE_API_KEY  = _get_secret("OPENCODE_API_KEY")
OPENCODE_BASE_URL = _get_secret("OPENCODE_BASE_URL", "https://opencode.ai/zen/go/v1")
OPENCODE_MODEL    = _get_secret("OPENCODE_MODEL",    "deepseek-v4-flash")

BASE = Path(__file__).parent
INPUT = BASE / "input"
OUTPUT = BASE / "output"
OUTPUT.mkdir(exist_ok=True)

UNIFIED_PATH = OUTPUT / "reviews_unified.json"
CATEGORISED_PATH = OUTPUT / "reviews_categorised.json"
INSIGHTS_PATH = OUTPUT / "insights_report.json"
RESEARCH_SOURCES_PATH = INPUT / "research_sources.json"
RESEARCH_COMPILED_PATH = OUTPUT / "research_compiled.json"
RESEARCH_COMPILED_INPUT_PATH = INPUT / "research_compiled.json"

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

# Spotify's official 6 audience segments (adapted for review-text detection)
SEGMENTS = [
    "super_listener",       # power user — Wrapped, Blend, Discover Weekly, years of use
    "moderate_listener",    # regular user — playlists, liked songs, daily use
    "light_listener",       # new/occasional — just installed, trying out
    "previously_active",    # lapsed — used to, cancelled, switched, deleted
    "programmed_listener",  # passive — autoplay, radio, algorithmic, shuffle-dependent
    "free_tier_user",       # ad-exposed — ads, free version, can't skip, no premium
]

CATEGORISE_PROMPT = """You are analyzing Spotify user reviews for a product manager research project.

For each review in the JSON array below, return a JSON array with one object per review containing:
- "id": same integer id as in the input
- "themes": list of relevant themes from ONLY these options: {themes}
- "discovery_related": true if the review mentions music discovery, new music, recommendations, or repeat listening; false otherwise
- "user_segment": classify into exactly ONE of these 6 Spotify audience segments:
    "super_listener"       — power user; mentions Wrapped, Discover Weekly, Blend, Daily Mix, Release Radar, Daylist, been using for years, family/student/duo plan
    "moderate_listener"    — regular user; mentions playlists, liked songs, library, listens daily or often, favourite artists
    "light_listener"       — new or occasional user; just downloaded, first time, new to Spotify, trying it out, recently switched
    "previously_active"    — lapsed user; used to love it, cancelled, uninstalled, switched to Apple Music/Tidal/YouTube Music, miss the old Spotify
    "programmed_listener"  — passive listener; relies on autoplay, radio, shuffle, the algorithm; background listening while working/studying/commuting
    "free_tier_user"       — non-paying user; frustrated by ads, can't skip, shuffle-only, wants premium features without paying
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

# Rules checked in priority order — first match wins
SEGMENT_RULES = {
    # Previously active: explicit lapsed signals take highest priority
    "previously_active": re.compile(
        r"\b(used to|used to love|cancel+ed|cancell?ing|uninstall|deleted|switched|"
        r"left spotify|moved to|going to apple|going to tidal|miss the old|downgrade|"
        r"gave up|stopped using|no longer|quit spotify|leaving)\b", re.I),

    # Free tier: ad/limitation signals
    "free_tier_user": re.compile(
        r"\b(free|ad|ads|advert|can'?t skip|shuffle only|limited|free plan|free account|"
        r"without premium|non.?premium|ad.?free|too many ads|ad supported|trial|free tier|"
        r"free version|free user|no premium)\b", re.I),

    # Super listener: deep engagement signals — Spotify-specific features, long tenure
    "super_listener": re.compile(
        r"\b(wrapped|discover weekly|daily mix|release radar|blend|daylist|"
        r"on repeat|made for you|years|since \d{4}|long.?time|been using for|"
        r"power user|super fan|hardcore|obsessed|never leave|best app ever|"
        r"premium for years|family plan|student plan|duo plan)\b", re.I),

    # Programmed listener: passive, algorithm-dependent signals
    "programmed_listener": re.compile(
        r"\b(autoplay|auto.?play|radio|algorithmic|the algorithm|shuffle|"
        r"plays for me|let spotify|it picks|random|just plays|background|"
        r"while (i work|i study|working|studying|driving|commut|exercis|workout|running))\b", re.I),

    # Light listener: new/occasional user signals
    "light_listener": re.compile(
        r"\b(just (downloaded|installed|started|tried|signed up|got)|new to|"
        r"first time|recently (switched|moved|joined|downloaded)|trying (out|it)|"
        r"gave it a try|first impression|just (got|begin)|brand new)\b", re.I),

    # Moderate listener: regular but not power-user signals (broad, low-specificity — catches the rest)
    "moderate_listener": re.compile(
        r"\b(playlist|liked songs|library|saved|follow|album|artist|track|"
        r"listen (every day|daily|regularly|often)|use (every day|daily|all the time)|"
        r"my music|my playlist|my library|favourite|favorite)\b", re.I),
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

    segment = "moderate_listener"  # default — catches unclassified regular users
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
# OpenAI-protocol tagger (OpenCode AI / any OpenAI-compatible endpoint)
# ---------------------------------------------------------------------------

def batch_categorise_openai(client, reviews, batch_size=10):
    """Same as batch_categorise but uses OpenAI chat completions protocol."""
    categorised = {}
    total_batches = -(-len(reviews) // batch_size)

    for i in range(0, len(reviews), batch_size):
        batch = reviews[i: i + batch_size]
        batch_input = [{"id": r["_id"], "text": r["text"][:800]} for r in batch]

        prompt = CATEGORISE_PROMPT.format(
            themes=json.dumps(THEMES),
            segments=json.dumps(SEGMENTS),
            reviews=json.dumps(batch_input, ensure_ascii=False),
        )

        batch_num = i // batch_size + 1
        print(f"  Categorising batch {batch_num}/{total_batches} "
              f"({len(batch)} reviews) via {OPENCODE_MODEL} ...")

        for attempt in range(3):
            try:
                response = client.chat.completions.create(
                    model=OPENCODE_MODEL,
                    max_tokens=16384,
                    temperature=0.1,
                    messages=[
                        {"role": "system", "content": "You are a JSON-only response bot. Return only valid JSON arrays, no markdown, no explanation."},
                        {"role": "user",   "content": prompt},
                    ],
                )
                raw = (response.choices[0].message.content or "").strip()
                # Strip DeepSeek <think>...</think> reasoning block and markdown fences
                raw = re.sub(r"<think>[\s\S]*?</think>", "", raw).strip()
                raw = re.sub(r"^```[a-z]*\n?", "", raw)
                raw = re.sub(r"\n?```$", "", raw)
                # Find the JSON array start in case there's stray text
                bracket = raw.find("[")
                if bracket > 0:
                    raw = raw[bracket:]
                results = json.loads(raw)
                for item in results:
                    categorised[item["id"]] = item
                print(f"    batch {batch_num}: {len(results)} records tagged OK")
                break
            except (json.JSONDecodeError, KeyError, IndexError) as e:
                print(f"    Attempt {attempt + 1} failed: {e}")
                if attempt == 2:
                    print("    Giving up on this batch — falling back to keyword tags")
                time.sleep(2)
            except Exception as e:
                print(f"    API error attempt {attempt + 1}: {e}")
                if attempt == 2:
                    print("    Giving up on this batch — falling back to keyword tags")
                time.sleep(5)

    return categorised


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------

def top_quotes(records, n=5, min_words=10, max_chars=500):
    """Return n full review texts — capped at max_chars, filtered for length, deduped."""
    seen = set()
    quotes = []
    # Prefer mid-length reviews (between 15–200 words) — long enough to be meaningful,
    # short enough to be readable. Sort by proximity to 80 words as the sweet spot.
    def _sort_key(r):
        wc = len(r.get("text", "").split())
        return -abs(wc - 80)   # closest to 80 words wins

    candidates = sorted(records, key=_sort_key)
    for r in candidates:
        text = r.get("text", "").strip()
        if len(text.split()) < min_words:
            continue
        # Cap long reviews with an ellipsis
        display = text if len(text) <= max_chars else text[:max_chars].rsplit(" ", 1)[0] + "…"
        norm = text[:200].lower()
        if norm in seen:
            continue
        seen.add(norm)
        quotes.append(display)
        if len(quotes) >= n:
            break
    return quotes


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
             "recommendation_quality" in r.get("themes", [])],
            n=8,
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
        "top_quotes": top_quotes(relevant, n=8),
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
        "top_quotes": top_quotes(relevant, n=8),
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
        count = len(seg_records)
        neg = sentiment_dist.get("negative", 0)
        segment_summary[seg] = {
            "review_count": count,
            "negative_count": neg,
            "negative_rate": round(neg / count, 4) if count else 0.0,
            "sentiment": dict(sentiment_dist),
            "top_themes": dict(top_themes.most_common(5)),
        }

    # ── "Most affected" methodology (Growth PM) ──────────────────────────
    # Volume just rewards the biggest bucket — and moderate_listener is the
    # unclassified catch-all (default in keyword tagging), so it drowns out
    # every real signal. Instead:
    #   1. Rank by NEGATIVE RATE (comparable pain intensity, not raw count)
    #   2. Require a sample floor (n >= MIN_N) so tiny segments can't win on noise
    #   3. Exclude the unclassified fallback bucket from eligibility
    #   4. Tie-break / prioritise the top contenders by Growth lever value
    MIN_N = 200
    # Segments excluded from the "most affected" ranking:
    #   moderate_listener is the keyword-tagging fallback bucket (~81% of reviews),
    #   so it represents a measurement gap, not a real audience.
    EXCLUDED_SEGMENTS = {"moderate_listener", "unknown"}
    GROWTH_RELEVANCE = {
        "previously_active": 1.0,   # churned — highest priority to win back
        "free_tier_user":    0.9,   # conversion blocker → direct revenue impact
        "super_listener":    0.6,   # retention risk for best users
        "light_listener":    0.5,   # activation drop-off
        "programmed_listener": 0.3, # passive, least strategic
    }

    eligible = {
        seg: data for seg, data in segment_summary.items()
        if seg not in EXCLUDED_SEGMENTS and data["review_count"] >= MIN_N
    }
    pool = eligible or {
        seg: data for seg, data in segment_summary.items()
        if seg not in EXCLUDED_SEGMENTS
    } or segment_summary

    # Among credibly-sized segments the top few are near-tied on negative rate,
    # so the decision comes from pain intensity + Growth value + real reach:
    #   55% pain rate (normalised), 25% Growth lever, 20% real volume (normalised).
    # Volume is normalised *within the eligible pool* and capped at 20% so it
    # informs the tie-break without letting the biggest bucket dominate again.
    _max_rate = max((d["negative_rate"] for d in pool.values()), default=1) or 1
    _max_n    = max((d["review_count"]  for d in pool.values()), default=1) or 1
    def _score(seg, data):
        rate_n = data["negative_rate"] / _max_rate
        grw    = GROWTH_RELEVANCE.get(seg, 0.3)
        vol_n  = data["review_count"] / _max_n
        return 0.55 * rate_n + 0.25 * grw + 0.20 * vol_n

    worst = max(
        pool.items(),
        key=lambda kv: _score(kv[0], kv[1]),
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


BEHAVIOR_PATTERNS = {
    "focus_work_study":   re.compile(r"\b(study|studying|work|working|focus|concentrate|homework|office|coding|writing|reading)\b", re.I),
    "workout_exercise":   re.compile(r"\b(workout|gym|run|running|exercise|training|jogging|cycling|fitness|sport)\b", re.I),
    "background_ambient": re.compile(r"\b(background|ambient|chill|relax|relaxing|sleep|sleeping|meditation|calm|unwind|lounge|white noise)\b", re.I),
    "commute_travel":     re.compile(r"\b(commute|commuting|drive|driving|car|travel|traveling|road trip|bus|train|subway)\b", re.I),
    "mood_emotional":     re.compile(r"\b(mood|feel|emotional|sad|happy|motivated|inspired|vibe|feeling|emotion|therapy)\b", re.I),
    "social_party":       re.compile(r"\b(party|social|friends|gathering|pregame|dinner|event|together)\b", re.I),
}

UNMET_KW = re.compile(
    r"\b(wish|want|need|missing|miss|feature|bring back|used to|should|can'?t|unable|"
    r"why not|please add|hope|request|improve|better|fix|would love|lacks|lack of|no option)\b",
    re.I,
)


def answer_q5(records, research_articles):
    """What listening behaviors are users trying to achieve?"""
    behavior_counts: Counter = Counter()
    behavior_examples: dict = {b: [] for b in BEHAVIOR_PATTERNS}

    for r in records:
        text = r.get("text", "")
        matched = False
        for behavior, pat in BEHAVIOR_PATTERNS.items():
            if pat.search(text):
                behavior_counts[behavior] += 1
                if len(behavior_examples[behavior]) < 20:
                    behavior_examples[behavior].append(r)
                matched = True
        if not matched:
            behavior_counts["general_listening"] = behavior_counts.get("general_listening", 0) + 1

    # Build per-behavior sentiment
    behavior_sentiment = {}
    for b, examples in behavior_examples.items():
        if examples:
            sent = Counter(r.get("sentiment", "unknown") for r in examples)
            behavior_sentiment[b] = dict(sent)

    relevant = [r for r in records if any(pat.search(r.get("text", "")) for pat in BEHAVIOR_PATTERNS.values())]
    return {
        "question": "What listening behaviors are users trying to achieve?",
        "total_relevant_reviews": len(relevant),
        "theme_frequency": dict(behavior_counts.most_common()),
        "behavior_sentiment": behavior_sentiment,
        "top_quotes": top_quotes(relevant, n=8),
        "research_corroboration": corroborate_with_research(research_articles, "q5_behaviors"),
    }


def answer_q6(records, research_articles):
    """What unmet needs emerge consistently across reviews?"""
    relevant = [r for r in records if UNMET_KW.search(r.get("text", "")) and r.get("sentiment") != "positive"]
    theme_counts = Counter(t for r in relevant for t in r.get("themes", []))
    sentiment_counts = Counter(r.get("sentiment", "unknown") for r in relevant)
    sources_present = {r["source"] for r in relevant}
    cross_platform = len(sources_present) >= 2
    return {
        "question": "What unmet needs emerge consistently across reviews?",
        "total_relevant_reviews": len(relevant),
        "theme_frequency": dict(theme_counts.most_common()),
        "sentiment_breakdown": dict(sentiment_counts),
        "cross_platform_signal": cross_platform,
        "platforms_with_complaint": list(sources_present),
        "top_quotes": top_quotes(relevant, n=8),
        "research_corroboration": corroborate_with_research(research_articles, "q6_unmet"),
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
    "q5_behaviors": re.compile(
        r"\b(study|work|focus|workout|gym|run|sleep|background|commute|travel|mood|"
        r"party|social|morning|chill|relax|meditation|drive|cook|concentrate)\b",
        re.I
    ),
    "q6_unmet": re.compile(
        r"\b(wish|want|need|missing|feature|bring back|used to|should|can'?t|unable|"
        r"why not|please add|hope|request|improve|better|fix)\b",
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
    """Load compiled research articles. Prefers output/ fresh fetch; falls back to input/ committed copy."""
    path = RESEARCH_COMPILED_PATH if RESEARCH_COMPILED_PATH.exists() else RESEARCH_COMPILED_INPUT_PATH
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--classifier", choices=["ai", "keyword"], default="ai",
                        help="ai: use OpenCode/Anthropic API; keyword: fast rule-based tagging")
    args, _ = parser.parse_known_args()
    use_ai_classifier = args.classifier == "ai"

    # Load unified reviews
    if not UNIFIED_PATH.exists():
        print(f"ERROR: {UNIFIED_PATH} not found.")
        print(f"Run parse_reviews.py first to generate output files in the output/ folder.")
        return

    # Use cached categorised file only if it is newer than the unified file.
    # If reviews_unified.json was regenerated (more/fewer reviews), re-tag.
    use_cache = (
        CATEGORISED_PATH.exists() and
        CATEGORISED_PATH.stat().st_mtime >= UNIFIED_PATH.stat().st_mtime
    )
    if use_cache:
        print(f"Found existing output/{CATEGORISED_PATH.name} — skipping tagging step.")
        with open(CATEGORISED_PATH, encoding="utf-8") as f:
            reviews = json.load(f)
        print(f"Loaded {len(reviews)} categorised reviews.")
    else:
        with open(UNIFIED_PATH, encoding="utf-8") as f:
            reviews = json.load(f)
        print(f"Loaded {len(reviews)} reviews from output/{UNIFIED_PATH.name}")


        anthropic_key = os.environ.get("ANTHROPIC_API_KEY")

        print("\nStep 1: Categorising reviews...")

        if not use_ai_classifier:
            print("  Classifier mode: keyword segments (fast rule-based tagging).")
            keyword_tag_all(reviews)

        elif OPENCODE_API_KEY and OPENAI_AVAILABLE:
            # ── OpenCode AI path (open-source models, OpenAI protocol) ────────
            print(f"  Classifier mode: AI — using {OPENCODE_MODEL} via OpenCode AI.")
            print(f"  Endpoint: {OPENCODE_BASE_URL}")
            for idx, r in enumerate(reviews):
                r["_id"] = idx
            client = OpenAI(api_key=OPENCODE_API_KEY, base_url=OPENCODE_BASE_URL)
            categorised_map = batch_categorise_openai(client, reviews)
            for r in reviews:
                tags = categorised_map.get(r["_id"], {})
                if tags:
                    r["themes"]           = tags.get("themes", [])
                    r["discovery_related"]= tags.get("discovery_related", False)
                    r["user_segment"]     = tags.get("user_segment", "moderate_listener")
                    r["sentiment"]        = tags.get("sentiment", "mixed")
                    r["key_quote"]        = tags.get("key_quote", "")
                else:
                    r.update(keyword_tag(r))
                del r["_id"]

        elif OPENCODE_API_KEY and not OPENAI_AVAILABLE:
            print("  Note: OPENCODE_API_KEY is set but 'openai' package not installed.")
            print("        Run: pip install openai   to enable OpenCode AI tagging.")
            keyword_tag_all(reviews)

        elif anthropic_key and ANTHROPIC_AVAILABLE:
            # ── Anthropic Claude path ─────────────────────────────────────────
            print("  Classifier mode: AI — using Claude API.")
            for idx, r in enumerate(reviews):
                r["_id"] = idx
            client = anthropic.Anthropic(api_key=anthropic_key)
            categorised_map = batch_categorise(client, reviews)
            for r in reviews:
                tags = categorised_map.get(r["_id"], {})
                r["themes"]           = tags.get("themes", [])
                r["discovery_related"]= tags.get("discovery_related", False)
                r["user_segment"]     = tags.get("user_segment", "moderate_listener")
                r["sentiment"]        = tags.get("sentiment", "mixed")
                r["key_quote"]        = tags.get("key_quote", "")
                del r["_id"]

        else:
            # ── Keyword fallback ──────────────────────────────────────────────
            print("  No API key found — falling back to keyword-based tagging.")
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
            answer_q5(reviews, research_articles),
            answer_q6(reviews, research_articles),
        ],
    }

    # Deduplicate quotes across all questions — no quote should appear in more than one Q
    _seen_quotes: set = set()
    for _q in insights["questions"]:
        for _key in ("top_quotes", "evidence_quotes"):
            if _key in _q:
                _unique = []
                for _quote in _q[_key]:
                    _norm = _quote.lower().strip()
                    if _norm not in _seen_quotes:
                        _seen_quotes.add(_norm)
                        _unique.append(_quote)
                _q[_key] = _unique

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
