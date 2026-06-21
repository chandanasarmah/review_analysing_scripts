# Input File Format Reference

Place all raw review files in the `input/` folder before running the pipeline.

---

## 1. `apple ios.txt` — Apple App Store Reviews

### Required structure

Reviews must be numbered sequentially. Each review block must contain at minimum a number line and a body.

```
1. <Review title or first line>
Rating: 4★
Reviewer: John Doe (2 years ago)
This app used to be great but now the shuffle is broken...

2. <Review title>
Rating: 1★
Reviewer: Jane Smith
Date: 4 June 2025
I cancelled my subscription because of constant ads...
```

### Field rules

| Field | Format | Required |
|-------|--------|----------|
| Review number | `N.` at the start of a line | Yes — used to split blocks |
| Rating | `Rating: N★` or `Rating: N*` (1–5) | Optional — record still kept if missing |
| Reviewer | `Reviewer: Name (date string)` | Optional — falls back to `"unknown"` |
| Inline date | `(2 years ago)`, `(13 Apr)` appended to Reviewer line | One of the three date formats |
| Separate date | `Date: 4 June 2025` on the line after Reviewer | One of the three date formats |
| Body text | Any lines after the header fields | Yes — block skipped if empty |

### Accepted date formats

- Relative: `2 years ago`, `3 months ago`, `14 days ago`
- Short: `13 Apr`, `5 Jan`
- Full: `4 June 2025`, `14 March 2024`

### Automatically stripped / ignored

- Blocks labelled `Key Issues:` or `Positive Themes:` (summary sections)
- Lines starting with `-` or `•` immediately after those headers
- Any block where the body is empty after stripping

### Common issues

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Review count much lower than expected | Numbers not at the start of a line | Ensure each review starts with `N.` at column 0 |
| All authors show `"unknown"` | `Reviewer:` line missing or differently spelled | Check spelling — must be exactly `Reviewer:` |
| Ratings all `null` | Rating line uses a different star character | Use `★` (U+2605) or plain `*` after the number |

---

## 2. `google play store review.txt` — Google Play Store (Batch 1)

### Required structure

Reviews are separated by blank lines. Each block must have an author on line 1 and a date on line 2 (or close after).

```
Alice Johnson
August 29, 2025
The recommendation algorithm feels stuck in 2019. I keep hearing the same 20 songs.
3 people found this helpful
Did you find this helpful?

Bob Martinez
September 5, 2025
Great app overall but ads are way too long on the free tier.
Did you find this helpful?
```

### Field rules

| Field | Format | Required |
|-------|--------|----------|
| Author | First non-empty line of block | Yes — block skipped if it matches a noise keyword |
| Date | Must contain a recognisable month name (full or 3-letter) | Yes — block skipped if no date found |
| Body | Lines after the date line | Yes — block skipped if empty after stripping |

### Accepted date formats

- `August 29, 2025`
- `Sep 5, 2025`
- `Jun 20, 2025`

### Automatically stripped / ignored

- `Did you find this helpful?`
- `X people found this helpful` / `X person found this helpful`
- Developer response blocks starting with `Spotify AB`
- Metadata lines: `About this app`, `Ratings and reviews`, `Updated`, `Size`, `Content rating`, `In-app purchases`, `Privacy`, `Terms of service`
- Chat-format lines like `[1:35 pm, 20/06/2026] Chandana: …`
- Lines starting with `https://`
- Exact duplicate reviews (same author + date + first 50 characters)

### Common issues

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Large blocks skipped | Block starts with a metadata/noise keyword | Ensure the first line is the reviewer's name |
| Date shows `"unknown"` | Date line doesn't contain a month name | Reformat to `Month DD, YYYY` |
| Developer responses leaking into body | `Spotify AB` text not on its own line | Parser stops at first `Spotify AB` occurrence in a block |

---

## 3. `google playstore review 2.txt` — Google Play Store (Batch 2)

Same format as Batch 1 above. Additionally handles:

- **File header lines** (lines 1–8): metadata like `India (English)`, icon image lines, and chat-format lines are skipped automatically.
- **Multilingual content**: Arabic, Swedish, Marathi, emoji-heavy text — preserved as-is.
- **`[deleted]` entries**: skipped.
- **Very short reviews** (single word, emoji-only): parsed and kept — they are valid signals.

No additional format changes needed beyond what Batch 1 requires.

---

## 4. `reddit.txt` — Reddit Posts and Comments

### Required structure

Content is organised by subreddit. Each thread starts with a subreddit header line.

```
r/truespotify

Why does Spotify keep playing the same 10 songs?
Discussion
I switched to premium 6 months ago and my Discover Weekly has gotten progressively worse...
•
3d ago
username123
Upvote
42
Downvote

u/ReplyUser avatar
ReplyUser
•
1d ago
Same here — I tried resetting my taste profile and it made zero difference.
Upvote
18
Downvote

r/spotify

Shuffle is not actually random
...
```

### Field rules

| Field | Format | Required |
|-------|--------|----------|
| Subreddit header | Line starting with `r/truespotify` or `r/spotify` | Yes — used to detect thread boundaries |
| Post title | First non-empty line after the header | Yes |
| Flair | One-word flair like `Discussion`, `iOS`, `Rant` on its own line | Optional — skipped automatically |
| Post body | Lines between title/flair and the `•` separator | Optional — title alone used if body is empty |
| Timestamp | `Nd ago`, `Nmo ago`, `Ny ago` format | Optional — falls back to `"unknown"` |
| Author | Line after timestamp | Optional — falls back to `"unknown"` |
| Comment author | `u/Username avatar` line, or plain username matching `[A-Za-z0-9_-]{2,30}` followed by `•` and a timestamp | Yes — used to detect comment start |

### Automatically stripped / ignored

- `Promoted` posts and ad sections
- `[deleted]` and `Comment deleted by user` blocks
- `Upvote`, `Downvote`, `Reply`, `Share`, `Report` action lines
- Numeric-only lines (upvote counts)
- Profile badge lines
- Thumbnail / comment image lines
- `Go to truespotify` / `Go to spotify` navigation lines
- Lines starting with `https://`
- Spotify employee responses

### Common issues

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Zero Reddit records | Subreddit header format doesn't match | First line of each thread must be exactly `r/truespotify` or `r/spotify` |
| Comments not parsed | Comment author line doesn't match expected pattern | Author line must be a plain `username` (2–30 alphanumeric/underscore/hyphen chars) followed on the next lines by `•` and a timestamp |
| Post body empty | Body starts after a flair line the parser doesn't recognise | Add the flair to the `REDDIT_FLAIRS` set in `parse_reviews.py` |

---

## Output schema

All records, regardless of source, are written to `output/reviews_unified.json` in this schema:

```json
{
  "source": "apple_ios | google_play | reddit",
  "rating": 4,
  "text": "review body text",
  "date": "2 years ago",
  "author": "username"
}
```

- `rating` is only present for Apple iOS records (1–5 integer).
- `date` is stored as-is (relative or absolute string — not parsed to a datetime).
- `author` falls back to `"unknown"` if not extractable.
- Records with an empty `text` after stripping are always skipped.

Skipped and malformed records are logged to `output/parse_log.txt` with a reason and source context.

---

## Minimum viable file sizes

The pipeline will warn if a file produces fewer records than expected:

| File | Minimum expected records |
|------|--------------------------|
| `apple ios.txt` | 10 |
| `google play store review.txt` | 30 |
| `google playstore review 2.txt` | 50 |
| `reddit.txt` | 10 |

If a file falls below its threshold, check `output/parse_log.txt` for skipped-block reasons.
