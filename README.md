# Spotify Clone (free, no API key)
<img width="1200" height="604" alt="image" src="https://github.com/user-attachments/assets/f6e0bec6-7aff-4191-b658-06608be93bb3" />


A Spotify-style music web player in **one Python file**. It uses Apple's free
**iTunes Search API**, so there is no account, no API key and no sign-up.

> You can test it live by spotify.paio.hackclub.app
---

## Quick start

1. Install **Python 3.7 or newer** (no extra packages are needed).
2. Put `spotify_clone.py` anywhere you like.
3. Run it:

   ```bash
   python spotify_clone.py
   ```

   On Mac/Linux you may need `python3 spotify_clone.py`.
4. Your browser opens by itself. If not, open the address printed in the
   terminal (for example `http://spotify.local` or `http://localhost:8080`).
5. Press `Ctrl + C` in the terminal to stop it.

When it starts, the terminal runs a quick connection check and prints
`Apple iTunes: connected, N songs` if everything works.


## Features

**Browsing**
- Home page with trending songs, popular albums, Bollywood and hip-hop shelves
- Search for songs, albums and artists, with All / Songs / Artists / Albums filters
- Top result card, plus Browse tiles for 20 genres (Pop, Bollywood, Punjabi, Tamil, Telugu, K-Pop...)
- Album, artist and genre pages
- Recent searches remembered on the Browse page
- "More from ..." shelves on Home, based on the artists you like and play most

**Player**
- Play, pause, next, previous, seek bar, volume, mute
- Shuffle and repeat (off / all / one)
- Queue panel, "Play next", click a queue item to jump to it
- Sleep timer (5 to 60 minutes, or end of the current song)
- Media keys and the browser media controls work
- The last song you played shows up (paused) when you reopen the page

**Your library (saved in your browser)**
- Liked Songs
- Create, rename, delete playlists; re-order songs inside a playlist
- Follow artists
- Library page and Stats page (top artists, counts, recently played)
- Export and import your library as a JSON file

**Settings** (click the round profile icon, top right)
- Store country (changes charts and results; 15 countries)
- Hide explicit songs
- Sleep timer, keyboard shortcuts, clear all data


## Troubleshooting

**The terminal says `Apple iTunes: PROBLEM`**
Your network is blocking Apple. Check your firewall, VPN or proxy, or try a
phone hotspot. The exact error is printed in the terminal.

**Home says "Could not load music from Apple"**
Same cause as above. Run with `--verbose` to see what is failing.

**Charts are empty but search works**
Apple's chart feed is separate from search. The app falls back to a search for
"top hits" automatically. Try a different store country in Settings.

**"Could not edit the hosts file"**
That only affects the nice `spotify.local` name. The app falls back to
`http://localhost:PORT`. Use `--no-hosts` to skip it on purpose. Run as
Administrator (Windows) or with `sudo` (Mac/Linux) if you want `spotify.local`.

**"Ports 80 and 8080 are both busy"**
Close the other program or choose a port: `--port 9000`.

**A song is greyed out or says "No preview available"**
Apple does not provide a preview for every track. Skip to another one.

**Too many requests / results suddenly stop**
Apple limits how often one connection can search (roughly 20 per minute).
Wait a minute and try again. Results are cached for 5 minutes to help.

**Nothing plays**
Browsers block autoplay until you click something. Click a play button once.
Also check the volume bar and that the tab is not muted.

---

# AI Usage

## Ai has helped me in making the Ui as close as possible to the real spotify and also made the code for the API calls for apple itunes.

---

## Credits

Music data and previews: Apple iTunes Search API and Apple's public chart feed.
Look and feel inspired by Spotify's web player. Not affiliated with either.
