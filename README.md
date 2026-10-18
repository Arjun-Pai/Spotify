# Spotify Clone

<img width="1200" height="604" alt="screenshot" src="https://github.com/user-attachments/assets/f6e0bec6-7aff-4191-b658-06608be93bb3" />

A Spotify-style music player that runs from a single Python file. It pulls songs from Apple's iTunes Search API, which is free and needs no key, so you can just run it.

Live demo: https://spotify.paio.hackclub.app

## Running it

You need Python 3.7+ and nothing else (no pip installs).

```bash
python spotify_clone.py
```

On Mac/Linux it might be `python3`. Your browser should open on its own. If it doesn't, use the address the terminal prints (`http://spotify.local` or `http://localhost:8080`). Ctrl+C stops it.

On startup it checks the connection to Apple and prints `Apple iTunes: connected, N songs` if it works.

## What it does

- Home page with trending songs and a few shelves (albums, Bollywood, hip-hop)
- Search for songs, albums and artists, with filters
- Genre tiles (Pop, Punjabi, Tamil, Telugu, K-Pop and more), plus album and artist pages
- Normal player stuff: play/pause, next/previous, seek, volume, shuffle, repeat, queue
- Sleep timer and media key support
- Liked songs, playlists you can reorder, and following artists, all saved in your browser
- Stats page, and export/import of your library as JSON
- Settings (top right profile icon): store country, hide explicit songs, clear data

## When something breaks

**Terminal says `Apple iTunes: PROBLEM`**: your network is probably blocking Apple. Try turning off your VPN or using a hotspot. The actual error is printed above it.

**Home says "Could not load music from Apple"**: same thing. Run with `--verbose` to see more.

**Charts are empty but search works**: Apple's chart feed is separate from search. It falls back to searching "top hits". Changing the store country in Settings can help.

**"Could not edit the hosts file"**: this only affects the `spotify.local` name. It will use `localhost:PORT` instead. Use `--no-hosts` to skip it, or run with admin/sudo if you want `spotify.local`.

**"Ports 80 and 8080 are both busy"**: close whatever is using them or pass `--port 9000`.

**"No preview available"**: Apple doesn't give a preview for every track. Skip it.

**Results suddenly stop**: Apple limits searches to roughly 20 a minute. Wait a bit. Results are cached for 5 minutes.

**Nothing plays**: browsers block autoplay, so click a play button once. Also check the tab isn't muted.

## AI usage

I used AI to help get the UI close to the real Spotify and to write the iTunes API calls. 

## Credits

Music data and previews come from Apple's iTunes Search API and public chart feed. The design is inspired by Spotify's web player. I'm not affiliated with either.
