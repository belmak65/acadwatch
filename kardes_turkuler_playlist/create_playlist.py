"""Create a Spotify playlist of Kardeş Türküler's Kurdish and Zazaki songs.

Requires SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET and SPOTIPY_REDIRECT_URI
to be set (see README.md). Run with: python create_playlist.py
"""
import json
from pathlib import Path

import spotipy
from spotipy.oauth2 import SpotifyOAuth

SCOPE = "playlist-modify-public playlist-modify-private"
SONGS_FILE = Path(__file__).parent / "songs.json"
PLAYLIST_NAME = "Kardeş Türküler - Kürtçe & Zazaca"
PLAYLIST_DESCRIPTION = "Kardeş Türküler'in Kürtçe (Kurmancî) ve Zazaca parçaları"
ARTIST_NAME = "Kardeş Türküler"


def load_songs():
    with open(SONGS_FILE, encoding="utf-8") as f:
        return json.load(f)


def find_track_uri(sp, title):
    results = sp.search(q=f'track:{title} artist:{ARTIST_NAME}', type="track", limit=1)
    items = results["tracks"]["items"]
    return items[0]["uri"] if items else None


def main():
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=SCOPE))

    user_id = sp.current_user()["id"]
    playlist = sp.user_playlist_create(
        user_id,
        name=PLAYLIST_NAME,
        public=False,
        description=PLAYLIST_DESCRIPTION,
    )

    track_uris = []
    not_found = []
    for song in load_songs():
        uri = find_track_uri(sp, song["title"])
        if uri:
            track_uris.append(uri)
        else:
            not_found.append(song["title"])

    for i in range(0, len(track_uris), 100):
        sp.playlist_add_items(playlist["id"], track_uris[i:i + 100])

    print(f"Playlist oluşturuldu: {playlist['external_urls']['spotify']}")
    print(f"{len(track_uris)} parça eklendi.")
    if not_found:
        print("Spotify'da bulunamayan parçalar:", ", ".join(not_found))


if __name__ == "__main__":
    main()
