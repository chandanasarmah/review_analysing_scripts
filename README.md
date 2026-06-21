# 🎵 Spotify Review Analyser

An AI-assisted pipeline that turns raw user reviews from multiple platforms into structured product insights, corroborated by external research. Built for a Product Manager Fellowship project on Spotify's music-discovery problem.

The pipeline ingests reviews from the **Apple App Store, Google Play Store, and Reddit**, normalises them into a single schema, tags each review with themes / sentiment / user segment, fetches supporting research from the web, and answers four product questions — then renders everything as an interactive dashboard and a self-contained HTML report.

---

## What it answers

1. **Why do users struggle to discover new music?**
2. **What causes repeat listening?**
3. **What are the most common recommendation frustrations?**
4. **Which user segments experience the most discovery challenges?**

Each answer combines **quantitative review breakdowns**, **representative user quotes**, and **supporting passages from independent research**.

---

## Pipeline

```
 raw review files (input/)
        │
        ▼
 parse_reviews.py      ──►  output/reviews_unified.json      (normalised schema)
        │
        ▼
 analyse_reviews.py    ──►  output/reviews_categorised.json  (themes, sentiment, segment)
        │                   output/insights_report.json      (the 4 answers + research)
        ▼
 fetch_research.py     ──►  output/research_compiled.json    (external research text)
        │
        ▼
 generate_report.py    ──►  output/report.html               (shareable report)
        │
        ▼
 app.py (Streamlit)    ──►  interactive dashboard
```

---

## Scripts

| Script | Purpose |
|--------|---------|
| `parse_reviews.py` | Parses 4 raw text files into one unified schema. Handles 3 date formats, multilingual text, duplicates, deleted comments, and developer responses with graceful fallbacks. |
| `analyse_reviews.py` | Tags each review (themes, sentiment, segment, key quote) and aggregates the 4 question answers. Works **offline** with keyword matching, or with the **Claude API** for richer tagging. |
| `fetch_research.py` | Fetches and extracts text from the URLs in `input/research_sources.json`. |
| `generate_report.py` | Builds a self-contained, styled `report.html` from the output files. |
| `app.py` | Streamlit dashboard with per-question tabs and a live review explorer. |

---

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Add your raw review files to input/  (see Schema below)

# 3. Run the pipeline
python parse_reviews.py
python fetch_research.py        # optional — needs internet
python analyse_reviews.py
python generate_report.py

# 4. View results
#    - open output/report.html in any browser, OR
streamlit run app.py
```

> On Windows, use `py` instead of `python` if the launcher is installed.

### Optional: Claude API tagging

By default, tagging uses offline keyword matching (no API key, no cost). For higher-accuracy tagging:

```bash
pip install anthropic
set ANTHROPIC_API_KEY=sk-ant-...      # Windows
export ANTHROPIC_API_KEY=sk-ant-...   # macOS/Linux
python analyse_reviews.py
```

You can also **manually edit** `output/reviews_categorised.json` — on the next run the script detects existing tags and skips re-tagging.

---

## Input schema

Place raw review text files in `input/`. The parser expects:

- **Apple App Store** — numbered reviews with `Rating: N★`, `Reviewer: name (time ago)`
- **Google Play Store** — `name` / `date` / `review text` / `Did you find this helpful?`
- **Reddit** — subreddit header, post title, body, upvotes, comments

Output records follow:

```json
{
  "source": "apple_ios | google_play | reddit",
  "rating": 5,                 // present only for Apple iOS
  "text": "the review body",
  "date": "2 years ago",
  "author": "username"
}
```

`input/research_sources.json` holds the list of public research URLs used by `fetch_research.py`.

---

## Project structure

```
.
├── parse_reviews.py
├── analyse_reviews.py
├── fetch_research.py
├── generate_report.py
├── app.py
├── requirements.txt
├── input/
│   └── research_sources.json   # public research URLs
└── output/                     # generated (git-ignored)
```

> **Note:** Raw review data and generated output are git-ignored — they contain reviewer names (PII) and are not committed. Bring your own data in `input/`.

---

## Features & limitations

**Features**
- Multi-platform ingestion into one schema
- Offline keyword tagging *or* Claude API tagging
- Manual tag overrides supported
- Research corroboration cross-referenced into each answer
- Cross-platform signal detection
- Duplicate filtering & graceful parse fallbacks
- Interactive dashboard + static HTML report

**Limitations**
- Google Play / Reddit reviews have no star rating — sentiment is inferred from text
- Keyword tagging is surface-level (misses sarcasm/context) unless the Claude API is used
- Relative dates ("2 years ago") can't be sorted chronologically
- Research fetching can fail on paywalled/bot-protected pages
- Flat-file storage; not optimised for very large datasets

---

## License

For educational / portfolio use.
