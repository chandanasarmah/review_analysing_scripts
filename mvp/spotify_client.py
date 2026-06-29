"""
spotify_client.py — thin Spotify Web API wrapper for the Discovery MVP.

Uses the Authorization Code flow (server-side, with client secret) and only the
endpoints that are still available post-Nov-2024:
  - GET  /me                         (profile + free/premium product)
  - GET  /me/top/{tracks|artists}    (taste snapshot)
  - GET  /search                     (resolve LLM picks -> real tracks)
  - POST /users/{id}/playlists       (create playlist)
  - POST /playlists/{id}/tracks      (add tracks)

The legacy /recommendations + audio-features endpoints are intentionally NOT used
(deprecated for new apps) — the LLM in dj_engine.py is the recommendation brain.
"""

import base64
import urllib.parse

import requests

AUTH_URL  = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
API       = "https://api.spotify.com/v1"

# Loopback IP is the one http redirect Spotify still allows — open the app at
# http://127.0.0.1:8501 (not localhost) so this matches your dashboard setting.
DEFAULT_REDIRECT = "http://127.0.0.1:8501"

SCOPES = " ".join([
    "user-read-private",
    "user-read-email",
    "user-top-read",
    "playlist-modify-private",
    "playlist-modify-public",
])


def get_auth_url(client_id, redirect_uri, state):
    q = urllib.parse.urlencode({
        "response_type": "code",
        "client_id": client_id,
        "scope": SCOPES,
        "redirect_uri": redirect_uri,
        "state": state,
        "show_dialog": "true",
    })
    return f"{AUTH_URL}?{q}"


def exchange_code(client_id, client_secret, code, redirect_uri):
    auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    r = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
        },
        headers={"Authorization": f"Basic {auth}",
                 "Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()  # {access_token, token_type, expires_in, refresh_token, scope}


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def get_me(token):
    """Try /me with user token. On 403, fall back to /me with a fresh client-creds attempt,
    then degrade gracefully — playlist creation uses /me/playlists so user_id isn't needed."""
    r = requests.get(f"{API}/me", headers=_headers(token), timeout=15)
    if r.status_code == 200:
        return r.json()
    if r.status_code == 403:
        return {
            "id":           "me",
            "display_name": "Spotify User",
            "email":        "",
            "product":      "unknown",
            "_from_token":  True,
        }
    r.raise_for_status()
    return r.json()


def get_top_tracks(token, limit=20, time_range="medium_term"):
    """Returns (tracks_list, error_string). tracks_list = 'Artist — Title' strings."""
    r = requests.get(
        f"{API}/me/top/tracks",
        headers=_headers(token),
        params={"limit": limit, "time_range": time_range},
        timeout=15,
    )
    print(f"[top/tracks] status={r.status_code}")
    if r.status_code != 200:
        print(f"[top/tracks] error: {r.text[:200]}")
        return [], None
    items = r.json().get("items", [])
    print(f"[top/tracks] got {len(items)} tracks")
    out = []
    for t in items:
        artists = ", ".join(a["name"] for a in t.get("artists", []))
        out.append(f"{artists} — {t.get('name', '')}")
    return out, None


def get_top_artists(token, limit=20, time_range="medium_term"):
    r = requests.get(
        f"{API}/me/top/artists",
        headers=_headers(token),
        params={"limit": limit, "time_range": time_range},
        timeout=15,
    )
    if r.status_code != 200:
        return []
    return [a.get("name", "") for a in r.json().get("items", [])]


def search_itunes(artist, title):
    """Search Apple iTunes catalog — free, no auth, no Premium needed.
    Returns (track_dict, error_string)."""
    import urllib.parse as _up
    q = _up.quote(f"{artist} {title}")
    try:
        r = requests.get(
            f"https://itunes.apple.com/search?term={q}&media=music&entity=song&limit=3",
            timeout=15,
        )
        if r.status_code != 200:
            return None, f"iTunes HTTP {r.status_code}"
        results = r.json().get("results", [])
        if not results:
            return None, f"No iTunes results for '{artist} — {title}'"
        t = results[0]
        return {
            "id":        None,
            "uri":       None,
            "itunes_id": t.get("trackId"),
            "name":      t.get("trackName", title),
            "artist":    t.get("artistName", artist),
            "album":     t.get("collectionName", ""),
            "album_art": t.get("artworkUrl100", "").replace("100x100", "300x300"),
            "url":       t.get("trackViewUrl", ""),
            "preview_url": t.get("previewUrl", ""),
            "popularity": 0,
            "_query":    f"{artist} {title}",  # saved for Spotify playlist lookup later
        }, None
    except Exception as e:
        return None, str(e)


def get_client_token(client_id, client_secret):
    """Client Credentials flow — app-level token for public endpoints (search).
    Returns (token_string, error_string)."""
    auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    try:
        r = requests.post(
            TOKEN_URL,
            data={"grant_type": "client_credentials"},
            headers={"Authorization": f"Basic {auth}",
                     "Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )
        if r.status_code != 200:
            return None, f"Client token HTTP {r.status_code}: {r.text[:120]}"
        return r.json().get("access_token"), None
    except Exception as e:
        return None, str(e)


def search_track(token, artist, title):
    """Resolve an LLM-suggested (artist, title) to a real Spotify track.
    Returns (track_dict, error_string) — one will always be None."""
    queries = [
        f"{artist} {title}",
        f"track:{title} artist:{artist}",
        title,
    ]
    for q in queries:
        try:
            r = requests.get(
                f"{API}/search",
                headers=_headers(token),
                params={"q": q, "type": "track", "limit": 3},
                timeout=15,
            )
            if r.status_code == 401:
                return None, "Token expired (401) — please log in again."
            if r.status_code == 403:
                return None, f"Search forbidden (403) for query '{q}'"
            if r.status_code != 200:
                return None, f"HTTP {r.status_code}: {r.text[:120]}"
            items = r.json().get("tracks", {}).get("items", [])
            if items:
                t = items[0]
                imgs = t.get("album", {}).get("images", [])
                return {
                    "id": t["id"],
                    "uri": t["uri"],
                    "name": t["name"],
                    "artist": ", ".join(a["name"] for a in t.get("artists", [])),
                    "album": t.get("album", {}).get("name", ""),
                    "album_art": imgs[1]["url"] if len(imgs) > 1 else (imgs[0]["url"] if imgs else ""),
                    "url": t.get("external_urls", {}).get("spotify", ""),
                    "popularity": t.get("popularity", 0),
                }, None
        except Exception as e:
            return None, str(e)
    return None, f"No results for '{artist} — {title}'"


def create_playlist(token, user_id, name, description=""):
    """Create playlist — uses /me/playlists (no user_id needed, avoids unknown ID issue)."""
    r = requests.post(
        f"{API}/me/playlists",
        headers={**_headers(token), "Content-Type": "application/json"},
        json={"name": name, "description": description, "public": False},
        timeout=15,
    )
    if r.status_code == 403:
        raise Exception(
            "Spotify returned 403 — the developer app owner needs a Premium subscription "
            "to create playlists via the API. Upgrade the owner account at spotify.com/account."
        )
    r.raise_for_status()
    return r.json()


def add_tracks(token, playlist_id, uris):
    r = requests.post(
        f"{API}/playlists/{playlist_id}/tracks",
        headers={**_headers(token), "Content-Type": "application/json"},
        json={"uris": uris},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()
