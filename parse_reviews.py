import re
import json
from pathlib import Path

BASE = Path(__file__).parent
INPUT = BASE / "input"
OUTPUT = BASE / "output"
OUTPUT.mkdir(exist_ok=True)

LOG_LINES = []

MONTH_PATTERN = (
    r"(January|February|March|April|May|June|July|August|September|"
    r"October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
)

NOISE_LINES = {
    "about this app", "spotify: music and podcasts", "ratings and reviews",
    "india (english)", "icon image", "did you find this helpful?",
    "play pass", "play points", "gift cards", "redeem", "refund policy",
    "updated", "size", "content rating", "in-app purchases",
    "privacy", "terms of service", "about google play",
}

REDDIT_FLAIRS = {"ios", "rant", "question", "discussion", "help", "bug", "feedback", "suggestion"}

REDDIT_SKIP_LINES = {
    "upvote", "downvote", "reply", "share", "report", "save",
    "go to comments", "go to truespotify", "go to spotify",
    "promoted", "spotify employee",
}


def log(msg):
    LOG_LINES.append(msg)


def is_noise(line):
    return line.strip().lower() in NOISE_LINES


def strip_key_issues_section(text):
    """Remove 'Key Issues:' and 'Positive Themes:' summary blocks."""
    lines = text.splitlines()
    out = []
    in_summary = False
    for line in lines:
        stripped = line.strip()
        if re.match(r"^(Key Issues|Positive Themes)\s*:", stripped, re.IGNORECASE):
            in_summary = True
            continue
        if in_summary:
            if stripped.startswith(("-", "•", "*")) or stripped == "":
                continue
            else:
                in_summary = False
        out.append(line)
    return "\n".join(out).strip()


# ---------------------------------------------------------------------------
# Parser 1: Apple iOS
# ---------------------------------------------------------------------------

def parse_apple(filepath):
    records = []
    try:
        text = Path(filepath).read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        log(f"[apple] File not found: {filepath}")
        return records

    blocks = re.split(r"\n(?=\d+\.\s)", text)

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        # Rating
        rating = None
        m = re.search(r"Rating:\s*(\d)[★*]?", block)
        if m:
            rating = int(m.group(1))

        # Author + date
        author = "unknown"
        date = "unknown"
        reviewer_match = re.search(r"Reviewer:\s*(.+)", block)
        if reviewer_match:
            reviewer_line = reviewer_match.group(1).strip()
            # Format 1: "Name (date string)"
            inline = re.match(r"^(.+?)\s+\((.+?)\)\s*$", reviewer_line)
            if inline:
                author = inline.group(1).strip()
                date = inline.group(2).strip()
            else:
                # Format 3: separate Date: line
                author = reviewer_line
                date_match = re.search(r"Date:\s*(.+)", block)
                if date_match:
                    date = date_match.group(1).strip()
                else:
                    log(f"[apple] No date found for author '{author}'")

        # Clean text: remove header lines
        lines = block.splitlines()
        body_lines = []
        skip_next_if_date = False
        for line in lines:
            s = line.strip()
            if re.match(r"^\d+\.\s", s):
                continue  # review number + title line
            if re.match(r"Rating:\s*\d", s):
                continue
            if re.match(r"Reviewer:\s*", s):
                skip_next_if_date = True
                continue
            if skip_next_if_date and re.match(r"Date:\s*", s):
                skip_next_if_date = False
                continue
            skip_next_if_date = False
            body_lines.append(line)

        body = strip_key_issues_section("\n".join(body_lines)).strip()

        if not body:
            log(f"[apple] Empty body for author '{author}', skipping")
            continue

        record = {"source": "apple_ios", "text": body, "date": date, "author": author}
        if rating is not None:
            record["rating"] = rating
        records.append(record)

    return records


# ---------------------------------------------------------------------------
# Parser 2: Google Play Store
# ---------------------------------------------------------------------------

def parse_google_play(filepath, source_label="google_play"):
    records = []
    try:
        text = Path(filepath).read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        log(f"[google_play] File not found: {filepath}")
        return records

    seen = set()
    blocks = re.split(r"\n\s*\n", text)

    for block in blocks:
        lines = [l for l in block.splitlines() if l.strip()]
        if len(lines) < 2:
            continue

        # Skip blocks that are clearly metadata/noise
        first = lines[0].strip()
        if is_noise(first):
            continue
        if re.match(r"^\[", first):  # chat-format line like [1:35 pm, ...]
            continue
        if re.match(r"^https?://", first):
            continue

        # Skip Spotify AB developer response blocks
        if any("Spotify AB" in l for l in lines[:2]):
            continue

        # Line 0 = author candidate
        author = first
        if is_noise(author.lower()):
            continue

        # Line 1 = date candidate
        date = "unknown"
        text_start = 1
        for i, line in enumerate(lines[1:], start=1):
            if re.search(MONTH_PATTERN, line):
                date = line.strip()
                text_start = i + 1
                break

        if date == "unknown":
            log(f"[google_play] No date for author '{author}', skipping block")
            continue

        # Body: remaining lines after date
        body_lines = []
        for line in lines[text_start:]:
            s = line.strip()
            if s.lower() == "did you find this helpful?":
                continue
            if re.match(r"^\d[\d,]* pe(ople|rson)", s, re.IGNORECASE):
                continue
            if "Spotify AB" in s:
                break  # developer response starts — stop
            if is_noise(s.lower()):
                continue
            body_lines.append(line)

        body = " ".join(body_lines).strip()
        body = re.sub(r"\s+", " ", body)

        if not body:
            log(f"[google_play] Empty body for author '{author}', skipping")
            continue

        # Deduplicate
        key = (author, date, body[:50])
        if key in seen:
            log(f"[google_play] Duplicate skipped: author='{author}' date='{date}'")
            continue
        seen.add(key)

        records.append({"source": source_label, "text": body, "date": date, "author": author})

    return records


# ---------------------------------------------------------------------------
# Parser 3: Reddit
# ---------------------------------------------------------------------------

def parse_reddit(filepath):
    records = []
    try:
        text = Path(filepath).read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        log(f"[reddit] File not found: {filepath}")
        return records

    lines = text.splitlines()
    i = 0
    n = len(lines)

    def is_timestamp(s):
        return bool(re.match(r"^\d+(d|mo|y)\s+ago$", s.strip()))

    def is_upvote_line(s):
        s = s.strip().lower()
        return s in ("upvote", "downvote", "reply", "share", "report") or re.match(r"^\d+$", s)

    def clean_author(s):
        s = re.sub(r"^u/", "", s.strip())
        s = re.sub(r"\s*avatar$", "", s, flags=re.IGNORECASE)
        s = re.sub(r"\s*(OP|Promoted|Spotify employee)$", "", s, flags=re.IGNORECASE)
        return s.strip() or "unknown"

    def collect_body(start, end):
        """Collect text lines between start and end indices, skipping noise."""
        body_lines = []
        in_deleted = False
        for j in range(start, min(end, n)):
            s = lines[j].strip()
            if s in ("[deleted]", "Comment deleted by user"):
                in_deleted = True
                continue
            if in_deleted:
                if s == "" or is_upvote_line(s):
                    in_deleted = False
                continue
            if is_upvote_line(s):
                continue
            if s.lower() in REDDIT_SKIP_LINES:
                continue
            if re.match(r"^Profile Badge", s):
                continue
            if re.match(r"^Thumbnail image", s):
                continue
            if re.match(r"^Comment Image", s):
                continue
            if re.match(r"^https?://", s):
                continue
            body_lines.append(s)
        return " ".join(body_lines).strip()

    while i < n:
        line = lines[i].strip()

        # Detect subreddit header
        if re.match(r"^r/(truespotify|spotify)\b", line, re.IGNORECASE) or \
           re.match(r"^Go to (truespotify|spotify)\b", line, re.IGNORECASE):

            # Skip promoted sections
            peek = " ".join(lines[i:i+6]).lower()
            if "promoted" in peek:
                i += 1
                continue

            i += 1
            # Skip "Go to X" navigation lines
            while i < n and re.match(r"^(Go to|r/)", lines[i].strip(), re.IGNORECASE):
                i += 1

            # Post title
            if i >= n:
                break
            title = lines[i].strip()
            i += 1

            # Skip flair line
            if i < n and lines[i].strip().lower() in REDDIT_FLAIRS:
                i += 1

            # Collect post body until bullet separator or timestamp
            body_start = i
            while i < n:
                s = lines[i].strip()
                if s == "•" and i + 1 < n and is_timestamp(lines[i + 1].strip()):
                    break
                if is_timestamp(s):
                    break
                i += 1

            post_body = collect_body(body_start, i)
            full_text = (title + " " + post_body).strip() if title else post_body

            # Date
            post_date = "unknown"
            if i < n and lines[i].strip() == "•":
                i += 1
            if i < n and is_timestamp(lines[i].strip()):
                post_date = lines[i].strip()
                i += 1

            # Author (line after timestamp, skip noise)
            post_author = "unknown"
            while i < n:
                candidate = lines[i].strip()
                if candidate == "" or is_upvote_line(candidate) or \
                   candidate.lower() in REDDIT_SKIP_LINES or \
                   re.match(r"^(Go to|r/)", candidate, re.IGNORECASE):
                    i += 1
                    continue
                post_author = clean_author(candidate)
                i += 1
                break

            if full_text:
                records.append({
                    "source": "reddit",
                    "text": full_text,
                    "date": post_date,
                    "author": post_author,
                })
            else:
                log(f"[reddit] Empty post body for title '{title}', skipping")

            # Now collect comments until next subreddit header
            while i < n:
                s = lines[i].strip()
                if re.match(r"^(Go to|r/)(truespotify|spotify)", s, re.IGNORECASE):
                    break  # next post starts
                if re.match(r"^r/(truespotify|spotify)\b", s, re.IGNORECASE):
                    break

                # Detect comment: "u/username avatar" or username + bullet + timestamp pattern
                is_u_prefix = re.match(r"^u/\S+", s)
                if is_u_prefix or (
                    re.match(r"^[A-Za-z0-9_\-]{2,30}$", s) and
                    i + 2 < n and
                    lines[i + 1].strip() == "•" and
                    is_timestamp(lines[i + 2].strip())
                ):
                    # Skip promoted / deleted
                    if s.lower() == "promoted":
                        i += 1
                        continue
                    if s in ("[deleted]", "Comment deleted by user"):
                        i += 1
                        continue

                    comment_author = clean_author(s)
                    # If "u/X avatar" format, next line might be the plain username
                    if is_u_prefix and i + 1 < n and re.match(r"^[A-Za-z0-9_\-]{2,30}$", lines[i+1].strip()):
                        i += 1
                        comment_author = clean_author(lines[i].strip())

                    i += 1
                    # Skip bullet
                    if i < n and lines[i].strip() == "•":
                        i += 1
                    # Timestamp
                    comment_date = "unknown"
                    if i < n and is_timestamp(lines[i].strip()):
                        comment_date = lines[i].strip()
                        i += 1

                    # Skip badge/edited lines
                    while i < n and (
                        re.match(r"^Profile Badge", lines[i].strip()) or
                        re.match(r"^Edited", lines[i].strip()) or
                        lines[i].strip().lower() == "op"
                    ):
                        i += 1

                    # Collect comment body
                    body_start = i
                    while i < n:
                        s2 = lines[i].strip()
                        if s2 == "•" and i + 1 < n and is_timestamp(lines[i + 1].strip()):
                            break
                        if re.match(r"^u/\S+", s2):
                            break
                        if re.match(r"^[A-Za-z0-9_\-]{2,30}$", s2) and \
                           i + 2 < n and lines[i+1].strip() == "•" and \
                           is_timestamp(lines[i+2].strip()):
                            break
                        if re.match(r"^(Go to|r/)(truespotify|spotify)", s2, re.IGNORECASE):
                            break
                        i += 1

                    comment_body = collect_body(body_start, i)

                    if comment_body and comment_body not in ("[deleted]", "Comment deleted by user"):
                        records.append({
                            "source": "reddit",
                            "text": comment_body,
                            "date": comment_date,
                            "author": comment_author,
                        })
                    else:
                        if not comment_body:
                            log(f"[reddit] Empty comment by '{comment_author}' at line {body_start}, skipping")
                else:
                    i += 1

        else:
            i += 1

    return records


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    all_reviews = []

    all_reviews += parse_apple(INPUT / "apple ios.txt")
    all_reviews += parse_google_play(INPUT / "google play store review.txt", "google_play")
    all_reviews += parse_google_play(INPUT / "google playstore review 2.txt", "google_play")
    all_reviews += parse_reddit(INPUT / "reddit.txt")

    out_path = OUTPUT / "reviews_unified.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_reviews, f, ensure_ascii=False, indent=2)

    log_path = OUTPUT / "parse_log.txt"
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("\n".join(LOG_LINES))

    from collections import Counter
    sources = Counter(r["source"] for r in all_reviews)
    has_rating = sum(1 for r in all_reviews if "rating" in r)

    print(f"Total records: {len(all_reviews)}")
    print(f"By source:     {dict(sources)}")
    print(f"With rating:   {has_rating}")
    print(f"Skipped/logged: {len(LOG_LINES)} entries")
    print(f"\nFiles saved to: {OUTPUT}")
    print(f"  - {out_path.name}")
    print(f"  - {log_path.name}")


if __name__ == "__main__":
    main()
