"""
Review Analysis Workflow — Streamlit App
PM Fellowship Final Project: Spotify Music Discovery

Left sidebar : upload input files (format auto-detected) + run controls.
Main area    : empty-state guide → loading screen → HTML report.
"""

import re
import subprocess
import sys
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

sys.path.insert(0, str(Path(__file__).parent))
from parse_reviews import validate_inputs

BASE       = Path(__file__).parent
INPUT_DIR  = BASE / "input"
OUTPUT_DIR = BASE / "output"
REPORT_HTML = OUTPUT_DIR / "report.html"

TYPE_LABEL = {
    "apple_ios":   "Apple iOS reviews",
    "google_play": "Google Play reviews",
    "reddit":      "Reddit posts",
}

# .txt files that live in input/ but are NOT review files
NON_REVIEW_FILES = {"RESEARCH_ARTICLES_FULL.txt"}

st.set_page_config(
    page_title="Spotify Review Analyser",
    page_icon="🎵",
    layout="wide",
)

st.markdown("""
<style>
  /* ── Global ─────────────────────────────────────────────────────────── */
  #MainMenu, header, footer { visibility: hidden; }
  [data-testid="stToolbar"]  { display: none; }
  .stApp           { background: #0b0e0f; }
  .block-container { padding-top: 1rem !important; }

  /* ── Sidebar shell ──────────────────────────────────────────────────── */
  section[data-testid="stSidebar"] {
    background: #0f1416 !important;
    border-right: 1px solid #1e2a2e;
  }
  section[data-testid="stSidebar"],
  section[data-testid="stSidebar"] p,
  section[data-testid="stSidebar"] span,
  section[data-testid="stSidebar"] label,
  section[data-testid="stSidebar"] div,
  section[data-testid="stSidebar"] small { color: #c8d8dc !important; }
  section[data-testid="stSidebar"] h1,
  section[data-testid="stSidebar"] h2,
  section[data-testid="stSidebar"] h3,
  section[data-testid="stSidebar"] strong { color: #e8eef0 !important; }

  /* ── Expander ───────────────────────────────────────────────────────── */
  section[data-testid="stSidebar"] [data-testid="stExpander"] {
    background: #000 !important;
    border: 1px solid #1DB954 !important;
    border-radius: 6px !important;
  }
  section[data-testid="stSidebar"] [data-testid="stExpander"] summary,
  section[data-testid="stSidebar"] [data-testid="stExpander"] summary p,
  section[data-testid="stSidebar"] [data-testid="stExpander"] summary span {
    background: #000 !important; color: #1DB954 !important; font-weight: 700 !important;
  }
  section[data-testid="stSidebar"] [data-testid="stExpander"] summary:hover,
  section[data-testid="stSidebar"] [data-testid="stExpander"] summary:hover span { color: #17a349 !important; }
  section[data-testid="stSidebar"] [data-testid="stExpander"] > div { background: #000 !important; }
  section[data-testid="stSidebar"] [data-testid="stExpander"] p,
  section[data-testid="stSidebar"] [data-testid="stExpander"] span:not(svg *),
  section[data-testid="stSidebar"] [data-testid="stExpander"] label,
  section[data-testid="stSidebar"] [data-testid="stExpander"] div {
    color: #1DB954 !important; background: transparent !important;
  }
  section[data-testid="stSidebar"] [data-testid="stExpander"] svg {
    fill: #1DB954 !important; stroke: #1DB954 !important;
  }

  /* ── File uploader ──────────────────────────────────────────────────── */
  section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] {
    background: #0f1416 !important; border: 2px dashed #1e3a2a !important; border-radius: 8px !important;
  }
  section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"]:hover {
    border-color: #1DB954 !important; background: #111e16 !important;
  }
  section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] *,
  section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzoneInstructions"] * { color: #8a979d !important; }
  section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] button,
  section[data-testid="stSidebar"] [data-testid="baseButton-secondary"] {
    background: #1a2a1e !important; color: #1DB954 !important;
    border: 1px solid #1DB954 !important; border-radius: 4px !important;
  }
  section[data-testid="stSidebar"] [data-testid="baseButton-secondary"]:hover {
    background: #1DB954 !important; color: #000 !important;
  }
  section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] small,
  section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzoneInstructions"] small { color: #4a6670 !important; }

  /* ── Primary run button ─────────────────────────────────────────────── */
  section[data-testid="stSidebar"] [data-testid="baseButton-primary"] {
    background: #1DB954 !important; color: #000 !important;
    border: none !important; font-weight: 700 !important; border-radius: 20px !important;
  }
  section[data-testid="stSidebar"] [data-testid="baseButton-primary"]:hover { background: #17a349 !important; }
  section[data-testid="stSidebar"] [data-testid="baseButton-primary"]:disabled {
    background: #1e2a2e !important; color: #4a6670 !important;
  }

  /* ── Checkbox ───────────────────────────────────────────────────────── */
  section[data-testid="stSidebar"] [data-testid="stCheckbox"] span { color: #c8d8dc !important; }
  section[data-testid="stSidebar"] [data-testid="stCheckbox"] input:checked + div {
    background: #1DB954 !important; border-color: #1DB954 !important;
  }

  /* ── Alerts ─────────────────────────────────────────────────────────── */
  section[data-testid="stSidebar"] [data-testid="stAlert"] { border-radius: 6px !important; }
  section[data-testid="stSidebar"] [data-baseweb="notification"][kind="positive"] {
    background: #0d2116 !important; border-left: 3px solid #1DB954 !important; color: #1DB954 !important;
  }
  section[data-testid="stSidebar"] [data-baseweb="notification"][kind="warning"] {
    background: #1f1800 !important; border-left: 3px solid #f0a500 !important;
  }
  section[data-testid="stSidebar"] [data-baseweb="notification"][kind="negative"] {
    background: #200d0d !important; border-left: 3px solid #e05252 !important;
  }

  /* ── Divider ────────────────────────────────────────────────────────── */
  section[data-testid="stSidebar"] hr { border-color: #1e2a2e !important; margin: 0.6rem 0 !important; }

  /* ── Loading step rows ──────────────────────────────────────────────── */
  .step-row { display:flex; align-items:center; gap:12px; padding:10px 0; border-bottom:1px solid #1e2a2e; }
  .step-row:last-child { border-bottom:none; }
  .step-dot { width:10px; height:10px; border-radius:50%; flex-shrink:0; }
  .step-dot.done    { background:#1DB954; }
  .step-dot.running { background:#1DB954; animation:pulse 1s infinite; }
  .step-dot.waiting { background:#2a3a3e; }
  .step-label { font-size:14px; color:#c8d8dc; }
  .step-label.done    { color:#1DB954; }
  .step-label.running { color:#e8eef0; font-weight:600; }
  @keyframes pulse { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.4;transform:scale(1.4)} }
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def detect_file_type(content: str):
    if re.search(r"^r/(truespotify|spotify)\b", content, re.IGNORECASE | re.MULTILINE):
        count = len(re.findall(r"^r/(truespotify|spotify)\b", content, re.IGNORECASE | re.MULTILINE))
        return "reddit", f"found {count} subreddit header(s)"

    numbered     = len(re.findall(r"^\d+\.\s", content, re.MULTILINE))
    has_rating   = bool(re.search(r"Rating:\s*\d", content))
    has_reviewer = bool(re.search(r"Reviewer:\s*\S", content))
    if numbered >= 3 and (has_rating or has_reviewer):
        return "apple_ios", f"found {numbered} numbered review(s) with Rating/Reviewer fields"

    month_re = (
        r"(January|February|March|April|May|June|July|August|September|"
        r"October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"\s+\d{1,2},\s+\d{4}"
    )
    date_matches = len(re.findall(month_re, content, re.IGNORECASE))
    if date_matches >= 5:
        extra = " + 'Did you find this helpful?' prompts" if re.search(r"Did you find this helpful", content, re.IGNORECASE) else ""
        return "google_play", f"found {date_matches} date lines{extra}"

    hints = []
    if numbered > 0:   hints.append(f"{numbered} numbered line(s) but no Rating/Reviewer")
    if date_matches > 0: hints.append(f"{date_matches} date line(s) found (need ≥5)")
    return None, ("; ".join(hints) or "no recognisable patterns found")


def save_uploaded_file(content_bytes: bytes, original_name: str):
    """Save uploaded file to input/ using original filename, avoiding collisions."""
    INPUT_DIR.mkdir(exist_ok=True)
    safe = re.sub(r'[<>:"/\\|?*]', '_', original_name).strip()
    dest = INPUT_DIR / safe
    if dest.exists():
        stem, suffix = Path(safe).stem, Path(safe).suffix
        counter = 2
        while dest.exists():
            dest = INPUT_DIR / f"{stem}_{counter}{suffix}"
            counter += 1
    dest.write_bytes(content_bytes)
    return dest.name


def slot_status():
    """Return per-type counts of review files currently in input/."""
    counts = {"apple_ios": 0, "google_play": 0, "reddit": 0}
    if not INPUT_DIR.exists():
        return counts
    for f in INPUT_DIR.glob("*.txt"):
        if f.name in NON_REVIEW_FILES:
            continue
        try:
            content = f.read_text(encoding="utf-8", errors="replace")[:8192]
            ft, _ = detect_file_type(content)
            if ft:
                counts[ft] += 1
        except Exception:
            pass
    return counts


# ── Session state ─────────────────────────────────────────────────────────────
if "session_initialized" not in st.session_state:
    # Fresh session — wipe leftover review files and stale outputs from any previous run
    st.session_state.session_initialized = True
    if INPUT_DIR.exists():
        for f in INPUT_DIR.glob("*.txt"):
            if f.name not in NON_REVIEW_FILES:
                try:
                    f.unlink()
                except Exception:
                    pass
    for _out in ["report.html", "reviews_unified.json",
                 "reviews_categorised.json", "insights_report.json"]:
        _p = OUTPUT_DIR / _out
        if _p.exists():
            try:
                _p.unlink()
            except Exception:
                pass

if "processed_uploads" not in st.session_state:
    st.session_state.processed_uploads = set()   # set of (name, size) tuples
if "processed_slots" not in st.session_state:
    st.session_state.processed_slots = {}        # (name, size) -> slot filename
if "running" not in st.session_state:
    st.session_state.running = False
if "fetch_research" not in st.session_state:
    st.session_state.fetch_research = False
if "run_error" not in st.session_state:
    st.session_state.run_error = None


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 🎵 Spotify Review Analyser")
    st.markdown("---")

    # Upload
    status = slot_status()
    has_any = any(status.values())

    with st.expander("Upload review files", expanded=not has_any):
        st.caption(
            "Upload one or more `.txt` review files — format is detected automatically. "
            "You can upload multiple files of the same type. "
            "Supports Apple iOS, Google Play, and Reddit exports."
        )
        uploaded_files = st.file_uploader(
            "Choose files", type=["txt"],
            accept_multiple_files=True, label_visibility="collapsed",
        )

        # Detect removals: any previously processed file no longer in the uploader
        current_uids = {(uf.name, uf.size) for uf in (uploaded_files or [])}
        removed_uids = st.session_state.processed_uploads - current_uids
        if removed_uids:
            for uid in removed_uids:
                slot = st.session_state.processed_slots.get(uid)
                if slot:
                    p = INPUT_DIR / slot
                    if p.exists():
                        p.unlink()
                st.session_state.processed_slots.pop(uid, None)
            st.session_state.processed_uploads -= removed_uids
            # Clear outputs so the report doesn't show stale data
            for out_file in ["report.html", "reviews_unified.json",
                             "reviews_categorised.json", "insights_report.json"]:
                p = OUTPUT_DIR / out_file
                if p.exists():
                    p.unlink()

        if uploaded_files:
            for uf in uploaded_files:
                uid = (uf.name, uf.size)
                if uid in st.session_state.processed_uploads:
                    ft, _ = detect_file_type(uf.getvalue()[:8192].decode("utf-8", errors="replace"))
                    if ft:
                        st.caption(f"✓ {uf.name} ({TYPE_LABEL[ft]})")
                    continue
                content_bytes = uf.getvalue()
                file_type, reason = detect_file_type(content_bytes[:8192].decode("utf-8", errors="replace"))
                if file_type is None:
                    st.error(
                        f"**{uf.name}** — unrecognised format\n_{reason}_\n\n"
                        "Expected: Apple iOS (numbered reviews + Rating/Reviewer fields), "
                        "Google Play (date lines like 'August 29, 2025'), "
                        "or Reddit (lines starting with r/spotify)."
                    )
                else:
                    try:
                        slot = save_uploaded_file(content_bytes, uf.name)
                        st.success(f"**{uf.name}** → {TYPE_LABEL[file_type]}\n_Detected: {reason}_\nSaved as `input/{slot}`")
                        st.session_state.processed_uploads.add(uid)
                        st.session_state.processed_slots[uid] = slot
                    except Exception as e:
                        st.error(f"**{uf.name}** — could not save: {e}")

    status = slot_status()
    st.markdown("---")

    # Input file status — show counts per type
    try:
        issues    = validate_inputs()
        warn_files = {fname for lvl, fname, _ in issues if lvl == "warning"}
    except Exception:
        issues, warn_files = [], set()

    st.markdown("**Input files**")
    for type_key, label in TYPE_LABEL.items():
        n = status[type_key]
        icon = "🟢" if n > 0 else "🔴"
        st.markdown(f"{icon} {label}: **{n} file{'s' if n != 1 else ''}**")

    for lvl, fname, msg in issues:
        if lvl == "warning":
            st.warning(f"**{fname}**: {msg}")

    for lvl, fname, msg in issues:
        if lvl == "warning":
            st.warning(f"**{fname}**: {msg}")

    st.markdown("---")

    fetch = st.checkbox("Fetch research sources", value=st.session_state.fetch_research,
                        help="Re-download research articles (needs internet). Uncheck to reuse cached data.")
    st.session_state.fetch_research = fetch

    has_minimum = any(status.values())
    if st.button(
        "▶  Run Full Workflow",
        use_container_width=True, type="primary",
        disabled=not has_minimum or st.session_state.running,
        help="Upload at least one review file to run." if not has_minimum else "",
    ):
        st.session_state.running = True
        st.session_state.run_error = None
        st.rerun()

    st.markdown("---")

    st.markdown("**Output files**")
    for label, fname in [
        ("reviews_unified.json",     "reviews_unified.json"),
        ("reviews_categorised.json", "reviews_categorised.json"),
        ("insights_report.json",     "insights_report.json"),
        ("research_compiled.json",   "research_compiled.json"),
        ("report.html",              "report.html"),
    ]:
        icon = "🟢" if (OUTPUT_DIR / fname).exists() else "⚪"
        st.markdown(f"{icon} {label}")


# ── Main area ─────────────────────────────────────────────────────────────────

STEPS = [
    ("parse_reviews.py",   "Parsing reviews"),
    ("fetch_research.py",  "Fetching research sources"),
    ("analyse_reviews.py", "Analysing & tagging reviews"),
    ("generate_report.py", "Generating HTML report"),
]

if st.session_state.running:
    # ── Loading screen ────────────────────────────────────────────────────
    st.markdown("""
    <div style="padding:48px 40px 24px; text-align:center;">
      <div style="font-size:48px; margin-bottom:12px;">⚙️</div>
      <h2 style="color:#1DB954; margin:0 0 6px;">Running analysis pipeline</h2>
      <p style="color:#8a979d; margin:0;">This takes 1–3 minutes — do not close this tab.</p>
    </div>
    """, unsafe_allow_html=True)

    fetch_val = st.session_state.fetch_research
    steps_to_run = [(s, l) for s, l in STEPS if s != "fetch_research.py" or fetch_val]

    error_msg = None
    for idx, (script, label) in enumerate(steps_to_run):
        with st.spinner(f"Step {idx+1}/{len(steps_to_run)}: {label}…"):
            result = subprocess.run(
                [sys.executable, str(BASE / script)],
                capture_output=True, text=True,
            )
        if result.returncode != 0:
            error_msg = f"**{label}** failed:\n```\n{(result.stderr or result.stdout).strip()}\n```"
            break

    st.session_state.running = False
    if error_msg:
        st.session_state.run_error = error_msg
    st.rerun()

elif st.session_state.run_error:
    st.error(st.session_state.run_error)
    if st.button("Clear error and retry"):
        st.session_state.run_error = None
        st.rerun()

elif REPORT_HTML.exists():
    # ── Report ────────────────────────────────────────────────────────────
    components.html(REPORT_HTML.read_text(encoding="utf-8"), height=3000, scrolling=True)

else:
    # ── Empty state ───────────────────────────────────────────────────────
    components.html("""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:#0b0e0f;color:#c8d8dc;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;padding:40px 32px 60px;}
  .hero{text-align:center;padding:48px 0 40px;}
  .hero-icon{font-size:52px;margin-bottom:16px;}
  .hero h1{font-size:32px;font-weight:800;color:#fff;margin-bottom:8px;}
  .hero p{color:#8a979d;font-size:15px;max-width:520px;margin:0 auto;}

  /* Steps */
  .steps{display:flex;gap:16px;margin:40px 0;flex-wrap:wrap;}
  .step{flex:1;min-width:180px;background:#111518;border:1px solid #1e2a2e;border-radius:10px;padding:20px;}
  .step-num{width:28px;height:28px;border-radius:50%;background:#1DB954;color:#000;
            font-weight:800;font-size:13px;display:flex;align-items:center;justify-content:center;margin-bottom:12px;}
  .step h3{font-size:14px;font-weight:700;color:#e8eef0;margin-bottom:6px;}
  .step p{font-size:12px;color:#8a979d;line-height:1.5;}

  /* Formats */
  .section-title{font-size:13px;font-weight:700;color:#1DB954;letter-spacing:.08em;text-transform:uppercase;margin:36px 0 14px;}
  .formats{display:flex;gap:14px;flex-wrap:wrap;}
  .fmt-card{flex:1;min-width:220px;background:#111518;border:1px solid #1e2a2e;border-radius:10px;padding:18px;}
  .fmt-card h4{font-size:13px;font-weight:700;color:#e8eef0;margin-bottom:10px;display:flex;align-items:center;gap:8px;}
  .badge{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600;background:#1a2a1e;color:#1DB954;}
  .fmt-card pre{background:#0b0e0f;border:1px solid #1e2a2e;border-radius:6px;padding:10px;font-size:11px;
                color:#8a979d;overflow-x:auto;line-height:1.6;margin-top:10px;white-space:pre;}
  .highlight{color:#1DB954;}
  .rule{margin-top:10px;font-size:11px;color:#4a6670;line-height:1.6;}
  .rule span{color:#c8d8dc;}
  .cta{margin-top:40px;padding:18px 24px;background:#111518;border:1px solid #1DB954;border-radius:10px;
        display:flex;align-items:center;gap:16px;}
  .cta-icon{font-size:28px;flex-shrink:0;}
  .cta p{font-size:13px;color:#8a979d;line-height:1.6;}
  .cta p strong{color:#e8eef0;}
</style>
</head>
<body>

<div class="hero">
  <div class="hero-icon">🎵</div>
  <h1>Spotify Review Analyser</h1>
  <p>Upload your review files, run the pipeline, and get a structured report answering four product questions about music discovery.</p>
</div>

<div class="section-title">How it works</div>
<div class="steps">
  <div class="step">
    <div class="step-num">1</div>
    <h3>Upload review files</h3>
    <p>Open the <strong style="color:#1DB954">Upload review files</strong> panel in the sidebar. Drop in your Apple iOS, Google Play, and Reddit export files — format is detected automatically.</p>
  </div>
  <div class="step">
    <div class="step-num">2</div>
    <h3>Run the workflow</h3>
    <p>Click <strong style="color:#1DB954">▶ Run Full Workflow</strong>. The pipeline parses reviews, fetches research, tags each review by theme and sentiment, then builds the report.</p>
  </div>
  <div class="step">
    <div class="step-num">3</div>
    <h3>Read the insights</h3>
    <p>The full report appears here answering: why users struggle to discover music, what causes repeat listening, recommendation frustrations, and which segments suffer most.</p>
  </div>
</div>

<div class="section-title">Expected file formats</div>
<div class="formats">

  <div class="fmt-card">
    <h4>🍎 Apple App Store <span class="badge">apple ios.txt</span></h4>
    <pre><span class="highlight">1.</span> Best music app ever
<span class="highlight">Rating: 5★</span>
<span class="highlight">Reviewer:</span> JohnDoe (2 years ago)
I've been using Spotify for years and the
music discovery has really declined lately...

<span class="highlight">2.</span> Shuffle is broken
<span class="highlight">Rating: 2★</span>
<span class="highlight">Reviewer:</span> Jane Smith (6 months ago)
The shuffle algorithm plays the same 10
songs every single time...</pre>
    <div class="rule">
      <span>Required signals:</span> numbered reviews (1. 2. 3…) + Rating and/or Reviewer lines<br>
      <span>Rating:</span> 1–5★ per review<br>
      <span>Date formats:</span> (2 years ago) · (13 Apr) · separate Date: line
    </div>
  </div>

  <div class="fmt-card">
    <h4>🤖 Google Play Store <span class="badge">google play store review.txt</span></h4>
    <pre>Alice Johnson
<span class="highlight">August 29, 2025</span>
The recommendation algorithm feels stuck.
I keep hearing the same 20 songs on repeat.
3 people found this helpful
Did you find this helpful?

Bob Martinez
<span class="highlight">September 5, 2025</span>
Great app but ads are way too long on
the free tier. Really frustrating...</pre>
    <div class="rule">
      <span>Required signals:</span> 5+ date lines matching "Month DD, YYYY"<br>
      <span>Structure:</span> Name → Date → Review text → blank line<br>
      <span>Auto-stripped:</span> "Did you find this helpful?", developer responses, metadata
    </div>
  </div>

  <div class="fmt-card">
    <h4>💬 Reddit <span class="badge">reddit.txt</span></h4>
    <pre><span class="highlight">r/spotify</span>

Why does Spotify keep playing the same songs?
Discussion
I switched to premium 6 months ago and my
Discover Weekly has gotten much worse...
•
3d ago
username123

<span class="highlight">r/truespotify</span>

Shuffle is not actually random
...</pre>
    <div class="rule">
      <span>Required signals:</span> lines starting with r/spotify or r/truespotify<br>
      <span>Parses:</span> post bodies + top-level comments as separate records<br>
      <span>Auto-stripped:</span> promoted posts, [deleted] comments, upvote lines
    </div>
  </div>

</div>

<div class="cta">
  <div class="cta-icon">👈</div>
  <p><strong>Ready to start?</strong> Open the <strong>Upload review files</strong> panel in the left sidebar, drop in your .txt files, then click <strong>▶ Run Full Workflow</strong>. The report will appear here automatically when the pipeline finishes.</p>
</div>

</body>
</html>
""", height=1100, scrolling=True)
