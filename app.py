"""
Review Analysis Workflow — Streamlit App
PM Fellowship Final Project: Spotify Music Discovery

Left sidebar: upload input files (auto-detected by content) + run the pipeline.
Main area: the generated HTML report, full-bleed.

Run locally:
    pip install streamlit
    streamlit run app.py
"""

import re
import subprocess
import sys
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

sys.path.insert(0, str(Path(__file__).parent))
from parse_reviews import validate_inputs

BASE = Path(__file__).parent
INPUT_DIR = BASE / "input"
OUTPUT_DIR = BASE / "output"
REPORT_HTML = OUTPUT_DIR / "report.html"

# Canonical filenames the pipeline expects
SLOT_APPLE  = "apple ios.txt"
SLOT_GP1    = "google play store review.txt"
SLOT_GP2    = "google playstore review 2.txt"
SLOT_REDDIT = "reddit.txt"

st.set_page_config(
    page_title="Spotify Review Analyser",
    page_icon="🎵",
    layout="wide",
)

st.markdown("""
<style>
  #MainMenu, header, footer {visibility: hidden;}
  [data-testid="stToolbar"] {display: none;}
  .stApp {background: #0b0e0f;}
  .block-container {padding-top: 1rem !important;}
  section[data-testid="stSidebar"] {background: #111518;}
  section[data-testid="stSidebar"] * {color: #e8eef0 !important;}
</style>
""", unsafe_allow_html=True)


# ── Format detection ──────────────────────────────────────────────────────────

def detect_file_type(content: str) -> tuple[str, str] | tuple[None, str]:
    """
    Inspect content and return (file_type, reason).
    file_type is one of: 'apple_ios', 'google_play', 'reddit', or None.

    Detection order:
      1. Reddit    — subreddit headers are unambiguous
      2. Apple iOS — numbered reviews + Rating/Reviewer fields
      3. Google Play — date lines + helpfulness prompt
    """
    # 1. Reddit: subreddit header lines
    if re.search(r"^r/(truespotify|spotify)\b", content, re.IGNORECASE | re.MULTILINE):
        count = len(re.findall(r"^r/(truespotify|spotify)\b", content, re.IGNORECASE | re.MULTILINE))
        return "reddit", f"found {count} subreddit header(s) (r/spotify or r/truespotify)"

    # 2. Apple iOS: numbered reviews + at least one of Rating / Reviewer
    numbered = len(re.findall(r"^\d+\.\s", content, re.MULTILINE))
    has_rating   = bool(re.search(r"Rating:\s*\d", content))
    has_reviewer = bool(re.search(r"Reviewer:\s*\S", content))
    if numbered >= 3 and (has_rating or has_reviewer):
        return "apple_ios", (
            f"found {numbered} numbered review(s) with "
            f"{'Rating' if has_rating else ''}"
            f"{' and ' if has_rating and has_reviewer else ''}"
            f"{'Reviewer' if has_reviewer else ''} fields"
        )

    # 3. Google Play: recognisable date lines (Month DD, YYYY)
    month_re = (
        r"(January|February|March|April|May|June|July|August|September|"
        r"October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"\s+\d{1,2},\s+\d{4}"
    )
    date_matches = len(re.findall(month_re, content, re.IGNORECASE))
    has_helpful  = bool(re.search(r"Did you find this helpful", content, re.IGNORECASE))
    if date_matches >= 5:
        reason = f"found {date_matches} date line(s)"
        if has_helpful:
            reason += " and 'Did you find this helpful?' prompts"
        return "google_play", reason

    # Unrecognised
    hints = []
    if numbered > 0:
        hints.append(f"{numbered} numbered line(s) found but no Rating/Reviewer fields")
    if date_matches > 0:
        hints.append(f"{date_matches} date line(s) found (need at least 5)")
    hint_str = "; ".join(hints) if hints else "no recognisable patterns found"
    return None, hint_str


def save_uploaded_file(content_bytes: bytes, file_type: str) -> str:
    """
    Save bytes to the correct input slot. Returns the slot filename used.
    Google Play files fill slot 1 first, then slot 2.
    """
    INPUT_DIR.mkdir(exist_ok=True)
    content = content_bytes.decode("utf-8", errors="replace")

    if file_type == "apple_ios":
        dest = INPUT_DIR / SLOT_APPLE
    elif file_type == "reddit":
        dest = INPUT_DIR / SLOT_REDDIT
    elif file_type == "google_play":
        # Fill GP1 first; if already present use GP2
        dest = INPUT_DIR / SLOT_GP1 if not (INPUT_DIR / SLOT_GP1).exists() else INPUT_DIR / SLOT_GP2
    else:
        raise ValueError(f"Unknown file_type: {file_type}")

    dest.write_text(content, encoding="utf-8")
    return dest.name


# ── Pipeline runner ───────────────────────────────────────────────────────────

def run_workflow(fetch_research: bool) -> bool:
    steps = [
        ("parse_reviews.py",   "Parsing reviews"),
        ("fetch_research.py",  "Fetching research") if fetch_research else None,
        ("analyse_reviews.py", "Analysing & tagging"),
        ("generate_report.py", "Generating report"),
    ]
    for step in steps:
        if step is None:
            continue
        script, label = step
        with st.spinner(f"{label}..."):
            result = subprocess.run(
                [sys.executable, str(BASE / script)],
                capture_output=True, text=True,
            )
        if result.returncode != 0:
            st.sidebar.error(f"{label} failed:\n{result.stderr or result.stdout}")
            return False
    return True


# ── Sidebar ───────────────────────────────────────────────────────────────────

TYPE_LABEL = {
    "apple_ios":   "Apple iOS reviews",
    "google_play": "Google Play reviews",
    "reddit":      "Reddit posts",
}

# Current state of input slots
def slot_status():
    return {
        "apple_ios":    (INPUT_DIR / SLOT_APPLE).exists(),
        "google_play_1": (INPUT_DIR / SLOT_GP1).exists(),
        "google_play_2": (INPUT_DIR / SLOT_GP2).exists(),
        "reddit":       (INPUT_DIR / SLOT_REDDIT).exists(),
    }

with st.sidebar:
    st.markdown("## 🎵 Spotify Review Analyser")
    st.markdown("---")

    # ── Upload section ────────────────────────────────────────────────────────
    status = slot_status()
    all_present = status["apple_ios"] and status["google_play_1"] and status["reddit"]

    with st.expander("Upload review files", expanded=not all_present):
        st.caption(
            "Upload any `.txt` review files — format is detected automatically. "
            "Supports Apple iOS, Google Play, and Reddit exports."
        )

        uploaded_files = st.file_uploader(
            "Choose files",
            type=["txt"],
            accept_multiple_files=True,
            label_visibility="collapsed",
        )

        if uploaded_files:
            saved_any = False
            for uf in uploaded_files:
                content_bytes = uf.getvalue()
                # Decode a sample for detection (first 8 KB is enough)
                sample = content_bytes[:8192].decode("utf-8", errors="replace")
                file_type, reason = detect_file_type(sample)

                if file_type is None:
                    st.error(
                        f"**{uf.name}** — unrecognised format  \n"
                        f"_{reason}_  \n"
                        "Check [INPUT_FORMAT.md](INPUT_FORMAT.md) for the expected structure."
                    )
                else:
                    slot = save_uploaded_file(content_bytes, file_type)
                    st.success(
                        f"**{uf.name}** → {TYPE_LABEL[file_type]}  \n"
                        f"_Detected: {reason}_  \n"
                        f"Saved as `{slot}`"
                    )
                    saved_any = True

            if saved_any:
                st.rerun()

    st.markdown("---")

    # ── Input file status ─────────────────────────────────────────────────────
    try:
        issues = validate_inputs()
        error_files = {fname for _, fname, _ in issues if _ == "error" or issues[0][0] == "error"}
        warn_files  = {fname for _, fname, _ in issues if issues[0][0] == "warning"}
        # Rebuild properly
        error_files = {fname for lvl, fname, _ in issues if lvl == "error"}
        warn_files  = {fname for lvl, fname, _ in issues if lvl == "warning"}
    except Exception:
        error_files, warn_files = set(), set()

    status = slot_status()
    st.markdown("**Input files**")

    def _icon(fname):
        if fname in error_files:  return "🔴"
        if fname in warn_files:   return "🟡"
        return "🟢"

    apple_icon = "🟢" if status["apple_ios"] else "🔴"
    st.markdown(f"{apple_icon} Apple iOS reviews")

    if status["google_play_1"] and status["google_play_2"]:
        gp_icon = _icon(SLOT_GP1) if _icon(SLOT_GP1) != "🟢" else _icon(SLOT_GP2)
        st.markdown(f"🟢 Google Play reviews (2 files)")
    elif status["google_play_1"]:
        st.markdown(f"{_icon(SLOT_GP1)} Google Play reviews (1 of 2)")
    else:
        st.markdown("🔴 Google Play reviews")

    reddit_icon = "🟢" if status["reddit"] else "🔴"
    st.markdown(f"{reddit_icon} Reddit posts")

    # Show any format warnings inline
    for lvl, fname, msg in (issues if 'issues' in dir() else []):
        if lvl == "warning":
            st.warning(f"**{fname}**: {msg}")

    st.markdown("---")

    # ── Run controls ──────────────────────────────────────────────────────────
    fetch = st.checkbox(
        "Fetch research sources",
        value=True,
        help="Re-download research articles (needs internet). Uncheck to reuse cached data.",
    )

    has_minimum = status["apple_ios"] or status["google_play_1"] or status["reddit"]
    run_disabled = not has_minimum
    if st.button(
        "▶  Run Full Workflow",
        use_container_width=True,
        type="primary",
        disabled=run_disabled,
        help="Upload at least one review file to run." if run_disabled else "",
    ):
        ok = run_workflow(fetch)
        if ok:
            st.success("Done! Report updated.")
            st.rerun()

    st.markdown("---")

    # ── Output file status ────────────────────────────────────────────────────
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


# ── Main area: HTML report ────────────────────────────────────────────────────
if REPORT_HTML.exists():
    report_html = REPORT_HTML.read_text(encoding="utf-8")
    components.html(report_html, height=3000, scrolling=True)
else:
    st.markdown(
        "<div style='padding:120px 40px; text-align:center; color:#8a979d;'>"
        "<h2 style='color:#1DB954;'>No report yet</h2>"
        "<p>Upload your review files using the sidebar, then click "
        "<strong>Run Full Workflow</strong>.</p>"
        "</div>",
        unsafe_allow_html=True,
    )
