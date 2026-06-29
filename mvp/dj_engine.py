"""
dj_engine.py — the AI recommendation brain for the Discovery MVP.

This replaces Spotify's deprecated /recommendations endpoint. It takes the user's
explicit controls (mood, novelty/risk, activity, exclusions, blocked artists) plus
an OPTIONAL real taste snapshot, and asks the OpenCode LLM (deepseek-v4-flash) to
return a structured, *explained* set of tracks — with novelty as a tunable knob
rather than an engagement side effect.

Reuses the same OpenCode plumbing pattern as the main app (app.py).
"""

import json
import os
import re

try:
    from openai import OpenAI as _OpenAI
    _OPENAI_AVAILABLE = True
except ImportError:
    _OPENAI_AVAILABLE = False


def get_secret(key, default=""):
    """Mirror of app.py _get_secret — st.secrets first, then env."""
    try:
        import streamlit as st
        return st.secrets.get(key, os.environ.get(key, default))
    except Exception:
        return os.environ.get(key, default)


NOVELTY_GUIDE = {
    1: "Stay almost entirely in the user's comfort zone — well-known, familiar, mainstream picks.",
    2: "Mostly familiar with a few gentle stretches into adjacent artists.",
    3: "A balanced mix of familiar anchors and genuinely new artists they likely haven't heard.",
    4: "Lean adventurous — mostly lesser-known / niche artists, only lightly anchored to their taste.",
    5: "Maximum exploration — deliberately break the filter bubble with obscure, off-the-beaten-path artists in adjacent or surprising styles.",
}

SYSTEM_PROMPT = (
    "You are an expert music curator that builds a listening queue from explicit user "
    "controls. You are NOT a black-box engagement optimizer — you obey the user's stated "
    "intent, mood, and novelty level exactly, and you explain every choice in one short, "
    "specific sentence. Never recommend a blocked artist. Output STRICT JSON only."
)


def build_prompt(mood, activity, novelty, taste_snapshot, blocked, n=12, sandbox=False):
    parts = []
    parts.append(f"Build a {n}-track listening queue.")
    parts.append(f"Mood / vibe: {mood or 'no specific mood'}.")
    parts.append(f"Activity / context: {activity or 'general listening'}.")
    parts.append(f"Novelty level {novelty}/5 — {NOVELTY_GUIDE.get(novelty, NOVELTY_GUIDE[3])}")

    if sandbox or not taste_snapshot:
        parts.append(
            "TASTE RESET / SANDBOX is ON: ignore any listening history. Build purely from the "
            "mood, activity and novelty above, as if for a brand-new listener. Do not assume "
            "past favourites."
        )
    else:
        parts.append("The user's recent taste snapshot (anchor familiar picks to this, "
                     "subject to the novelty level):")
        parts.append("; ".join(taste_snapshot[:20]))

    if blocked:
        parts.append("BLOCKED — never include these artists: " + ", ".join(blocked) + ".")

    parts.append(
        "Return STRICT JSON: an array of exactly "
        f"{n} objects, each {{\"artist\": string, \"title\": string, \"why\": string}}. "
        "\"why\" must be ONE short sentence explaining why this fits the mood/novelty. "
        "Real, existing songs only. No commentary, no markdown, JSON array only."
    )
    return "\n".join(parts)


def generate(mood, activity, novelty, taste_snapshot, blocked, n=12, sandbox=False):
    """Return (tracks, error). tracks = list of {artist, title, why}."""
    api_key  = get_secret("OPENCODE_API_KEY")
    base_url = get_secret("OPENCODE_BASE_URL", "https://opencode.ai/zen/go/v1")
    model    = get_secret("OPENCODE_MODEL", "deepseek-v4-flash")

    if not api_key or not _OPENAI_AVAILABLE:
        return [], "OpenCode API key not configured (set OPENCODE_API_KEY in secrets)."

    prompt = build_prompt(mood, activity, novelty, taste_snapshot, blocked, n, sandbox)
    try:
        client = _OpenAI(api_key=api_key, base_url=base_url)
        resp = client.chat.completions.create(
            model=model,
            max_tokens=16384,
            temperature=0.7,  # a little warmth for variety
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        raw = (resp.choices[0].message.content or "").strip()
        raw = re.sub(r"<think>[\s\S]*?</think>", "", raw).strip()
        # Extract the JSON array
        start = raw.find("[")
        end = raw.rfind("]")
        if start == -1 or end == -1:
            return [], "Model did not return a JSON array."
        data = json.loads(raw[start:end + 1])
        tracks = []
        blocked_lower = {b.lower() for b in (blocked or [])}
        for item in data:
            if not isinstance(item, dict):
                continue
            artist = str(item.get("artist", "")).strip()
            title = str(item.get("title", "")).strip()
            why = str(item.get("why", "")).strip()
            if not artist or not title:
                continue
            if artist.lower() in blocked_lower:
                continue  # hard guarantee blocked artists never appear
            tracks.append({"artist": artist, "title": title, "why": why})
        return tracks, None
    except Exception as e:
        return [], f"Recommendation engine failed: {e}"
