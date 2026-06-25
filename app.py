"""
Review Analysis Workflow — Streamlit App
PM Fellowship Final Project: Spotify Music Discovery

Left sidebar : upload input files (format auto-detected) + run controls.
Main area    : empty-state guide → loading screen → HTML report.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

try:
    from openai import OpenAI as _OpenAI
    _OPENAI_AVAILABLE = True
except ImportError:
    _OPENAI_AVAILABLE = False

def _get_secret(key, default=""):
    try:
        return st.secrets.get(key, os.environ.get(key, default))
    except Exception:
        return os.environ.get(key, default)


def _render_md(text):
    """Markdown → styled HTML for the AI answer card. Used both while streaming
    and for the stored answer so the formatting/colors are identical."""
    import html as _h
    try:
        import markdown as _mdlib
        return _mdlib.markdown(text, extensions=["nl2br", "fenced_code"])
    except ImportError:
        h = _h.escape(text)
        h = re.sub(r"^#### (.+)$", r'<h4 style="color:#1DB954;margin:14px 0 6px;">\1</h4>', h, flags=re.MULTILINE)
        h = re.sub(r"^### (.+)$",  r'<h3 style="color:#1DB954;margin:18px 0 8px;">\1</h3>', h, flags=re.MULTILINE)
        h = re.sub(r"^## (.+)$",   r'<h2 style="color:#1DB954;margin:22px 0 10px;font-size:17px;">\1</h2>', h, flags=re.MULTILINE)
        h = re.sub(r"^# (.+)$",    r'<h1 style="color:#1DB954;margin:26px 0 12px;font-size:20px;">\1</h1>', h, flags=re.MULTILINE)
        h = re.sub(r"\*\*(.+?)\*\*", r'<strong style="color:#ffffff;">\1</strong>', h)
        h = re.sub(r"\*(.+?)\*",     r"<em>\1</em>", h)
        h = re.sub(r"^[-*] (.+)$",   r'<li style="margin:5px 0;">\1</li>', h, flags=re.MULTILINE)
        h = re.sub(r"^\d+\. (.+)$",  r'<li style="margin:5px 0;">\1</li>', h, flags=re.MULTILINE)
        h = re.sub(r"(<li[^>]*>.*?</li>\n?)+",
                   lambda m: f'<ul style="padding-left:22px;margin:10px 0;">{m.group()}</ul>',
                   h, flags=re.DOTALL)
        out = []
        for part in re.split(r"\n{2,}", h):
            part = part.strip()
            if not part:
                continue
            out.append(part if part.startswith("<")
                       else f'<p style="margin:10px 0;">{part.replace(chr(10), "<br>")}</p>')
        return "\n".join(out)

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
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
  /* ── Global ─────────────────────────────────────────────────────────── */
  #MainMenu, header, footer { visibility: hidden; }
  [data-testid="stToolbar"]  { display: none; }
  .stApp           { background: #0b0e0f; }
  .block-container { padding-top: 1rem !important; }

  /* ── Sidebar — always visible ───────────────────────────────────────── */
  section[data-testid="stSidebar"] {
    background: #0f1416 !important;
    border-right: 1px solid #1e2a2e !important;
    min-width: 280px !important;
    transform: none !important;
    display: block !important;
    visibility: visible !important;
  }
  /* Hide both collapse buttons so sidebar can never be dismissed */
  [data-testid="stSidebarCollapseButton"],
  [data-testid="collapsedControl"] { display: none !important; }
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

  /* ── Q&A text area ──────────────────────────────────────────────────── */
  section[data-testid="stSidebar"] textarea {
    background: #000 !important;
    color: #fff !important;
    border: 1px solid #1e3a2a !important;
    border-radius: 6px !important;
    font-size: 13px !important;
  }
  section[data-testid="stSidebar"] textarea:focus {
    border-color: #1DB954 !important;
    box-shadow: 0 0 0 1px #1DB954 !important;
  }
  section[data-testid="stSidebar"] textarea::placeholder {
    color: #4a6670 !important;
  }

  /* ── Radio buttons ──────────────────────────────────────────────────── */
  section[data-testid="stSidebar"] [data-testid="stRadio"] label {
    color: #c8d8dc !important;
    padding: 6px 10px !important;
    border-radius: 6px !important;
    cursor: pointer !important;
  }
  section[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) {
    background: #0d2116 !important;
    color: #1DB954 !important;
    font-weight: 600 !important;
  }
  section[data-testid="stSidebar"] [data-testid="stRadio"] [data-testid="stMarkdownContainer"] p {
    color: inherit !important;
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

  /* ── Main area markdown — white text for AI answer ───────────────── */
  section.main [data-testid="stMarkdownContainer"] p,
  section.main [data-testid="stMarkdownContainer"] li,
  section.main [data-testid="stMarkdownContainer"] ul,
  section.main [data-testid="stMarkdownContainer"] ol { color: #e8eef0 !important; }
  section.main [data-testid="stMarkdownContainer"] h1,
  section.main [data-testid="stMarkdownContainer"] h2,
  section.main [data-testid="stMarkdownContainer"] h3,
  section.main [data-testid="stMarkdownContainer"] h4 { color: #1DB954 !important; }
  section.main [data-testid="stMarkdownContainer"] strong { color: #ffffff !important; }
  section.main [data-testid="stMarkdownContainer"] code { color: #1DB954 !important; background: #0d1a12 !important; }
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


UI_UPLOADS_MANIFEST = INPUT_DIR / ".ui_uploads.json"

def _load_manifest():
    try:
        return json.loads(UI_UPLOADS_MANIFEST.read_text(encoding="utf-8"))
    except Exception:
        return []

def _save_manifest(names: list):
    INPUT_DIR.mkdir(exist_ok=True)
    UI_UPLOADS_MANIFEST.write_text(json.dumps(names), encoding="utf-8")

def save_uploaded_file(content_bytes: bytes, original_name: str):
    """Save uploaded file to input/ and register it in the UI uploads manifest."""
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
    # Track this file so it gets cleared on next session init
    manifest = _load_manifest()
    if dest.name not in manifest:
        manifest.append(dest.name)
        _save_manifest(manifest)
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
if "processed_uploads" not in st.session_state:
    st.session_state.processed_uploads = set()   # set of (name, size) tuples
if "processed_slots" not in st.session_state:
    st.session_state.processed_slots = {}        # (name, size) -> slot filename

if "session_initialized" not in st.session_state:
    st.session_state.session_initialized = True
    # Clear files uploaded via the UI in the previous session
    for _fname in _load_manifest():
        _p = INPUT_DIR / _fname
        if _p.exists():
            try:
                _p.unlink()
            except Exception:
                pass
    _save_manifest([])  # reset manifest
    # Clear stale output files so the report isn't from a previous run
    for _out in ["report.html", "reviews_unified.json",
                 "reviews_categorised.json", "insights_report.json"]:
        _p = OUTPUT_DIR / _out
        if _p.exists():
            try:
                _p.unlink()
            except Exception:
                pass
if "running" not in st.session_state:
    st.session_state.running = False
if "fetch_research" not in st.session_state:
    st.session_state.fetch_research = False
if "run_error" not in st.session_state:
    st.session_state.run_error = None
if "stop_requested" not in st.session_state:
    st.session_state.stop_requested = False
if "pipeline_stopped" not in st.session_state:
    st.session_state.pipeline_stopped = False
if "running_pid" not in st.session_state:
    st.session_state.running_pid = None
if "qa_query" not in st.session_state:
    st.session_state.qa_query = ""
if "qa_answer" not in st.session_state:
    st.session_state.qa_answer = ""


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

    st.markdown("---")

    # ── Q&A — only shown when a report exists ────────────────────────────
    _insights_path = OUTPUT_DIR / "insights_report.json"
    if _insights_path.exists():
        st.markdown("**Ask the report**")
        qa_query = st.text_area(
            "qa_input",
            value=st.session_state.qa_query,
            placeholder=(
                "Type your questions here, e.g.\n"
                "Why do users struggle to discover music?\n"
                "Which segment is most frustrated with ads?\n"
                "What causes repeat listening?"
            ),
            height=120,
            label_visibility="collapsed",
        )
        if st.button("Ask AI", use_container_width=True, type="primary", disabled=st.session_state.running):
            st.session_state.qa_query = qa_query
            st.session_state.qa_answer = "__loading__"
            st.rerun()

    has_minimum = any(status.values())
    if st.button(
        "▶  Run Full Workflow",
        use_container_width=True, type="primary",
        disabled=not has_minimum or st.session_state.running,
        help="Upload at least one review file to run." if not has_minimum else "",
    ):
        st.session_state.running = True
        st.session_state.run_error = None
        st.session_state.pipeline_stopped = False
        st.session_state.qa_answer = ""
        st.rerun()

    if st.session_state.running:
        if st.button("⏹  Stop", use_container_width=True):
            st.session_state.stop_requested = True
            st.rerun()
    elif st.session_state.run_error or st.session_state.pipeline_stopped:
        if st.button("↺  Re-run", use_container_width=True):
            st.session_state.running = True
            st.session_state.run_error = None
            st.session_state.pipeline_stopped = False
            st.session_state.qa_answer = ""
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

_PDF_BTN_HTML = """
<style>
.rpt-pdf-btn {
  position:fixed; top:16px; right:16px; z-index:9999;
  background:#1DB954; color:#000 !important; border:none;
  border-radius:8px; padding:9px 18px; font-weight:700;
  font-size:13px; cursor:pointer;
  display:flex; align-items:center; gap:7px;
  box-shadow:0 2px 14px rgba(29,185,84,0.45);
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  transition:background .18s;
}
.rpt-pdf-btn:hover { background:#17a349; }
@media print { .rpt-pdf-btn { display:none !important; } }
</style>
<button class="rpt-pdf-btn" onclick="window.print()">
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
    <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
    <polyline points="7 10 12 15 17 10"/>
    <line x1="12" y1="15" x2="12" y2="3"/>
  </svg>
  Download PDF
</button>
"""

def _inject_pdf_btn(html_str: str) -> str:
    if "</body>" in html_str:
        return html_str.replace("</body>", _PDF_BTN_HTML + "</body>", 1)
    return html_str + _PDF_BTN_HTML


if st.session_state.running:
    # ── Centered dialog loading screen ────────────────────────────────────
    steps_to_run = [(s, l) for s, l in STEPS if s != "fetch_research.py"]

    tracker_ph = st.empty()

    def _render_dialog(statuses, batch_cur=0, batch_tot=0, log_lines=None):
        if log_lines is None:
            log_lines = []
        icons  = {"done": "✅", "running": "⏳", "waiting": "○", "error": "❌"}
        colors = {"done": "#1DB954", "running": "#1DB954", "waiting": "#3a5540", "error": "#e05252"}

        rows = ""
        for i, (_, lbl) in enumerate(steps_to_run):
            st_ = statuses.get(i, "waiting")
            ic  = icons[st_]
            col = colors[st_]
            fw  = "700" if st_ in ("running", "done") else "400"
            rows += (
                f'<div style="display:flex;align-items:center;gap:14px;padding:10px 0;'
                f'border-bottom:1px solid #152218;">'
                f'<span style="font-size:18px;min-width:26px;text-align:center;">{ic}</span>'
                f'<span style="color:{col};font-weight:{fw};font-size:14px;">'
                f'Step {i+1} — {lbl}</span>'
                f'</div>'
            )

        batch_html = ""
        if batch_tot > 0:
            pct = batch_cur / batch_tot
            batch_html = (
                f'<div style="margin-top:18px;">'
                f'<div style="display:flex;justify-content:space-between;'
                f'font-size:11px;color:#4a7a5a;margin-bottom:7px;">'
                f'<span style="color:#1DB954;font-weight:600;">Classifying reviews</span>'
                f'<span style="color:#1DB954;">{batch_cur}/{batch_tot} batches</span></div>'
                f'<div style="background:#152218;border-radius:6px;height:6px;overflow:hidden;">'
                f'<div style="background:#1DB954;width:{pct*100:.1f}%;height:100%;'
                f'border-radius:6px;transition:width .4s;"></div></div></div>'
            )

        log_html = ""
        if log_lines:
            lines_html = "".join(
                f'<div style="font-size:10px;color:#1DB954;font-family:monospace;'
                f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;opacity:0.55;">{l}</div>'
                for l in log_lines
            )
            log_html = f'<div style="margin-top:14px;">{lines_html}</div>'

        html = f"""
        <div style="display:flex;justify-content:center;align-items:flex-start;
                    padding:48px 16px;min-height:60vh;">
          <div style="
            background:#060e09;
            border:2px solid #1DB954;
            border-radius:18px;
            padding:40px 44px;
            width:100%;
            max-width:560px;
            box-shadow:0 0 60px rgba(29,185,84,0.15),0 2px 24px rgba(0,0,0,0.5);
          ">
            <div style="text-align:center;margin-bottom:32px;">
              <div style="font-size:46px;margin-bottom:16px;">⚙️</div>
              <h2 style="color:#1DB954;font-size:23px;font-weight:800;margin:0 0 8px;
                         letter-spacing:-0.02em;">Running Analysis Pipeline</h2>
              <p style="color:#3a5540;font-size:13px;margin:0;">Do not close this tab.</p>
            </div>
            <div>{rows}</div>
            {batch_html}
            {log_html}
          </div>
        </div>
        """
        tracker_ph.markdown(html, unsafe_allow_html=True)

    statuses   = {i: "waiting" for i in range(len(steps_to_run))}
    error_msg  = None
    failed_out = ""

    for idx, (script, label) in enumerate(steps_to_run):
        statuses[idx] = "running"
        _render_dialog(statuses)

        cmd = [sys.executable, "-u", str(BASE / script)]
        if script == "analyse_reviews.py":
            cmd += ["--classifier", "keyword"]

        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, encoding="utf-8", errors="replace",
        )
        st.session_state.running_pid = proc.pid

        batch_cur = 0
        batch_tot = 0
        log_lines = []
        all_output = []
        line_count = 0

        for raw_line in iter(proc.stdout.readline, ""):
            line = raw_line.rstrip()
            if not line:
                continue
            all_output.append(line)
            log_lines.append(line)
            line_count += 1
            if len(log_lines) > 3:
                log_lines.pop(0)

            if line_count % 5 == 0 and st.session_state.get("stop_requested"):
                proc.terminate()
                break

            m = re.search(r"batch (\d+)/(\d+)", line)
            if m:
                batch_cur = int(m.group(1))
                batch_tot = int(m.group(2))

            _render_dialog(statuses, batch_cur, batch_tot, log_lines)

        proc.wait()

        if st.session_state.get("stop_requested"):
            statuses[idx] = "error"
            _render_dialog(statuses, batch_cur, batch_tot, log_lines)
            st.session_state.stop_requested = False
            st.session_state.pipeline_stopped = True
            st.session_state.running_pid = None
            break

        if proc.returncode != 0:
            statuses[idx] = "error"
            _render_dialog(statuses, batch_cur, batch_tot, log_lines)
            failed_out = "\n".join(all_output[-30:])
            error_msg = f"**{label}** failed:\n```\n{failed_out}\n```"
            break
        else:
            statuses[idx] = "done"
            _render_dialog(statuses, 0, 0, [])

    st.session_state.running = False
    st.session_state.running_pid = None
    if error_msg:
        st.session_state.run_error = error_msg
    st.rerun()

elif st.session_state.pipeline_stopped:
    st.info("Pipeline stopped. Click **↺ Re-run** in the sidebar to restart.")

elif st.session_state.run_error:
    st.error(st.session_state.run_error)

elif st.session_state.qa_answer == "__loading__":
    # ── AI Q&A — stream response from OpenCode ───────────────────────────
    _insights_path = OUTPUT_DIR / "insights_report.json"
    try:
        with open(_insights_path, encoding="utf-8") as _f:
            _insights = json.load(_f)
    except Exception as _e:
        st.error(f"Could not load insights: {_e}")
        st.session_state.qa_answer = ""
        st.stop()

    def _compact_context(ins):
        ctx = {
            "total_reviews": ins.get("total_reviews_analysed"),
            "sources": ins.get("source_breakdown", {}),
            "questions": [],
        }
        for q in ins.get("questions", []):
            segs = q.get("segments", {})
            entry = {
                "question": q.get("question"),
                "relevant_reviews": q.get("total_relevant_reviews"),
                "top_themes": list(q.get("theme_frequency", {}).keys())[:3],
                "sentiment": q.get("sentiment_breakdown", {}),
                "key_quotes": (q.get("top_quotes") or q.get("evidence_quotes") or [])[:2],
            }
            # Use the REPORT's computed answer — not raw review count, which
            # would pick the unclassified catch-all bucket.
            if segs:
                worst = q.get("worst_affected_segment")
                entry["most_affected_segment"] = worst
                if worst and worst in segs:
                    entry["most_affected_negative_rate"] = segs[worst].get("negative_rate")
                # Compact per-segment pain signal so the AI can't draw its own
                # conflicting conclusion from volume alone.
                entry["segment_negative_rates"] = {
                    s: d.get("negative_rate") for s, d in segs.items()
                }
            ctx["questions"].append(entry)
        return json.dumps(ctx, ensure_ascii=False)

    _context = _compact_context(_insights)
    _user_q  = st.session_state.qa_query.strip()
    _api_key  = _get_secret("OPENCODE_API_KEY")
    _base_url = _get_secret("OPENCODE_BASE_URL", "https://opencode.ai/zen/go/v1")
    _model    = _get_secret("OPENCODE_MODEL", "deepseek-v4-flash")

    import html as _html_lib
    import random as _random

    _LOADER_MSGS = [
        "Bribing the algorithm for answers…",
        "Asking 27,000 Spotify users their deepest opinions…",
        "Untangling recommendation spaghetti…",
        "Decoding shuffle logic (nobody knows how it works)…",
        "Consulting the ghost of Discover Weekly past…",
        "Turning one-star rants into actionable insights…",
        "Counting how many times 'same songs' appears…",
        "Interrogating the echo chamber…",
        "Converting user frustration into PM gold…",
        "Finding signal in the sea of shuffle complaints…",
    ]
    _loader_msg = _LOADER_MSGS[hash(st.session_state.get("qa_query", "")) % len(_LOADER_MSGS)]

    _CARD = (
        "background:#060e09;border:2px solid #1DB954;border-radius:14px;"
        "padding:26px 30px 28px;margin-bottom:20px;"
        "box-shadow:0 0 50px rgba(29,185,84,0.12);"
    )
    _LABEL = (
        "color:#1DB954;font-size:11px;font-weight:800;letter-spacing:.12em;"
        "text-transform:uppercase;margin-bottom:16px;opacity:0.9;"
    )
    _BODY = (
        "color:#ffffff;line-height:1.85;font-size:14px;"
        "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;"
    )
    _LOADER_CSS = """
<style>
@keyframes cc-star {
  0% { content:"\\2736"; } 16% { content:"\\2738"; } 33% { content:"\\273A"; }
  50% { content:"\\2739"; } 66% { content:"\\2737"; } 83% { content:"\\2735"; }
  100% { content:"\\2736"; }
}
@keyframes cc-pulse { 0%,100% { opacity:1; transform:scale(1); } 50% { opacity:.5; transform:scale(.82); } }
@keyframes cc-word {
  0%,16% { content:"Analyzing"; } 16%,33% { content:"Crunching"; }
  33%,50% { content:"Synthesizing"; } 50%,66% { content:"Distilling"; }
  66%,83% { content:"Reasoning"; } 83%,100% { content:"Finalizing"; }
}
@keyframes blink { 0%,100% { opacity:1; } 50% { opacity:0; } }
.cc-star {
  display:inline-block; color:#1DB954; font-size:18px; line-height:1;
  animation: cc-pulse 1s ease-in-out infinite;
  filter: drop-shadow(0 0 7px rgba(29,185,84,.65));
}
.cc-star::before { content:"\\2736"; animation: cc-star .85s steps(1,end) infinite; }
.cc-word::after  { content:"Analyzing"; animation: cc-word 7.2s steps(1,end) infinite; }
</style>"""

    def _loader_row():
        return (
            '<div style="display:flex;align-items:baseline;gap:10px;margin-bottom:16px;">'
            '<span class="cc-star"></span>'
            '<span style="color:#1DB954;font-size:13px;font-weight:600;letter-spacing:.01em;">'
            '<span class="cc-word"></span><span style="opacity:.45;">…</span></span>'
            '</div>'
        )

    def _ai_card(body_html, streaming=False, loading=False):
        if loading:
            return f"""{_LOADER_CSS}
<div style="{_CARD}">
  <div style="{_LABEL}">AI Analysis</div>
  {_loader_row()}
  <div style="color:#3a5540;font-size:12px;line-height:1.5;margin-left:28px;">{_loader_msg}</div>
</div>"""
        if streaming:
            cursor = '<span style="color:#1DB954;animation:blink .9s step-end infinite;">▌</span>'
            return f"""{_LOADER_CSS}
<div style="{_CARD}">
  <div style="{_LABEL}">AI Analysis</div>
  {_loader_row()}
  <div style="{_BODY}">{body_html}{cursor}</div>
</div>"""
        # final — loader gone, no cursor
        return f"""
<div style="{_CARD}">
  <div style="{_LABEL}">AI Analysis</div>
  <div style="{_BODY}">{body_html}</div>
</div>"""

    if not _api_key or not _OPENAI_AVAILABLE:
        st.warning("OpenCode API key not configured — Q&A requires the API.")
        st.session_state.qa_answer = ""
        st.rerun()
    else:
        _box = st.empty()
        _box.markdown(_ai_card("", loading=True), unsafe_allow_html=True)
        try:
            _client = _OpenAI(api_key=_api_key, base_url=_base_url)
            _stream = _client.chat.completions.create(
                model=_model,
                max_tokens=16384,
                temperature=0.3,
                stream=True,
                messages=[
                    {"role": "system", "content": (
                        "You are a product research analyst. Answer the user's questions using "
                        "ONLY the Spotify review data provided. Be specific — cite review counts, "
                        "segment names, and direct quotes where available. Use clear headings for "
                        "each question. Format your response in markdown.\n\n"
                        "IMPORTANT — stay consistent with the report's findings:\n"
                        "- When asked which segment is 'most affected', use the "
                        "'most_affected_segment' field provided. Do NOT infer it from raw review "
                        "counts — the largest segment is an unclassified catch-all bucket, not the "
                        "most affected one.\n"
                        "- Judge how 'affected' a segment is by its negative RATE "
                        "(see 'segment_negative_rates'), not by review volume."
                    )},
                    {"role": "user", "content": (
                        f"Here is the Spotify review analysis data:\n{_context}\n\n"
                        f"Please answer these questions:\n{_user_q}"
                    )},
                ],
            )

            _accumulated = ""
            _buf = ""
            _in_think = False
            for _chunk in _stream:
                _delta = (_chunk.choices[0].delta.content or "")
                _buf += _delta
                if _in_think:
                    _end = _buf.find("</think>")
                    if _end != -1:
                        _in_think = False
                        _buf = _buf[_end + 8:]
                    else:
                        _buf = ""
                        continue
                if not _in_think:
                    _start = _buf.find("<think>")
                    if _start != -1:
                        if _start > 0:
                            _accumulated += _buf[:_start]
                        _in_think = True
                        _buf = _buf[_start + 7:]
                        _end2 = _buf.find("</think>")
                        if _end2 != -1:
                            _in_think = False
                            _buf = _buf[_end2 + 8:]
                        else:
                            _buf = ""
                    else:
                        _accumulated += _buf
                        _buf = ""
                _box.markdown(
                    _ai_card(_render_md(_accumulated), streaming=True),
                    unsafe_allow_html=True,
                )
            if _buf and not _in_think:
                _accumulated += _buf
            # Final render — loader removed, no cursor
            _box.markdown(_ai_card(_render_md(_accumulated), streaming=False), unsafe_allow_html=True)
            st.session_state.qa_answer = _accumulated.strip()
        except Exception as _e:
            st.session_state.qa_answer = ""
            st.error(f"AI Q&A failed: {_e}")
        st.rerun()

elif st.session_state.qa_answer:
    # ── Show stored Q&A answer — render markdown inside the green card ────
    _answer_html = _render_md(st.session_state.qa_answer)
    st.markdown(f"""
<div style="background:#060e09;border:2px solid #1DB954;border-radius:14px;
            padding:26px 30px 28px;margin-bottom:12px;
            box-shadow:0 0 50px rgba(29,185,84,0.12);">
  <div style="color:#1DB954;font-size:11px;font-weight:800;letter-spacing:.12em;
              text-transform:uppercase;margin-bottom:16px;opacity:0.9;">AI Analysis</div>
  <div style="color:#ffffff;line-height:1.85;font-size:14px;
              font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
    {_answer_html}
  </div>
</div>
""", unsafe_allow_html=True)

    # ── Copy / Download buttons for AI answer ─────────────────────────────
    _btn_js_text = json.dumps(st.session_state.qa_answer)
    components.html(f"""
<style>
  body {{ margin:0; padding:0; background:transparent; }}
  .btn-row {{ display:flex; gap:10px; padding:0 2px 4px; }}
  .action-btn {{
    display:flex; align-items:center; gap:7px;
    background:#111518; border:1px solid #1e2a2e;
    color:#c8d8dc; border-radius:8px;
    padding:8px 16px; font-size:13px; font-weight:600;
    cursor:pointer; transition:all .18s;
    font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  }}
  .action-btn:hover {{ background:#0d1c14; border-color:#1DB954; color:#1DB954; }}
  .action-btn svg {{ flex-shrink:0; }}
</style>
<div class="btn-row">
  <button class="action-btn" id="copyBtn">
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
      <rect x="9" y="9" width="13" height="13" rx="2"/>
      <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/>
    </svg>
    Copy
  </button>
  <button class="action-btn" id="dlBtn">
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
      <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
      <polyline points="7 10 12 15 17 10"/>
      <line x1="12" y1="15" x2="12" y2="3"/>
    </svg>
    Download .md
  </button>
</div>
<script>
const _text = {_btn_js_text};
document.getElementById('copyBtn').addEventListener('click', function() {{
  navigator.clipboard.writeText(_text).then(() => {{
    const svg = this.querySelector('svg').outerHTML;
    this.innerHTML = svg + ' ✓ Copied!';
    this.style.borderColor = '#1DB954';
    this.style.color = '#1DB954';
    setTimeout(() => {{
      this.innerHTML = svg + ' Copy';
      this.style.borderColor = '';
      this.style.color = '';
    }}, 2000);
  }}).catch(() => {{
    this.innerHTML = this.innerHTML.replace('Copy','Failed');
  }});
}});
document.getElementById('dlBtn').addEventListener('click', function() {{
  const blob = new Blob([_text], {{type: 'text/markdown'}});
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href = url; a.download = 'spotify_ai_analysis.md'; a.click();
  URL.revokeObjectURL(url);
}});
</script>
""", height=52)

    st.markdown("---")
    if REPORT_HTML.exists():
        _rhtml = REPORT_HTML.read_text(encoding="utf-8")
        _rhtml = _inject_pdf_btn(_rhtml)
        components.html(_rhtml, height=3000, scrolling=True)

elif REPORT_HTML.exists():
    # ── Report ────────────────────────────────────────────────────────────
    _rhtml = REPORT_HTML.read_text(encoding="utf-8")
    _rhtml = _inject_pdf_btn(_rhtml)
    components.html(_rhtml, height=3000, scrolling=True)

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
