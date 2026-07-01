"""
discovery_app.py — Spotify "AI Recs" : AI-native Discovery Controls panel.
Run:  python -m streamlit run mvp/discovery_app.py --server.port 8501
Open: http://127.0.0.1:8501
"""

import os
import sys
import uuid
import urllib.parse
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))
import spotify_client as sp
import dj_engine


def get_secret(key, default=""):
    try:
        return st.secrets.get(key, os.environ.get(key, default))
    except Exception:
        return os.environ.get(key, default)


CLIENT_ID     = get_secret("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = get_secret("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI  = get_secret("SPOTIFY_REDIRECT_URI", sp.DEFAULT_REDIRECT)

st.set_page_config(page_title="AI Recs", page_icon="🎧", layout="centered")

# ── Mood + moment definitions (mirrors the Figma mockup) ──────────────────────
VIBES = [
    {"id": "dreamy",     "label": "Dreamy",     "bg": "#4B2D8A", "dot": "#A78BFA"},
    {"id": "chill",      "label": "Chill",      "bg": "#1B3A4B", "dot": "#60A5FA"},
    {"id": "energetic",  "label": "Energetic",  "bg": "#6B1A1A", "dot": "#F87171"},
    {"id": "happy",      "label": "Happy",      "bg": "#3D2E00", "dot": "#FBBF24"},
]
VIBE_MOOD_TEXT = {
    "dreamy": "Dreamy / ambient", "chill": "Calm", "energetic": "Energetic", "happy": "Happy / upbeat",
}

MOMENTS = [
    {"id": "work",    "label": "Work",    "icon": "💼"},
    {"id": "study",   "label": "Study",   "icon": "📖"},
    {"id": "commute", "label": "Commute", "icon": "🚆"},
    {"id": "workout", "label": "Workout", "icon": "🏋️"},
    {"id": "relax",   "label": "Relax",   "icon": "🛋️"},
    {"id": "driving", "label": "Driving", "icon": "🚗"},
]
MOMENT_ACTIVITY_TEXT = {
    "work": "Focus / work / study", "study": "Focus / work / study",
    "commute": "Commute / driving", "workout": "Workout / exercise",
    "relax": "Relaxing / sleep / background", "driving": "Commute / driving",
}

st.markdown("""
<style>
  .stApp { background:#0f0f0f; }
  #MainMenu, header, footer { visibility:hidden; }
  .block-container { max-width:460px; padding-top:1.2rem; }

  .stApp, .stApp p, .stApp span, .stApp label,
  .stApp div, .stApp li, .stApp small,
  div[data-testid="stMarkdownContainer"] p,
  div[data-testid="stMarkdownContainer"] li,
  div[data-testid="stMarkdownContainer"] span { color:#e8eef0 !important; }
  h1,h2,h3,h4,h5,h6 { color:#ffffff !important; }

  .stTextInput input { background:#1e1e1e !important; border-color:#2a2a2a !important; color:#e8eef0 !important; border-radius:12px !important; }
  .stSlider [role="slider"] { background:#22c55e !important; }
  .stSlider > div > div > div > div { background:#22c55e !important; }
  .stToggle [role="switch"][aria-checked="true"] { background:#22c55e !important; }

  .stAlert p { color:#e8eef0 !important; }
  .stSuccess { background:#0d2116 !important; border-color:#22c55e !important; }
  .stSuccess p { color:#22c55e !important; }
  .stInfo { background:#0e1a2a !important; border-color:#1a6fa3 !important; }
  .stWarning { background:#1a1400 !important; border-color:#8a7000 !important; }
  .stError { background:#1a0e0e !important; border-color:#7a2020 !important; }
  .stCaption, [data-testid="stCaptionContainer"] { color:#8a979d !important; }

  /* Default (unselected) buttons — vibe / moment cards */
  .stButton > button {
    background:#1e1e1e !important; color:#fff !important;
    border:2px solid transparent !important; border-radius:14px !important;
    font-weight:600 !important; width:100% !important;
  }
  .stButton > button:hover { border-color:#3a3a3a !important; }

  /* Selected state via key-based targeting is not possible in pure CSS,
     so selection is shown with an inline badge inside the button label. */

  /* Primary CTA (Show my recommendations / Generate) */
  button[kind="primary"] {
    background:#22c55e !important; color:#000 !important;
    border:none !important; border-radius:30px !important; font-weight:700 !important;
    padding:14px !important; font-size:15px !important;
  }
  button[kind="primary"]:hover { background:#1db954 !important; }

  div[data-testid="stLinkButton"] a {
    background:#22c55e !important; color:#000 !important;
    border-radius:20px !important; font-weight:700 !important;
    border:none !important; padding:6px 18px !important; text-decoration:none !important;
  }

  .greeting { font-size:26px; font-weight:700; color:#fff; margin:6px 0 0; }
  .greeting-sub { color:#888; font-size:13px; margin:2px 0 14px; }
  .beta-badge {
    display:inline-block; background:#1f3a2a; color:#4ade80; font-size:10px;
    font-weight:700; padding:2px 8px; border-radius:6px; letter-spacing:.05em; margin-left:8px;
  }
  .section-label { color:#fff; font-weight:700; font-size:15px; margin:18px 0 0; }
  .section-sub { color:#666; font-size:12px; margin:2px 0 8px; }

  .track-card {
    display:flex; gap:14px; align-items:flex-start; background:#1a1a1a;
    border:1px solid #262626; border-radius:12px; padding:12px 14px; margin-bottom:10px;
  }
  .track-card img { width:52px; height:52px; border-radius:8px; flex-shrink:0; object-fit:cover; }
  .track-art-placeholder { width:52px; height:52px; border-radius:8px; flex-shrink:0; background:#262626; }
  .track-meta { flex:1; min-width:0; }
  .track-title  { color:#fff; font-weight:700; font-size:14px; margin-bottom:2px; }
  .track-artist { color:#888; font-size:12px; }
  .track-pop    { color:#5a7a6a; font-size:11px; margin-top:2px; }
  .track-why    { color:#22c55e; font-size:12px; margin-top:5px; line-height:1.4; }

  .pill {
    display:inline-block; background:#0d2116; color:#22c55e;
    border:1px solid #22c55e; border-radius:20px;
    padding:3px 10px; font-size:11px; margin:2px 4px 2px 0;
  }

  .debug-box { background:#141414; border:1px solid #262626; border-radius:10px; padding:12px 16px; margin-bottom:10px; font-size:12px; }
  .debug-row { color:#8a979d; margin:2px 0; line-height:1.5; }
  .debug-row b { color:#c8d6db; }
  .debug-track { color:#c8d6db; margin:3px 0; padding-left:8px; border-left:2px solid #22c55e; }
  .debug-track .dt-ok  { color:#22c55e; font-size:10px; }
  .debug-track .dt-err { color:#ff6b6b; font-size:10px; }

  hr { border-color:#262626 !important; }
</style>
""", unsafe_allow_html=True)

# ── Session defaults ───────────────────────────────────────────────────────────
for k, v in {
    "sp_token": None, "sp_user": None, "sp_top": None, "sp_top_err": None,
    "blocked": [], "results": [], "last_intent": "",
    "debug_log": [], "view": "controls",
    "sel_vibe": "chill", "sel_moment": "study", "adventurous": 3,
    "free_text": "",
}.items():
    st.session_state.setdefault(k, v)


# ── OAuth ─────────────────────────────────────────────────────────────────────
def handle_oauth_redirect():
    code = st.query_params.get("code")
    if code and not st.session_state.sp_token:
        try:
            tok = sp.exchange_code(CLIENT_ID, CLIENT_SECRET, code, REDIRECT_URI)
            token = tok.get("access_token")
            st.session_state.sp_token = token
            try:
                st.session_state.sp_user = sp.get_me(token)
            except Exception as me_err:
                if "403" in str(me_err):
                    for k in ["sp_token", "sp_user", "sp_top", "sp_top_err"]:
                        st.session_state[k] = None
                    st.query_params.clear()
                    st.error(
                        "**Spotify login blocked (403).** The account you logged in with isn't in the app's allowlist.\n\n"
                        "Add the exact Spotify email at: **developer.spotify.com/dashboard → your app → Users and Access**"
                    )
                    auth_url2 = sp.get_auth_url(CLIENT_ID, REDIRECT_URI, state=str(uuid.uuid4())[:8])
                    c1, c2 = st.columns(2)
                    with c1:
                        st.link_button("🔄  Try a different account", auth_url2, use_container_width=True)
                    with c2:
                        if st.button("🏠  Back to login screen", use_container_width=True):
                            st.query_params.clear()
                            st.rerun()
                    st.stop()
                raise
            tracks, top_err = sp.get_top_tracks(token, limit=20)
            st.session_state.sp_top     = tracks
            st.session_state.sp_top_err = top_err
            st.query_params.clear()
            st.rerun()
        except Exception as e:
            st.error(f"Spotify login failed: {e}")


if not CLIENT_ID or not CLIENT_SECRET:
    st.warning("Spotify credentials missing — add SPOTIFY_CLIENT_ID / CLIENT_SECRET to .streamlit/secrets.toml.")
    st.stop()

handle_oauth_redirect()

# ── Login gate ─────────────────────────────────────────────────────────────────
if not st.session_state.sp_token:
    st.markdown(
        '<div style="text-align:center;padding:14px 0 4px;">'
        '<h1 style="font-size:24px;margin:0;color:#fff;">🎧 AI Recs<span class="beta-badge">BETA</span></h1>'
        '<p style="color:#888;margin:8px 0 0;font-size:13px;">'
        'Log in with Spotify to get AI-curated recommendations from your real library.</p>'
        '</div>', unsafe_allow_html=True)
    auth_url = sp.get_auth_url(CLIENT_ID, REDIRECT_URI, state=str(uuid.uuid4())[:8])
    st.link_button("🎵  Log in with Spotify", auth_url, use_container_width=True)
    st.caption(f"Redirect URI: `{REDIRECT_URI}` — must match your Spotify app dashboard exactly.")
    if st.query_params:
        if st.button("🔄  Clear & retry"):
            st.query_params.clear()
            st.rerun()
    st.stop()

user = st.session_state.sp_user or {}
top_count = len(st.session_state.sp_top or [])
name = user.get("display_name") or user.get("id") or "there"
if name in ("Spotify User", "me"):
    name = "there"
email = user.get("email", "")


# ── Header row: title + logout ────────────────────────────────────────────────
h1, h2 = st.columns([5, 1])
with h1:
    st.markdown(
        '<span style="color:#fff;font-weight:700;font-size:17px;">🎧 AI Recs</span>'
        '<span class="beta-badge">BETA</span>', unsafe_allow_html=True)
with h2:
    if st.button("🚪 Log out", use_container_width=True):
        for k in ["sp_token", "sp_user", "sp_top", "sp_top_err", "results", "blocked", "debug_log"]:
            st.session_state[k] = None if k in ("sp_token", "sp_user", "sp_top", "sp_top_err") else []
        st.session_state["last_intent"] = ""
        st.session_state["view"] = "controls"
        st.query_params.clear()
        st.rerun()

if top_count:
    st.caption(f"Logged in{' as ' + name if name != 'there' else ''} · {top_count} top tracks loaded")


# ══════════════════════════════════════════════════════════════════════════════
#  VIEW: CONTROLS  ("Hi {name}" screen — pick vibe / moment / novelty)
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.view == "controls":
    st.markdown(f'<div class="greeting">Hi {name} 👋</div>', unsafe_allow_html=True)
    st.markdown('<div class="greeting-sub">What are we listening to today?</div>', unsafe_allow_html=True)

    st.session_state.free_text = st.text_input(
        "Describe the vibe, mood, activity or artist…",
        value=st.session_state.free_text,
        placeholder="Describe the vibe, mood, activity or artist…",
        label_visibility="collapsed",
    )

    st.markdown('<div class="section-label">How are you feeling?</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Pick your vibe</div>', unsafe_allow_html=True)
    vc = st.columns(2)
    for i, v in enumerate(VIBES):
        with vc[i % 2]:
            selected = st.session_state.sel_vibe == v["id"]
            label = f'{"✅ " if selected else ""}{v["label"]}'
            if st.button(label, key=f"vibe_{v['id']}", use_container_width=True):
                st.session_state.sel_vibe = v["id"]
                st.rerun()

    st.markdown('<div class="section-label">What\'s the moment?</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Choose a context</div>', unsafe_allow_html=True)
    mc = st.columns(2)
    for i, m in enumerate(MOMENTS):
        with mc[i % 2]:
            selected = st.session_state.sel_moment == m["id"]
            label = f'{m["icon"]} {"✅ " if selected else ""}{m["label"]}'
            if st.button(label, key=f"moment_{m['id']}", use_container_width=True):
                st.session_state.sel_moment = m["id"]
                st.rerun()

    st.markdown('<div class="section-label">How adventurous?</div>', unsafe_allow_html=True)
    adv = st.slider("Familiar ↔ Adventurous", 1, 5, st.session_state.adventurous, label_visibility="collapsed")
    st.session_state.adventurous = adv

    sandbox = st.toggle("🧪  Sandbox / reset taste", value=False,
        help="Ignore listening history — nothing contaminates your real profile.")
    n_tracks = st.slider("Number of tracks", 6, 20, 10)

    if st.session_state.blocked:
        st.markdown('<span style="color:#ff6b6b;font-size:13px;font-weight:600;">🚫 Blocked artists</span>',
                    unsafe_allow_html=True)
        st.markdown("".join(f'<span class="pill">🚫 {b}</span>' for b in st.session_state.blocked),
                    unsafe_allow_html=True)
        if st.button("Clear blocked artists"):
            st.session_state.blocked = []
            st.rerun()

    show_debug = st.toggle("🔍  Show verbose log", value=False)

    go = st.button("Show my recommendations", use_container_width=True, type="primary")

    if go:
        mood = VIBE_MOOD_TEXT[st.session_state.sel_vibe]
        activity = MOMENT_ACTIVITY_TEXT[st.session_state.sel_moment]
        if st.session_state.free_text.strip():
            mood = f"{mood} — user also said: \"{st.session_state.free_text.strip()}\""

        debug_log = []
        taste = [] if sandbox else (st.session_state.sp_top or [])

        if sandbox:
            debug_log.append(("taste", "Sandbox ON — taste snapshot skipped", []))
        elif taste:
            debug_log.append(("taste",
                f"Taste snapshot ({len(taste)} tracks from your recent listening)", taste[:10]))

        prompt_text = dj_engine.build_prompt(mood, activity, adv, taste, st.session_state.blocked, n_tracks, sandbox)
        debug_log.append(("prompt", "Prompt sent to LLM", [prompt_text]))

        status = st.empty()
        status.info("🤖  Asking the AI to curate your queue…")

        picks, err = dj_engine.generate(
            mood=mood, activity=activity, novelty=adv,
            taste_snapshot=taste, blocked=st.session_state.blocked,
            n=n_tracks, sandbox=sandbox,
        )

        if err:
            debug_log.append(("error", f"LLM error: {err}", []))
            st.session_state.debug_log = debug_log
            status.error(f"AI generation failed: {err}")
        elif not picks:
            debug_log.append(("error", "LLM returned 0 tracks", []))
            st.session_state.debug_log = debug_log
            status.error("The AI returned no tracks — try again.")
        else:
            debug_log.append(("llm_out", f"LLM returned {len(picks)} picks",
                [f"{p['artist']} — {p['title']}" for p in picks]))

            debug_log.append(("ok", "Resolving tracks via Spotify catalog", []))
            status.info(f"🔍  Looking up {len(picks)} tracks in the Spotify catalog…")
            resolved, search_log = [], []
            for p in picks:
                track, serr = sp.search_itunes(p["artist"], p["title"])
                if track:
                    track["why"] = p["why"]
                    resolved.append(track)
                    search_log.append(("ok", f"{p['artist']} — {p['title']}", f"→ {track['name']} by {track['artist']}"))
                else:
                    search_log.append(("err", f"{p['artist']} — {p['title']}", serr or "not found"))

            debug_log.append(("search", f"Spotify catalog: {len(resolved)}/{len(picks)} tracks resolved", search_log))
            st.session_state.debug_log = debug_log

            if not resolved:
                first_err = next((s[2] for s in search_log if s[0] == "err"), "unknown")
                status.error(f"Search failed for all tracks. First error: {first_err}")
            else:
                vibe_lbl = next(v["label"] for v in VIBES if v["id"] == st.session_state.sel_vibe)
                moment_lbl = next(m["label"] for m in MOMENTS if m["id"] == st.session_state.sel_moment)
                st.session_state.results = resolved
                st.session_state.last_intent = (
                    f"{vibe_lbl} vibes · {moment_lbl} · Novelty {adv}/5"
                    + (" · sandbox" if sandbox else "")
                )
                status.success(f"✅  {len(resolved)} of {len(picks)} tracks resolved — queue ready!")
                st.session_state.view = "results"
                st.rerun()

    if show_debug and st.session_state.debug_log:
        st.divider()
        st.markdown('<span style="color:#22c55e;font-size:15px;font-weight:700;">🔍 Verbose Log</span>',
                    unsafe_allow_html=True)
        ICON = {"taste": "🎧", "prompt": "📝", "llm_out": "🤖", "search": "🔎", "ok": "✅", "warn": "⚠️", "error": "❌"}
        for kind, label, items in st.session_state.debug_log:
            icon = ICON.get(kind, "•")
            with st.expander(f"{icon}  {label}", expanded=(kind in ("error", "warn"))):
                if kind == "prompt":
                    st.code(items[0] if items else "", language="text")
                elif kind == "search":
                    for status_flag, inp, out in items:
                        dot = "✅" if status_flag == "ok" else "❌"
                        st.markdown(
                            f'<div class="debug-track"><b>{inp}</b><br>'
                            f'<span class="dt-{"ok" if status_flag=="ok" else "err"}">{dot} {out}</span></div>',
                            unsafe_allow_html=True)
                elif items:
                    for row in items:
                        st.markdown(f'<div class="debug-row">• {row}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="debug-row">{label}</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  VIEW: RESULTS  (track list + "Open in Spotify")
# ══════════════════════════════════════════════════════════════════════════════
else:
    back_col, _ = st.columns([1, 4])
    with back_col:
        if st.button("← Back"):
            st.session_state.view = "controls"
            st.rerun()

    results = st.session_state.results
    vibe_label = next((v["label"] for v in VIBES if v["id"] == st.session_state.sel_vibe), "")
    st.caption(st.session_state.last_intent)
    st.markdown(f'<div class="greeting" style="font-size:20px;">Your {vibe_label} playlist</div>',
                unsafe_allow_html=True)

    if not results:
        st.info("No recommendations yet — go back and hit **Show my recommendations**.")
    else:
        for i, t in enumerate(results):
            c1, c2 = st.columns([7, 1])
            with c1:
                art = (f'<img src="{t["album_art"]}">'
                       if t.get("album_art") else '<div class="track-art-placeholder"></div>')
                pop_html = f'<div class="track-pop">Popularity: {t["popularity"]}/100</div>' if t.get("popularity") else ""
                st.markdown(
                    f'<div class="track-card">{art}'
                    f'<div class="track-meta">'
                    f'<div class="track-title">{t["name"]}</div>'
                    f'<div class="track-artist">{t["artist"]}</div>'
                    f'{pop_html}'
                    f'<div class="track-why">💬 {t["why"]}</div>'
                    f'</div></div>', unsafe_allow_html=True)
            with c2:
                sp_url = "https://open.spotify.com/search/" + urllib.parse.quote(f"{t['artist']} {t['name']}")
                st.link_button("▶", sp_url, help="Search on Spotify")
                if st.button("🚫", key=f"block{i}", help=f"Block {t['artist']}"):
                    first_artist = t["artist"].split(",")[0].strip()
                    if first_artist not in st.session_state.blocked:
                        st.session_state.blocked.append(first_artist)
                    st.rerun()

        st.divider()
        pl_name = st.text_input("💾  Playlist name", value=f"AI Recs · {vibe_label}")

        if st.button("Open in Spotify", use_container_width=True, type="primary"):
            try:
                uid = (st.session_state.sp_user or {}).get("id")
                pl = sp.create_playlist(
                    st.session_state.sp_token, uid, pl_name,
                    description=f"AI Recs — {st.session_state.last_intent}",
                )
                uris = []
                with st.spinner("Finding tracks on Spotify…"):
                    for t in results:
                        track, _ = sp.search_track(st.session_state.sp_token, t["artist"], t["name"])
                        if track and track.get("uri"):
                            uris.append(track["uri"])
                if not uris:
                    st.error("Couldn't resolve any tracks on Spotify to save. Your account may need Premium.")
                else:
                    sp.add_tracks(st.session_state.sp_token, pl["id"], uris)
                    pl_url = pl.get("external_urls", {}).get("spotify", "")
                    st.success(f"✅  Saved {len(uris)} tracks!")
                    if pl_url:
                        st.link_button("🎵  Open playlist in Spotify", pl_url, use_container_width=True)
            except Exception as e:
                st.error(f"Could not save playlist: {e}")

        if st.button("Adjust preferences", use_container_width=True):
            st.session_state.view = "controls"
            st.rerun()
