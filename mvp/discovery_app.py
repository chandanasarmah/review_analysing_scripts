"""
discovery_app.py — Spotify "Compass" : AI-native Discovery Controls panel.
Run:  python -m streamlit run mvp/discovery_app.py --server.port 8501
Open: http://127.0.0.1:8501
"""

import os
import sys
import uuid
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

st.set_page_config(page_title="Spotify Compass", page_icon="🧭", layout="wide")

st.markdown("""
<style>
  .stApp { background:#0b0e0f; }
  #MainMenu, header, footer { visibility:hidden; }

  /* ── All text white on dark bg ── */
  .stApp, .stApp p, .stApp span, .stApp label,
  .stApp div, .stApp li, .stApp small,
  div[data-testid="stMarkdownContainer"] p,
  div[data-testid="stMarkdownContainer"] li,
  div[data-testid="stMarkdownContainer"] span { color:#e8eef0 !important; }
  h1,h2,h3,h4,h5,h6 { color:#ffffff !important; }

  /* ── Inputs ── */
  .stSelectbox label, .stSlider label, .stToggle label,
  .stTextInput label, .stNumberInput label { color:#c8d6db !important; font-size:13px !important; }
  div[data-baseweb="select"] > div { background:#111518 !important; border-color:#2a3a3e !important; color:#e8eef0 !important; }
  div[data-baseweb="select"] span { color:#e8eef0 !important; }
  div[data-baseweb="popover"] li { color:#e8eef0 !important; background:#111518 !important; }
  div[data-baseweb="popover"] li:hover { background:#1e2a2e !important; }
  .stSlider [role="slider"] { background:#1DB954 !important; }
  .stSlider > div > div > div > div { background:#1DB954 !important; }
  .stTextInput input { background:#111518 !important; border-color:#2a3a3e !important; color:#e8eef0 !important; }

  /* ── Alerts ── */
  .stAlert p { color:#e8eef0 !important; }
  .stSuccess { background:#0d2116 !important; border-color:#1DB954 !important; }
  .stSuccess p { color:#1DB954 !important; }
  .stInfo { background:#0e1a2a !important; border-color:#1a6fa3 !important; }
  .stWarning { background:#1a1400 !important; border-color:#8a7000 !important; }
  .stError { background:#1a0e0e !important; border-color:#7a2020 !important; }
  .stCaption, [data-testid="stCaptionContainer"] { color:#8a979d !important; }

  /* ── Buttons ── */
  .stButton > button {
    background:#1DB954 !important; color:#000 !important;
    border:none !important; border-radius:20px !important; font-weight:700 !important;
  }
  .stButton > button:hover { background:#17a349 !important; }
  /* Logout button — red */
  div[data-testid="column"]:last-child .stButton > button {
    background:#7a2020 !important; color:#ffcccc !important;
  }
  div[data-testid="column"]:last-child .stButton > button:hover { background:#a33030 !important; }
  div[data-testid="stLinkButton"] a {
    background:#1DB954 !important; color:#000 !important;
    border-radius:20px !important; font-weight:700 !important;
    border:none !important; padding:6px 18px !important; text-decoration:none !important;
  }
  .stToggle [role="switch"][aria-checked="true"] { background:#1DB954 !important; }

  /* ── Track card ── */
  .track-card {
    display:flex; gap:14px; align-items:flex-start; background:#111518;
    border:1px solid #1e2a2e; border-radius:12px; padding:12px 14px; margin-bottom:10px;
  }
  .track-card img { width:56px; height:56px; border-radius:8px; flex-shrink:0; object-fit:cover; }
  .track-art-placeholder { width:56px; height:56px; border-radius:8px; flex-shrink:0; background:#1e2a2e; }
  .track-meta { flex:1; min-width:0; }
  .track-title  { color:#fff; font-weight:700; font-size:15px; margin-bottom:2px; }
  .track-artist { color:#8a979d; font-size:12.5px; }
  .track-pop    { color:#5a7a6a; font-size:11px; margin-top:2px; }
  .track-why    { color:#1DB954; font-size:12px; margin-top:5px; line-height:1.4; }

  /* ── Pill ── */
  .pill {
    display:inline-block; background:#0d2116; color:#1DB954;
    border:1px solid #1DB954; border-radius:20px;
    padding:3px 10px; font-size:11px; margin:2px 4px 2px 0;
  }

  /* ── Verbose / debug panel ── */
  .debug-box {
    background:#0d1a1f; border:1px solid #1e3040; border-radius:10px;
    padding:12px 16px; margin-bottom:10px; font-size:12px;
  }
  .debug-label {
    color:#1DB954; font-size:11px; font-weight:700;
    text-transform:uppercase; letter-spacing:.06em; margin-bottom:6px;
  }
  .debug-row { color:#8a979d; margin:2px 0; line-height:1.5; }
  .debug-row b { color:#c8d6db; }
  .debug-track { color:#c8d6db; margin:3px 0; padding-left:8px; border-left:2px solid #1DB954; }
  .debug-track .dt-ok  { color:#1DB954; font-size:10px; }
  .debug-track .dt-err { color:#ff6b6b; font-size:10px; }

  /* ── Novelty label ── */
  .novelty-label { color:#1DB954; font-size:12px; font-weight:600; margin-top:-6px; margin-bottom:4px; }

  hr { border-color:#1e2a2e !important; }
</style>
""", unsafe_allow_html=True)

# ── Session defaults ───────────────────────────────────────────────────────────
for k, v in {
    "sp_token": None, "sp_user": None, "sp_top": None, "sp_top_err": None,
    "blocked": [], "results": [], "last_intent": "",
    "debug_log": [],
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
                    for k in ["sp_token","sp_user","sp_top","sp_top_err"]:
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


# ── Hero ───────────────────────────────────────────────────────────────────────
st.markdown(
    '<div style="text-align:center;padding:14px 0 4px;">'
    '<h1 style="font-size:28px;margin:0;color:#fff;">🧭 Spotify Compass</h1>'
    '<p style="color:#8a979d;margin:4px 0 0;font-size:13px;">'
    'Steerable, explainable discovery — you control the risk, the mood, and the bubble.</p>'
    '</div>',
    unsafe_allow_html=True,
)

if not CLIENT_ID or not CLIENT_SECRET:
    st.warning("Spotify credentials missing — add SPOTIFY_CLIENT_ID / CLIENT_SECRET to .streamlit/secrets.toml.")
    st.stop()

handle_oauth_redirect()

# ── Login gate ─────────────────────────────────────────────────────────────────
if not st.session_state.sp_token:
    auth_url = sp.get_auth_url(CLIENT_ID, REDIRECT_URI, state=str(uuid.uuid4())[:8])
    st.info("Log in with Spotify to use your real library and save real playlists.")
    st.link_button("🎵  Log in with Spotify", auth_url)
    st.caption(f"Redirect URI: `{REDIRECT_URI}` — must match your Spotify app dashboard exactly.")
    # Force-clear any stale query params
    if st.query_params:
        if st.button("🔄  Clear & retry"):
            st.query_params.clear()
            st.rerun()
    st.stop()

user = st.session_state.sp_user or {}
top_count = len(st.session_state.sp_top or [])
top_err   = st.session_state.get("sp_top_err")
from_token = user.get("_from_token", False)
name  = user.get("display_name") or user.get("id") or "Spotify User"
if name == "Spotify User" and user.get("id") and user["id"] != "unknown":
    name = user["id"]
email = user.get("email", "")

col_user, col_logout = st.columns([5, 1])
with col_user:
    label = f"✅  Logged in with Spotify · {name}"
    if email:
        label += f" ({email})"
    if top_count:
        label += f" · {top_count} top tracks loaded"
    st.success(label)
with col_logout:
    if st.button("🚪 Log out", use_container_width=True):
        for k in ["sp_token","sp_user","sp_top","sp_top_err","results","blocked","debug_log"]:
            st.session_state[k] = None if k in ("sp_token","sp_user","sp_top","sp_top_err") else []
        st.session_state["last_intent"] = ""
        st.query_params.clear()
        st.rerun()

# ── Layout ─────────────────────────────────────────────────────────────────────
left, right = st.columns([1, 1.6], gap="large")

with left:
    st.markdown('<span style="color:#1DB954;font-size:17px;font-weight:700;">🎛️ Discovery Controls</span>', unsafe_allow_html=True)

    mood = st.selectbox("🎭  Mood",
        ["Calm", "Energetic", "Focus", "Melancholy", "Happy / upbeat",
         "Workout hype", "Romantic", "Nostalgic", "Dreamy / ambient", "Angsty"], index=2)

    activity = st.selectbox("📍  Context",
        ["Focus / work / study", "Workout / exercise", "Commute / driving",
         "Relaxing / sleep / background", "Party / social", "Just listening"], index=0)

    novelty = st.slider("🎚️  Novelty — familiar ↔ adventurous", 1, 5, 3,
        help="1 = comfort zone · 5 = break my bubble")
    novelty_labels = {1:"😌 Comfort zone", 2:"🙂 Mostly familiar", 3:"⚖️ Balanced mix",
                      4:"🌿 Lean adventurous", 5:"🚀 Break my bubble"}
    st.markdown(f'<div class="novelty-label">{novelty_labels[novelty]}</div>', unsafe_allow_html=True)

    sandbox = st.toggle("🧪  Sandbox / reset taste", value=False,
        help="Ignore listening history — nothing contaminates your real profile.")

    n = st.slider("🎵  Number of tracks", 6, 20, 10)

    if st.session_state.blocked:
        st.markdown('<span style="color:#ff6b6b;font-size:13px;font-weight:600;">🚫 Blocked artists</span>',
                    unsafe_allow_html=True)
        st.markdown("".join(f'<span class="pill">🚫 {b}</span>' for b in st.session_state.blocked),
                    unsafe_allow_html=True)
        if st.button("Clear blocked artists", key="clearblock"):
            st.session_state.blocked = []
            st.rerun()

    go = st.button("✨  Generate queue", use_container_width=True, type="primary")

    # ── verbose toggle + connectivity test ────────────────────────────────────
    st.divider()
    show_debug = st.toggle("🔍  Show verbose log", value=False)
    if st.button("🩺  Test catalog lookup", help="Quick check: can we find tracks?"):
        track, serr = sp.search_itunes("Brian Eno", "An Ending Ascent")
        if serr:
            st.error(f"Spotify catalog lookup failed: {serr}")
        else:
            st.success(f"✅ Found: {track['name']} by {track['artist']} · {track['album']}")


# ── Generate ──────────────────────────────────────────────────────────────────
if go:
    debug_log = []
    taste = [] if sandbox else (st.session_state.sp_top or [])

    # ── Log: taste snapshot ────────────────────────────────────────────────────
    if sandbox:
        debug_log.append(("taste", "Sandbox ON — taste snapshot skipped", []))
    elif taste:
        debug_log.append(("taste",
            f"Taste snapshot ({len(taste)} tracks from your recent listening)",
            taste[:10]))

    # ── Log: prompt ───────────────────────────────────────────────────────────
    prompt_text = dj_engine.build_prompt(mood, activity, novelty, taste, st.session_state.blocked, n, sandbox)
    debug_log.append(("prompt", "Prompt sent to LLM", [prompt_text]))

    status = st.empty()
    status.info("🤖  Asking the AI to curate your queue…")

    picks, err = dj_engine.generate(
        mood=mood, activity=activity, novelty=novelty,
        taste_snapshot=taste, blocked=st.session_state.blocked,
        n=n, sandbox=sandbox,
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
        # ── Log: LLM output ───────────────────────────────────────────────────
        debug_log.append(("llm_out",
            f"LLM returned {len(picks)} picks",
            [f"{p['artist']} — {p['title']}" for p in picks]))

        # ── Resolve via Spotify catalog ───────────────────────────────────────
        debug_log.append(("ok", "Resolving tracks via Spotify catalog", []))
        status.info(f"🔍  Looking up {len(picks)} tracks in the Spotify catalog…")
        resolved = []
        search_log = []
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
            st.session_state.results = resolved
            st.session_state.last_intent = (
                f"{mood} · {activity} · novelty {novelty}/5"
                + (" · sandbox" if sandbox else "")
            )
            status.success(f"✅  {len(resolved)} of {len(picks)} tracks resolved — queue ready!")


# ── Queue ─────────────────────────────────────────────────────────────────────
with right:
    st.markdown('<span style="color:#1DB954;font-size:17px;font-weight:700;">🎶 Your Queue</span>',
                unsafe_allow_html=True)

    results = st.session_state.results
    if not results:
        st.markdown(
            '<p style="color:#5a7a6a;font-size:13px;margin-top:12px;">'
            'Set controls on the left and hit <strong style="color:#1DB954;">✨ Generate queue</strong>. '
            'Every track comes with a one-line reason — block any artist to exclude them.</p>',
            unsafe_allow_html=True)
    else:
        st.caption(f"Intent: {st.session_state.last_intent}  ·  {len(results)} tracks")
        for i, t in enumerate(results):
            c1, c2 = st.columns([7, 1])
            with c1:
                art = (f'<img src="{t["album_art"]}">'
                       if t.get("album_art")
                       else '<div class="track-art-placeholder"></div>')
                pop_html = f'<div class="track-pop">Popularity: {t["popularity"]}/100</div>' if t.get("popularity") else ""
                st.markdown(
                    f'<div class="track-card">{art}'
                    f'<div class="track-meta">'
                    f'<div class="track-title">{t["name"]}</div>'
                    f'<div class="track-artist">{t["artist"]}</div>'
                    f'{pop_html}'
                    f'<div class="track-why">💬 {t["why"]}</div>'
                    f'</div></div>',
                    unsafe_allow_html=True)
            with c2:
                import urllib.parse as _up
                sp_url = "https://open.spotify.com/search/" + _up.quote(f"{t['artist']} {t['name']}")
                st.link_button("▶", sp_url, help="Search on Spotify")
                if st.button("🚫", key=f"block{i}", help=f"Block {t['artist']}"):
                    first_artist = t["artist"].split(",")[0].strip()
                    if first_artist not in st.session_state.blocked:
                        st.session_state.blocked.append(first_artist)
                    st.rerun()

        st.divider()
        pl_name = st.text_input("💾  Playlist name", value=f"Compass · {mood} ({activity})")
        if st.button("💾  Save as Spotify playlist", use_container_width=True):
            try:
                uid = (st.session_state.sp_user or {}).get("id")
                pl = sp.create_playlist(
                    st.session_state.sp_token, uid, pl_name,
                    description=f"Spotify Compass — {st.session_state.last_intent}",
                )
                # Resolve URIs now using the logged-in user's token
                uris = []
                with st.spinner("Finding tracks on Spotify…"):
                    for t in results:
                        query = t.get("_query") or f"{t['artist']} {t['name']}"
                        track, _ = sp.search_track(st.session_state.sp_token,
                                                   t["artist"], t["name"])
                        if track and track.get("uri"):
                            uris.append(track["uri"])
                if not uris:
                    st.error("Couldn't resolve any tracks on Spotify to save. Your account may need Premium.")
                else:
                    sp.add_tracks(st.session_state.sp_token, pl["id"], uris)
                    pl_url = pl.get("external_urls", {}).get("spotify", "")
                    st.success(f"✅  Saved {len(uris)} tracks! [Open in Spotify]({pl_url})")
            except Exception as e:
                st.error(f"Could not save playlist: {e}")


# ── Verbose log panel ─────────────────────────────────────────────────────────
if show_debug and st.session_state.debug_log:
    st.divider()
    st.markdown('<span style="color:#1DB954;font-size:15px;font-weight:700;">🔍 Verbose Log</span>',
                unsafe_allow_html=True)

    ICON = {"taste":"🎧", "prompt":"📝", "llm_out":"🤖", "search":"🔎",
            "ok":"✅", "warn":"⚠️", "error":"❌"}

    for kind, label, items in st.session_state.debug_log:
        icon = ICON.get(kind, "•")
        with st.expander(f"{icon}  {label}", expanded=(kind in ("error","warn"))):
            if kind == "prompt":
                st.code(items[0] if items else "", language="text")
            elif kind == "search":
                for status_flag, inp, out in items:
                    dot = "✅" if status_flag == "ok" else "❌"
                    st.markdown(
                        f'<div class="debug-track">'
                        f'<b>{inp}</b><br>'
                        f'<span class="dt-{"ok" if status_flag=="ok" else "err"}">{dot} {out}</span>'
                        f'</div>',
                        unsafe_allow_html=True)
            elif items:
                for row in items:
                    st.markdown(
                        f'<div class="debug-row">• {row}</div>',
                        unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="debug-row">{label}</div>', unsafe_allow_html=True)
