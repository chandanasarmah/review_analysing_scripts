"""
Review Analysis Workflow — Streamlit App
PM Fellowship Final Project: Spotify Music Discovery

Left sidebar: upload input files + run the pipeline.
Main area: the generated HTML report, full-bleed.

Run locally:
    pip install streamlit
    streamlit run app.py
"""

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

INPUT_FILES = [
    ("Apple iOS reviews",     "apple ios.txt"),
    ("Google Play (batch 1)", "google play store review.txt"),
    ("Google Play (batch 2)", "google playstore review 2.txt"),
    ("Reddit posts",          "reddit.txt"),
]

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
  /* Keep expander header readable */
  [data-testid="stExpander"] summary {color: #e8eef0 !important;}
</style>
""", unsafe_allow_html=True)


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
with st.sidebar:
    st.markdown("## 🎵 Spotify Review Analyser")
    st.markdown("---")

    # ── Upload input files ────────────────────────────────────────────────────
    all_present = all((INPUT_DIR / fname).exists() for _, fname in INPUT_FILES)

    with st.expander("Upload input files", expanded=not all_present):
        st.caption(
            "Upload each review file as a `.txt` file. "
            "Files are saved to `input/` and used by the pipeline."
        )
        INPUT_DIR.mkdir(exist_ok=True)
        saved_files = []

        for label, fname in INPUT_FILES:
            already_exists = (INPUT_DIR / fname).exists()
            status_tag = " ✓" if already_exists else " (missing)"
            uploaded = st.file_uploader(
                f"{label}{status_tag}",
                type=["txt"],
                key=f"upload_{fname}",
            )
            if uploaded is not None:
                (INPUT_DIR / fname).write_bytes(uploaded.getvalue())
                saved_files.append(label)

        if saved_files:
            st.success(f"Saved: {', '.join(saved_files)}")
            st.rerun()

    st.markdown("---")

    # ── Validate and show status ──────────────────────────────────────────────
    try:
        issues = validate_inputs()
        errors   = [i for i in issues if i[0] == "error"]
        warnings = [i for i in issues if i[0] == "warning"]
    except Exception:
        errors, warnings = [], []

    error_files = {fname for _, fname, _ in errors}
    warn_files  = {fname for _, fname, _ in warnings}

    st.markdown("**Input files**")
    for label, fname in INPUT_FILES:
        if fname in error_files:
            icon, note = "🔴", " — missing"
        elif fname in warn_files:
            icon, note = "🟡", " — format warning"
        else:
            icon, note = "🟢", ""
        st.markdown(f"{icon} {label}{note}")

    if warnings and not errors:
        for _, fname, msg in warnings:
            st.warning(f"**{fname}**: {msg}")

    st.markdown("---")

    # ── Run controls ─────────────────────────────────────────────────────────
    fetch = st.checkbox(
        "Fetch research sources",
        value=True,
        help="Re-download research articles (needs internet). Uncheck to reuse cached data.",
    )

    run_disabled = bool(errors)
    if st.button(
        "▶  Run Full Workflow",
        use_container_width=True,
        type="primary",
        disabled=run_disabled,
        help="Upload all input files first." if run_disabled else "",
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
