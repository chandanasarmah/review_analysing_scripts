# 🧭 Spotify Compass — AI-Native Discovery MVP

A functional prototype for the PM Fellowship Growth project. It fixes the **algorithmic
filter bubble** by giving users an **embedded discovery-controls panel**: explicit control
over novelty (risk), mood, taste-reset (sandbox), and negative feedback that actually
sticks — powered by an LLM recommendation engine, resolved against the **real Spotify
catalog** and saved as **real Spotify playlists**.

## Why this is AI-native (not the old recsys)

Spotify deprecated its `/recommendations` + audio-features endpoints for new apps
(Nov 2024). That is the point: traditional collaborative-filtering recommenders optimize a
single engagement objective, converge on familiarity, are opaque, and accept only coarse
like/skip feedback. Here the **LLM is the recommendation brain** — it interprets
natural-language mood/intent, treats **novelty as a tunable parameter**, **explains every
pick**, honors **blocked artists** instantly, and supports a **sandbox taste reset** that
never contaminates the long-term profile. Spotify supplies auth, the real catalog (Search),
and playlist creation.

| Control | Unmet need it solves |
|---|---|
| Novelty / risk dial | Control over recommendation "risk level" |
| Sandbox / reset taste | Reset taste profile + stop playlist contamination |
| Mood selector | Mood-based direct navigation |
| 🚫 Block artist (sticks) | Honor negative feedback |
| Per-track "why" | Transparency / rebuild trust |

## Setup

1. **Create a Spotify app:** https://developer.spotify.com/dashboard → *Create app*.
   - Copy the **Client ID** and **Client Secret**.
   - Under *Redirect URIs* add exactly: `http://127.0.0.1:8501`
2. **Add secrets** to `../.streamlit/secrets.toml` (already gitignored):
   ```toml
   SPOTIFY_CLIENT_ID     = "..."
   SPOTIFY_CLIENT_SECRET = "..."
   SPOTIFY_REDIRECT_URI  = "http://127.0.0.1:8501"
   ```
   (The `OPENCODE_*` keys for the LLM are already there.)
3. **Install deps:** `pip install -r ../requirements.txt`

## Run

```bash
python -m streamlit run mvp/discovery_app.py
```

Open **http://127.0.0.1:8501** (use `127.0.0.1`, not `localhost`, so it matches the Spotify
redirect URI). Click **Log in with Spotify**, approve, and you're in.

## Demo script (proves each unmet need)

1. Mood = **Focus**, novelty **1** → familiar, on-taste focus tracks, each with a reason.
2. Novelty **5** ("break my bubble") → visibly more niche artists (check the popularity score drop).
3. Toggle **Sandbox / reset taste** → results stop reflecting your history.
4. Click **🚫** on a track → that artist is blocked and never returns in the next generation.
5. **Save as Spotify playlist** → a real private playlist appears in your account.

## Files

- `discovery_app.py` — Streamlit UI + OAuth + the discovery-controls panel.
- `spotify_client.py` — Spotify Web API wrapper (auth, search, top items, playlists).
- `dj_engine.py` — the LLM recommendation engine (OpenCode / deepseek-v4-flash).

## Notes & limits

- Full in-app playback needs **Premium** (Web Playback SDK); this MVP uses real playlist
  creation + deep-links, which works for **Free** accounts (the target segment).
- A new Spotify app starts in *development mode* — add your own account under
  *Users and Access* in the dashboard to log in.
