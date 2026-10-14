# Spotify Clone (Deezer Edition)

A music player website that runs on your own computer. It is one Python file (`spotify.py`) with nothing to install. It opens a local site at `http://spotify.local`, styled like a modern dark music app, and plays music from the free Deezer API.

This is a learning project. It is not affiliated with any music service.

## What you need

- Python 3 (a recent version)
- An internet connection (the songs come from Deezer)
- A web browser (Chrome, Edge, Firefox or Safari)

No account, no API key and no `pip install` is needed.

## How to run it

**Windows**

1. Press the Start button, type `cmd`, right-click Command Prompt and choose **Run as administrator**.
2. Go to the folder that holds the file, for example: `cd Downloads`
3. Run: `python spotify.py`

**Mac or Linux**

1. Open a terminal and go to the folder that holds the file.
2. Run: `sudo python3 spotify.py`

Your browser opens by itself. If it does not, type the address shown in the window.

To stop the program, click the window and press **Ctrl + C**.

## Why does it ask for Administrator / sudo?

To make the name `spotify.local` work, the program adds two lines to your computer's `hosts` file. Only an administrator can change that file.

If you run it without admin rights, everything still works, but the address is `http://localhost:8080` instead.

## What you can do

- **Home:** quick picks, trending songs, popular albums and artists, featured playlists and new releases
- **Search:** search songs, artists, albums and playlists, or browse by genre
- **Album, artist and playlist pages:** play everything, shuffle, and see the full song list
- **Liked Songs:** tap the heart on any song to save it
- **Your own playlists:** create, rename and delete playlists, and add songs from the `...` menu
- **Follow artists:** followed artists show up in your library
- **Player bar:** play and pause, next and previous, shuffle, repeat, seek, volume and a queue panel
- **Recently played:** the last songs you listened to appear on the home page

## Controls

| Action | How |
| --- | --- |
| Play or pause | Space |
| Next / previous song | Shift + Right / Shift + Left |
| Volume up / down | Shift + Up / Shift + Down |
| Mute | M |
| Go to search | / |
| Close a pop-up | Esc |
| Play a song in a list | Double-click it, or click its number |
| Song options menu | Right-click a song, or click the `...` button |

## Good to know

- **Songs are 30 second previews.** That is what Deezer's free API provides. Full songs are not available.
- **Your data stays in your browser.** Liked songs, playlists, followed artists and recently played songs are saved in the browser you use. Clearing your browser data removes them.
- **The server only runs on your computer.** It listens on your own machine and is not reachable from other devices.

## How it works

`spotify.py` has two parts.

1. **The Python server (top of the file).** It edits the hosts file, starts a small web server, and passes music requests on to Deezer. The browser cannot call Deezer directly, so the server does it and keeps answers for five minutes to stay fast.
2. **The website (bottom of the file).** The page, the style and the code are stored inside the Python file as text, and the server hands them to your browser.

You can change a few things at the top of the file:

| Setting | What it does |
| --- | --- |
| `SITE_NAME` | The web address (default `spotify.local`) |
| `FIRST_PORT` | The port tried first (default 80) |
| `BACKUP_PORT` | Used if the first port is busy (default 8080) |
| `CACHE_SECONDS` | How long answers from Deezer are remembered |

## Troubleshooting

**The page says it could not reach Deezer.**
Check your internet connection and press Try again.

**`spotify.local` does not open.**
Run the program again as Administrator (or with `sudo`). If you cannot, use `http://localhost:8080`.

**The address needs `:8080` at the end.**
Port 80 was busy or not allowed, so the backup port was used. Open the address the program prints.

**Both ports are busy.**
Close other programs that run a local server, then start it again.

**A song will not play.**
A few songs have no preview. Those rows look faded. Try another song.

**There is no sound.**
Check the volume slider in the player bar and your computer volume.

## Removing it

1. Delete `spotify.py`.
2. Optional: open your `hosts` file as administrator and delete the lines that contain `spotify.local`.
   - Windows: `C:\Windows\System32\drivers\etc\hosts`
   - Mac / Linux: `/etc/hosts`
