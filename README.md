# Spotify Clone (free, no API key)
![Uploading image.png…]()

A Spotify-style music web player in **one Python file**. It uses Apple's free
**iTunes Search API**, so there is no account, no API key and no sign-up.

> This is a learning project. It is not affiliated with Spotify, Apple or any
> music service. Songs play as **free 30-second previews**.

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

### Command line options

| Option | What it does |
| --- | --- |
| `--port 9000` | Use a specific port instead of trying 80, then 8080 |
| `--no-hosts` | Do not edit your hosts file; use `http://localhost:PORT` |
| `--no-browser` | Do not open the browser automatically |
| `--verbose` | Print every request the server receives (useful for debugging) |

Example: `python spotify_clone.py --no-hosts --port 8080`

---

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

### Keyboard shortcuts

Press `?` in the app to see them all.

| Key | Action |
| --- | --- |
| `Space` | Play / pause |
| `Shift` + `Right` / `Left` | Next / previous song |
| `Right` / `Left` | Skip 5 seconds |
| `Shift` + `Up` / `Down` | Volume |
| `M` | Mute |
| `S` / `R` | Shuffle / repeat |
| `L` | Like the current song |
| `Q` | Open or close the queue |
| `/` | Search |

---

## How it works

```
 Your browser  <-->  spotify_clone.py (tiny local server)  <-->  Apple iTunes API
                     |  serves the page (HTML, CSS, JS)           Apple chart feed
                     |  forwards music requests + caches them     Apple preview audio
```

- The Python file contains the **whole website** as text (`PAGE_HTML`,
  `PAGE_CSS`, `PAGE_JS`) and serves it on `127.0.0.1` only (your own computer).
- When the page needs data, it asks the local server, which asks Apple and
  keeps the answer for 5 minutes. This avoids browser security (CORS) problems
  and keeps you under Apple's rate limit.
- Song audio is streamed straight from Apple's servers.
- Everything you save (likes, playlists, follows, history, settings) is stored
  in your **browser's local storage**, not on a server. Using a different
  browser or clearing site data starts you fresh, so use Export if you want a backup.

### Files

Only one file is needed: `spotify_clone.py`. The sections inside it are:

| Section | What it is |
| --- | --- |
| Top of file | Settings, caching, the local web server, command line options |
| `PAGE_CSS` | All the styling |
| `PAGE_HTML` | The page skeleton |
| `PAGE_JS` | The whole app: data, pages, player, library, settings |

---

## What changed from the original (Deezer) version

It is **not** just a swap of one API name. Deezer and iTunes return different
data, so the app was reworked around iTunes:

| Area | Original (Deezer) | Now (iTunes) |
| --- | --- | --- |
| Data source | Deezer API | Apple iTunes Search API + Apple chart feed |
| Needs a key? | Public API (blocked on some networks) | No key at all |
| Song audio | 30 s Deezer previews, iTunes as backup | 30 s Apple previews (every song) |
| Home charts | Deezer charts | Apple "most played" charts |
| Genres | Deezer genre list | A built-in list of 20 genres turned into searches |
| Artist photos | Deezer artist pictures | Not available, so an album cover is used |
| Public playlists | Deezer editorial playlists | Not available (your own playlists still work) |
| "Fans also like" / fan counts | Yes | Not available in this API |

New features added: settings, store country picker, sleep timer, stats page,
library page, search history, "made for you" shelves, import/export,
song info, playlist re-ordering, extra keyboard shortcuts, hide explicit songs,
command line options, and restoring your last song.

---

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

## Limits

- Previews are 30 seconds. Apple does not give free full-length tracks, and
  there is no legal free source for full mainstream songs.
- The app needs an internet connection.
- It is built for one person on one computer. It is not meant to be put on the internet.

---

## Credits

Music data and previews: Apple iTunes Search API and Apple's public chart feed.
Look and feel inspired by Spotify's web player. Not affiliated with either.
