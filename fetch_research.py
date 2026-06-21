"""
fetch_research.py

Fetches content from input/research_sources.json and compiles all articles
into structured files for the review analysis pipeline.

This integrates with:
  - analyse_reviews.py: Uses research_compiled.json to back up review insights
  - app.py: Serves research data in the Streamlit dashboard

Requirements: pip install requests beautifulsoup4

Usage:
    python fetch_research.py

Outputs:
  - output/research_compiled.json (JSON format for Python analysis)
  - output/RESEARCH_ARTICLES_FULL.txt (Human-readable text)
"""

import json
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, List

BASE = Path(__file__).parent
INPUT = BASE / "input"
OUTPUT = BASE / "output"

# Ensure output folder exists
OUTPUT.mkdir(exist_ok=True)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}


def fetch_url_content(url: str) -> str:
    """Fetch HTML content from URL."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"  [ERROR] Failed to fetch: {str(e)[:100]}")
        return ""


def extract_text_from_html(html: str) -> str:
    """Extract clean text from HTML."""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        text = soup.get_text()
        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        return text[:2000]  # Limit to first 2000 chars
    except ImportError:
        return html[:2000]
    except Exception as e:
        return ""


def fetch_and_compile():
    """Fetch all sources and compile into JSON file."""

    sources_path = INPUT / "research_sources.json"
    if not sources_path.exists():
        print(f"ERROR: {sources_path} not found")
        return

    with open(sources_path, encoding='utf-8') as f:
        sources_data = json.load(f)

    print("Fetching research sources...")
    print("=" * 80)

    compiled = {
        "metadata": {
            "fetched_at": datetime.now().isoformat(),
            "total_attempted": 0,
            "successful": 0,
            "failed": 0,
        },
        "articles": []
    }

    # Flatten all sources
    all_sources = []
    for cat in ["medium_articles", "substack_articles", "reddit_discussions",
                "spotify_official_forums", "spotify_research"]:
        if cat in sources_data:
            all_sources.extend(sources_data[cat])

    print(f"Found {len(all_sources)} sources to fetch\n")

    for i, source in enumerate(all_sources, 1):
        url = source.get("url", "")
        title = source.get("title", "Unknown")
        source_id = source.get("id", "")

        print(f"[{i}/{len(all_sources)}] {source_id}: {title[:60]}")
        compiled["metadata"]["total_attempted"] += 1

        # Fetch content
        html = fetch_url_content(url)
        if not html:
            compiled["metadata"]["failed"] += 1
            print(f"  [FAILED] Could not fetch")
            continue

        # Extract text
        text = extract_text_from_html(html)
        if not text:
            compiled["metadata"]["failed"] += 1
            print(f"  [FAILED] Could not extract text")
            continue

        compiled["metadata"]["successful"] += 1
        article = {
            "id": source_id,
            "title": title,
            "url": url,
            "source_type": source.get("source_type", "unknown"),
            "topics": source.get("topics", []),
            "preview_text": text,
        }
        if "author" in source:
            article["author"] = source["author"]
        if "date" in source:
            article["date"] = source["date"]
        if "subreddit" in source:
            article["subreddit"] = source["subreddit"]

        compiled["articles"].append(article)
        print(f"  [OK] Fetched successfully")

    print("\n" + "=" * 80)
    print(f"Results: {compiled['metadata']['successful']}/{compiled['metadata']['total_attempted']} successful")

    # Save compiled results
    output_path = OUTPUT / "research_compiled.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(compiled, f, ensure_ascii=False, indent=2)
    print(f"\nSaved to: {output_path}")

    # Also save as text file for manual review
    text_path = OUTPUT / "RESEARCH_ARTICLES_FULL.txt"
    with open(text_path, 'w', encoding='utf-8') as f:
        for article in compiled["articles"]:
            f.write(f"\n{'='*80}\n")
            f.write(f"TITLE: {article['title']}\n")
            f.write(f"SOURCE: {article.get('author', 'Unknown')} ({article['source_type']})\n")
            if "date" in article:
                f.write(f"DATE: {article['date']}\n")
            f.write(f"URL: {article['url']}\n")
            if article.get('topics'):
                f.write(f"TOPICS: {', '.join(article['topics'])}\n")
            f.write(f"\n{article['preview_text']}\n")
    print(f"Text version: {text_path}")


if __name__ == "__main__":
    try:
        fetch_and_compile()
        print("\n" + "=" * 80)
        print("NEXT STEPS:")
        print("  1. Run: python analyse_reviews.py")
        print("     This will integrate research data into insights_report.json")
        print("\n  2. View dashboard:")
        print("     py -m streamlit run app.py")
        print("=" * 80)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\nERROR: {e}")
