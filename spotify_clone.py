"""
SPOTIFY CLONE  (free music from Apple's iTunes Search API - no key, no account)

Run:   python spotify_clone.py
Open:  the address it prints (it opens your browser automatically)

Every song plays a free 30 second preview straight from Apple.
Liked songs, playlists and followed artists are saved in your browser.
"""

import sys
import time
import argparse
import json
import threading
import webbrowser
import ssl
import urllib.request
import urllib.parse
import urllib.error
from http.server import BaseHTTPRequestHandler
try:
    from http.server import ThreadingHTTPServer
except ImportError:  # very old Python
    from http.server import HTTPServer
    from socketserver import ThreadingMixIn

    class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
        daemon_threads = True


SITE_NAME = "spotify.local"
FIRST_PORT = 80
BACKUP_PORT = 8080
ITUNES_URL = "https://itunes.apple.com"
RSS_URL = "https://rss.applemarketingtools.com"
CACHE_SECONDS = 300

api_cache = {}
image_cache = {}
VERBOSE = False


# ----------------------------------------------------------------------
#  hosts file (so you can open http://spotify.local) - optional
# ----------------------------------------------------------------------

def get_hosts_file_path():
    if sys.platform.startswith("win"):
        return r"C:\Windows\System32\drivers\etc\hosts"
    return "/etc/hosts"


def setup_hosts_file():
    path = get_hosts_file_path()
    try:
        with open(path, "r") as f:
            text = f.read()
    except Exception:
        return False

    for line in text.split("\n"):
        line = line.strip()
        if not line.startswith("#") and SITE_NAME in line:
            return True

    try:
        with open(path, "a") as f:
            f.write("\n127.0.0.1 " + SITE_NAME + "\n")
            f.write("::1 " + SITE_NAME + "\n")
        print("  Added " + SITE_NAME + " to your hosts file.")
        return True
    except Exception:
        return False


# ----------------------------------------------------------------------
#  downloading + caching
# ----------------------------------------------------------------------

def download(url):
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "*/*"}
    request = urllib.request.Request(url, headers=headers)
    last_error = None
    for attempt in range(2):
        try:
            try:
                return urllib.request.urlopen(request, timeout=15)
            except urllib.error.URLError as error:
                if "CERTIFICATE" in str(error).upper():
                    context = ssl._create_unverified_context()
                    return urllib.request.urlopen(request, timeout=15, context=context)
                raise
        except urllib.error.HTTPError as error:
            last_error = error
            if error.code in (403, 429, 503):
                time.sleep(1.2)
            else:
                break
        except Exception as error:
            last_error = error
            time.sleep(0.5)
    raise last_error


def get_cached(url):
    now = time.time()
    saved = api_cache.get(url)
    if saved and now - saved["time"] < CACHE_SECONDS:
        return saved["data"]

    if len(api_cache) > 600:
        api_cache.clear()

    data = download(url).read()
    api_cache[url] = {"time": now, "data": data}
    return data


def get_picture(url):
    host = urllib.parse.urlparse(url).hostname
    if host is None:
        return None
    if not (host.endswith("mzstatic.com") or host.endswith("apple.com")):
        return None

    if url in image_cache:
        return image_cache[url]
    if len(image_cache) > 300:
        image_cache.clear()

    answer = download(url)
    data = answer.read()
    kind = answer.headers.get("Content-Type", "image/jpeg")
    result = {"data": data, "kind": kind}
    image_cache[url] = result
    return result


# ----------------------------------------------------------------------
#  the web server
# ----------------------------------------------------------------------

class MyHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        if VERBOSE:
            print("  " + (format % args))

    def send_answer(self, code, kind, body, cache="no-store"):
        try:
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", cache)
            self.end_headers()
            self.wfile.write(body)
        except Exception:
            pass

    def proxy_json(self, base, rest, label):
        try:
            data = get_cached(base + rest)
            self.send_answer(200, "application/json; charset=utf-8", data)
        except Exception as error:
            print("  " + label + " problem: " + str(error))
            message = json.dumps({"error": "Could not reach " + label + ": " + str(error)})
            self.send_answer(502, "application/json", message.encode("utf-8"))

    def do_GET(self):
        path = self.path

        if path == "/" or path.startswith("/?"):
            self.send_answer(200, "text/html; charset=utf-8", PAGE_HTML.encode("utf-8"))
        elif path == "/style.css":
            self.send_answer(200, "text/css; charset=utf-8", PAGE_CSS.encode("utf-8"))
        elif path == "/app.js":
            self.send_answer(200, "application/javascript; charset=utf-8", PAGE_JS.encode("utf-8"))
        elif path == "/favicon.svg" or path == "/favicon.ico":
            self.send_answer(200, "image/svg+xml", FAVICON.encode("utf-8"))
        elif path.startswith("/itunes/"):
            self.proxy_json(ITUNES_URL, path[len("/itunes"):], "Apple iTunes")
        elif path.startswith("/rss/"):
            self.proxy_json(RSS_URL, path[len("/rss"):], "Apple charts")
        elif path.startswith("/img?"):
            options = urllib.parse.parse_qs(urllib.parse.urlparse(path).query)
            if "u" not in options:
                self.send_answer(400, "text/plain", b"missing picture address")
                return
            try:
                picture = get_picture(options["u"][0])
                if picture is None:
                    self.send_answer(403, "text/plain", b"not allowed")
                else:
                    self.send_answer(200, picture["kind"], picture["data"], "max-age=86400")
            except Exception as error:
                print("  Picture problem: " + str(error))
                self.send_answer(502, "text/plain", b"picture failed")
        else:
            self.send_answer(404, "text/plain", b"Not found")


def make_server(ports=None):
    for port in (ports or (FIRST_PORT, BACKUP_PORT)):
        try:
            server = ThreadingHTTPServer(("127.0.0.1", port), MyHandler)
            server.daemon_threads = True
            return server, port
        except Exception:
            continue
    return None, 0


def check_connection():
    print("  Checking the music service...")
    try:
        text = get_cached(ITUNES_URL + "/search?term=daft%20punk&media=music&entity=song&limit=5")
        results = json.loads(text).get("results", [])
        with_preview = sum(1 for r in results if r.get("previewUrl"))
        print("    Apple iTunes: connected, " + str(len(results)) + " songs, " + str(with_preview) + " with previews")
    except Exception as error:
        print("    Apple iTunes: PROBLEM - " + str(error))
        print("    Check your internet connection, firewall, or VPN.")
    try:
        text = get_cached(RSS_URL + "/api/v2/us/music/most-played/5/songs.json")
        n = len(json.loads(text).get("feed", {}).get("results", []))
        print("    Apple charts: connected, " + str(n) + " chart songs")
    except Exception as error:
        print("    Apple charts: PROBLEM - " + str(error))
        print("    (The home page will fall back to search results.)")
    print("")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Spotify clone powered by the free Apple iTunes Search API."
    )
    parser.add_argument(
        "--port", type=int, default=0,
        help="use this port instead of trying 80 and then 8080",
    )
    parser.add_argument(
        "--no-hosts", action="store_true",
        help="do not edit the hosts file (use http://localhost instead of spotify.local)",
    )
    parser.add_argument(
        "--no-browser", action="store_true",
        help="do not open the browser automatically",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="print every request the server receives",
    )
    args = parser.parse_args()
    args.ports = (args.port,) if args.port else None
    return args


def main():
    global VERBOSE
    args = parse_args()
    VERBOSE = args.verbose

    print("")
    print("  ==============================")
    print("    SPOTIFY CLONE  (iTunes)")
    print("  ==============================")
    print("")

    name_works = False if args.no_hosts else setup_hosts_file()

    server, port = make_server(args.ports)
    if server is None:
        print("  Could not start. Ports 80 and 8080 are both busy.")
        print("  Close other programs and try again.")
        return

    if name_works:
        address = "http://" + SITE_NAME + ("" if port == 80 else ":" + str(port))
    else:
        address = "http://localhost:" + str(port)
        if not args.no_hosts:
            print("  Note: could not edit the hosts file, so " + SITE_NAME)
            print("  will not work. Run again as Administrator / with sudo")
            print("  to get the nice name. Using localhost for now.")
            print("")

    print("  Open this in your browser:")
    print("")
    print("      " + address)
    print("")
    print("  Press Ctrl + C to stop.")
    print("")

    if not args.no_browser:
        threading.Timer(0.5, webbrowser.open, [address]).start()

    checker = threading.Thread(target=check_connection)
    checker.daemon = True
    checker.start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("")
        print("  Goodbye!")
        server.server_close()


FAVICON = r"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><circle cx="16" cy="16" r="16" fill="#1ed760"/><path d="M18 7v11.2a3.6 3.6 0 1 0 2 3.2V11h4V7z" fill="#000"/></svg>"""


# ----------------------------------------------------------------------
#  PAGE: CSS
# ----------------------------------------------------------------------

PAGE_CSS = r"""
:root {
  --bg: #000;
  --panel: #121212;
  --card: #181818;
  --card-hover: #282828;
  --text: #fff;
  --muted: #b3b3b3;
  --green: #1ed760;
  --green-hover: #3be477;
  --line: rgba(255, 255, 255, 0.1);
  --hue: #2a3b55;
  --a: 0;
  --topbar-h: 64px;
  --side-w: 300px;
}

* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

html,
body {
  height: 100%;
}

body {
  background: var(--bg);
  color: var(--text);
  overflow: hidden;
  font: 14px "Circular Std", "Inter", "Segoe UI", "Helvetica Neue", Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
}

button {
  font-family: inherit;
  color: inherit;
  background: none;
  border: none;
  cursor: pointer;
}

a {
  color: inherit;
  text-decoration: none;
}

input {
  font-family: inherit;
}

img {
  display: block;
}

svg {
  display: block;
}

.hidden {
  display: none !important;
}

button:focus-visible,
a:focus-visible,
input:focus-visible {
  outline: 2px solid #fff;
  outline-offset: 2px;
}

#main::-webkit-scrollbar,
.lib-list::-webkit-scrollbar,
#queue::-webkit-scrollbar {
  width: 12px;
}

#main::-webkit-scrollbar-thumb,
.lib-list::-webkit-scrollbar-thumb,
#queue::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.28);
  border: 3px solid transparent;
  background-clip: padding-box;
  border-radius: 6px;
}

#app {
  display: grid;
  height: 100vh;
  padding: 8px;
  gap: 8px;
  grid-template-columns: var(--side-w) 1fr;
  grid-template-rows: minmax(0, 1fr) auto;
  grid-template-areas: "side main" "player player";
}

#app.queue-open {
  grid-template-columns: var(--side-w) 1fr 330px;
  grid-template-areas: "side main queue" "player player player";
}

.panel {
  background: var(--panel);
  border-radius: 8px;
}

#sidebar {
  grid-area: side;
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 0;
}

.nav-panel {
  padding: 8px 12px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 20px;
  height: 40px;
  padding: 0 12px;
  font-size: 16px;
  font-weight: 700;
  color: var(--muted);
  transition: color 0.2s;
}

.nav-item:hover,
.nav-item.active {
  color: #fff;
}

.nav-item svg {
  width: 24px;
  height: 24px;
  fill: currentColor;
}

.lib-panel {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.lib-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 56px;
  padding: 0 8px 0 20px;
  flex-shrink: 0;
}

.lib-title {
  display: flex;
  align-items: center;
  gap: 12px;
  color: var(--muted);
  font-weight: 700;
  font-size: 16px;
}

.lib-title svg {
  width: 24px;
  height: 24px;
  fill: currentColor;
}

.icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  color: var(--muted);
}

.icon-btn:hover {
  color: #fff;
  background: #1f1f1f;
}

.icon-btn svg {
  width: 20px;
  height: 20px;
  fill: currentColor;
}

.lib-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 8px 8px;
}

.lib-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px;
  border-radius: 6px;
  cursor: pointer;
}

.lib-item:hover {
  background: #1a1a1a;
}

.lib-item.active {
  background: #232323;
}

.lib-img {
  width: 48px;
  height: 48px;
  flex-shrink: 0;
  border-radius: 4px;
  background: #282828;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  color: var(--muted);
}

.lib-img svg {
  width: 22px;
  height: 22px;
  fill: currentColor;
}

.lib-img img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.lib-img.liked {
  background: linear-gradient(135deg, #450af5, #8e8ee5);
  color: #fff;
}

.lib-img.round {
  border-radius: 50%;
}

.lib-img.grid4 {
  display: grid;
  grid-template-columns: 1fr 1fr;
}

.lib-text {
  min-width: 0;
}

.lib-name {
  font-size: 16px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.lib-sub {
  margin-top: 2px;
  color: var(--muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.lib-promo {
  background: #242424;
  border-radius: 8px;
  padding: 16px 20px 20px;
  margin: 8px 8px 0;
}

.lib-promo b {
  display: block;
  font-size: 16px;
  margin-bottom: 8px;
}

.lib-promo p {
  margin-bottom: 20px;
}

.pill {
  display: inline-block;
  padding: 8px 32px;
  border-radius: 500px;
  background: #fff;
  color: #000;
  font-weight: 700;
  transition: transform 0.1s;
}

.pill:hover {
  transform: scale(1.04);
}

.pill.small {
  padding: 6px 16px;
}

.pill.ghost {
  background: transparent;
  color: #fff;
}

.pill.outline {
  background: transparent;
  color: #fff;
  border: 1px solid #7c7c7c;
  padding: 7px 16px;
}

.pill.outline:hover {
  border-color: #fff;
}

.pill.green {
  background: var(--green);
}

#main {
  grid-area: main;
  position: relative;
  background: var(--panel);
  border-radius: 8px;
  overflow-y: auto;
  overflow-x: hidden;
  min-width: 0;
}

#bg {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 360px;
  background: linear-gradient(180deg, var(--hue) 0%, var(--panel) 100%);
  opacity: 0.6;
  pointer-events: none;
  transition: background 0.4s;
}

#topbar {
  position: sticky;
  top: 0;
  z-index: 20;
  height: var(--topbar-h);
  margin-bottom: calc(var(--topbar-h) * -1);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  background: rgba(18, 18, 18, var(--a));
}

.top-left,
.top-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.circle-btn {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
}

.circle-btn svg {
  width: 22px;
  height: 22px;
  fill: currentColor;
}

.search-box {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: 8px;
  width: min(364px, 40vw);
  height: 48px;
  padding: 0 12px;
  background: #242424;
  border-radius: 500px;
  border: 2px solid transparent;
  color: var(--muted);
}

.search-box:hover {
  background: #2a2a2a;
  color: #fff;
}

.search-box:focus-within {
  border-color: #fff;
  color: #fff;
}

.search-box svg {
  width: 24px;
  height: 24px;
  fill: currentColor;
  flex-shrink: 0;
}

.search-box input {
  flex: 1;
  min-width: 0;
  background: none;
  border: none;
  outline: none;
  color: #fff;
  font-size: 16px;
}

.search-box input::placeholder {
  color: #8a8a8a;
}

.search-box button {
  display: flex;
  color: var(--muted);
}

.avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: #1f1f1f;
  display: flex;
  align-items: center;
  justify-content: center;
}

.avatar span {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #535353;
  display: flex;
  align-items: center;
  justify-content: center;
}

.avatar svg {
  width: 20px;
  height: 20px;
  fill: #fff;
}

#view {
  position: relative;
  z-index: 1;
  padding: var(--topbar-h) 24px 32px;
  min-height: 100%;
}

.spinner {
  width: 40px;
  height: 40px;
  margin: 140px auto;
  border: 4px solid #333;
  border-top-color: var(--green);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.empty {
  text-align: center;
  padding: 80px 20px;
}

.empty h2 {
  font-size: 24px;
  margin-bottom: 8px;
}

.empty p {
  color: var(--muted);
  margin-bottom: 24px;
}

.footer-note {
  margin-top: 64px;
  padding-top: 24px;
  border-top: 1px solid var(--line);
  color: var(--muted);
  font-size: 12px;
  line-height: 1.6;
}

.greeting {
  font-size: 32px;
  font-weight: 800;
  letter-spacing: -0.5px;
  padding-top: 8px;
}

.quick-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
  margin-top: 20px;
}

.quick {
  position: relative;
  display: flex;
  align-items: center;
  height: 64px;
  border-radius: 4px;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.1);
  cursor: pointer;
}

.quick:hover {
  background: rgba(255, 255, 255, 0.2);
}

.quick img,
.quick .quick-ph {
  width: 64px;
  height: 64px;
  flex-shrink: 0;
  object-fit: cover;
  background: #333;
  box-shadow: 0 0 12px rgba(0, 0, 0, 0.4);
}

.quick .quick-ph {
  display: flex;
  align-items: center;
  justify-content: center;
}

.quick .quick-ph.liked {
  background: linear-gradient(135deg, #450af5, #8e8ee5);
}

.quick .quick-ph svg {
  width: 26px;
  height: 26px;
  fill: #fff;
}

.quick .q-name {
  flex: 1;
  min-width: 0;
  padding: 0 16px;
  font-weight: 700;
  font-size: 16px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.quick .card-play {
  right: 16px;
  bottom: auto;
  top: 8px;
}

.shelf {
  margin-top: 32px;
}

.shelf-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  margin-bottom: 4px;
}

.shelf-title {
  font-size: 24px;
  font-weight: 700;
  letter-spacing: -0.5px;
}

.shelf-more {
  color: var(--muted);
  font-weight: 700;
  padding-bottom: 2px;
}

.shelf-more:hover {
  text-decoration: underline;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(176px, 1fr));
  grid-auto-rows: 0;
  overflow: hidden;
  margin: 0 -6px;
}

.grid.wrap {
  grid-auto-rows: auto;
}

.grid > .card {
  margin: 6px;
}

.card {
  position: relative;
  min-width: 0;
  padding: 16px;
  background: var(--card);
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.3s;
}

.card:hover {
  background: var(--card-hover);
}

.card-img-wrap {
  position: relative;
  margin-bottom: 16px;
}

.card-img {
  width: 100%;
  aspect-ratio: 1/1;
  border-radius: 6px;
  overflow: hidden;
  background: #333;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
}

.card-img img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.card-img svg {
  width: 40%;
  fill: #777;
}

.card.round .card-img {
  border-radius: 50%;
}

.card-title {
  font-size: 16px;
  font-weight: 700;
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-sub {
  line-height: 20px;
  color: var(--muted);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-play {
  position: absolute;
  right: 8px;
  bottom: 8px;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: var(--green);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8px 8px rgba(0, 0, 0, 0.3);
  opacity: 0;
  transform: translateY(8px);
  transition: opacity 0.3s, transform 0.3s;
}

.card:hover .card-play,
.quick:hover .card-play,
.top-card:hover .card-play,
.card-play:focus-visible {
  opacity: 1;
  transform: none;
}

.card-play:hover {
  background: var(--green-hover);
  transform: scale(1.06) !important;
}

.card-play svg {
  width: 24px;
  height: 24px;
  fill: #000;
}

.entity-head {
  display: flex;
  align-items: flex-end;
  gap: 24px;
  min-height: 300px;
  padding: 24px 0;
}

.entity-cover {
  width: 232px;
  height: 232px;
  flex-shrink: 0;
  border-radius: 4px;
  overflow: hidden;
  background: #282828;
  box-shadow: 0 4px 60px rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #7f7f7f;
}

.entity-cover.round {
  border-radius: 50%;
}

.entity-cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.entity-cover svg {
  width: 64px;
  height: 64px;
  fill: currentColor;
}

.entity-cover.liked {
  background: linear-gradient(135deg, #450af5, #8e8ee5);
  color: #fff;
}

.entity-cover.grid4 {
  display: grid;
  grid-template-columns: 1fr 1fr;
}

.entity-info {
  min-width: 0;
}

.entity-type {
  font-weight: 700;
}

.entity-title {
  margin: 8px 0 12px;
  font-size: 96px;
  font-weight: 900;
  letter-spacing: -0.04em;
  line-height: 1.05;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.entity-title.mid {
  font-size: 64px;
}

.entity-title.small {
  font-size: 40px;
}

.entity-meta {
  color: #e6e6e6;
  line-height: 1.5;
}

.entity-meta .bold {
  font-weight: 700;
  color: #fff;
}

.entity-meta a:hover {
  text-decoration: underline;
}

.entity-meta .dim {
  color: #cfcfcf;
}

.actions {
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 24px 0;
}

.big-play {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: var(--green);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform 0.1s;
}

.big-play:hover {
  transform: scale(1.06);
  background: var(--green-hover);
}

.big-play svg {
  width: 28px;
  height: 28px;
  fill: #000;
}

.act-btn {
  color: var(--muted);
  display: flex;
  align-items: center;
  font-weight: 700;
}

.act-btn:hover {
  color: #fff;
}

.act-btn svg {
  width: 32px;
  height: 32px;
  fill: currentColor;
}

.t-head,
.t-row {
  display: grid;
  grid-template-columns: 24px minmax(120px, 6fr) 32px 56px 32px;
  gap: 16px;
  align-items: center;
  padding: 0 16px;
}

.tracks.album-col .t-head,
.tracks.album-col .t-row {
  grid-template-columns: 24px minmax(120px, 6fr) minmax(100px, 4fr) 32px 56px 32px;
}

.t-head {
  height: 36px;
  margin-bottom: 8px;
  color: var(--muted);
  border-bottom: 1px solid var(--line);
}

.t-head .t-time-h {
  display: flex;
  justify-content: flex-end;
}

.t-head svg {
  width: 16px;
  height: 16px;
  fill: currentColor;
}

.t-num-h {
  text-align: center;
  font-size: 16px;
}

.t-row {
  height: 56px;
  border-radius: 4px;
  color: var(--muted);
}

.t-row:hover {
  background: rgba(255, 255, 255, 0.1);
}

.t-row.selected {
  background: rgba(255, 255, 255, 0.2);
}

.t-row.unavailable {
  opacity: 0.4;
}

.t-num {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  cursor: pointer;
}

.t-num .num-play {
  display: none;
}

.t-num .num-play svg {
  width: 20px;
  height: 20px;
  fill: #fff;
}

.t-row:hover .t-num .num-text {
  display: none;
}

.t-row:hover .t-num .num-play {
  display: block;
}

.eq {
  display: none;
  width: 14px;
  height: 14px;
  align-items: flex-end;
  gap: 2px;
}

.eq i {
  flex: 1;
  background: var(--green);
  animation: eq 0.9s infinite ease-in-out;
}

.eq i:nth-child(1) {
  animation-delay: -0.5s;
}

.eq i:nth-child(2) {
  animation-delay: -0.25s;
}

@keyframes eq {
  0%,
  100% {
    height: 25%;
  }

  50% {
    height: 100%;
  }
}

body.paused .eq i {
  animation-play-state: paused;
}

.t-row.playing .eq {
  display: flex;
}

.t-row.playing .num-text {
  display: none;
}

.t-row.playing:hover .eq {
  display: none;
}

.t-row.playing .t-title {
  color: var(--green);
}

.t-main {
  display: flex;
  align-items: center;
  gap: 16px;
  min-width: 0;
}

.t-main img {
  width: 40px;
  height: 40px;
  border-radius: 4px;
  object-fit: cover;
  flex-shrink: 0;
  background: #333;
}

.t-text {
  min-width: 0;
}

.t-title {
  font-size: 16px;
  color: #fff;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.t-artist {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.t-row:hover .t-artist,
.t-row:hover .t-album {
  color: #fff;
}

.t-artist a:hover,
.t-album a:hover {
  text-decoration: underline;
}

.explicit {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border-radius: 2px;
  background: #b3b3b3;
  color: #000;
  font-size: 10px;
  font-weight: 700;
  flex-shrink: 0;
}

.t-album {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.t-heart,
.t-more {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--muted);
  opacity: 0;
}

.t-row:hover .t-heart,
.t-row:hover .t-more,
.t-heart.liked,
.t-heart:focus-visible,
.t-more:focus-visible {
  opacity: 1;
}

.t-heart:hover,
.t-more:hover {
  color: #fff;
}

.t-heart.liked {
  color: var(--green);
}

.t-heart svg,
.t-more svg {
  width: 20px;
  height: 20px;
  fill: currentColor;
}

.t-time {
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.tracks.collapsed .t-row:nth-child(n+6) {
  display: none;
}

.see-more {
  margin: 8px 0 0 16px;
  color: var(--muted);
  font-weight: 700;
}

.see-more:hover {
  color: #fff;
}

.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}

.chip {
  padding: 8px 14px;
  border-radius: 500px;
  background: rgba(255, 255, 255, 0.1);
}

.chip:hover {
  background: rgba(255, 255, 255, 0.2);
}

.chip.active {
  background: #fff;
  color: #000;
}

.genre-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
  gap: 24px;
  margin-top: 16px;
}

.genre-card {
  position: relative;
  aspect-ratio: 1/1;
  padding: 16px;
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  font-size: 24px;
  font-weight: 700;
  letter-spacing: -0.5px;
  transition: transform 0.15s;
}

.genre-card:hover {
  transform: scale(1.02);
}

.top-grid {
  display: grid;
  grid-template-columns: minmax(280px, 2fr) 5fr;
  gap: 24px;
  margin-top: 24px;
}

.top-card {
  position: relative;
  min-height: 240px;
  padding: 20px;
  background: var(--card);
  border-radius: 8px;
  cursor: pointer;
}

.top-card:hover {
  background: var(--card-hover);
}

.top-card img,
.top-card .ph {
  width: 100px;
  height: 100px;
  margin-bottom: 20px;
  border-radius: 4px;
  object-fit: cover;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
  background: #333;
}

.top-card .ph {
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
}

.top-card .ph svg {
  width: 44px;
  height: 44px;
  fill: #888;
}

.top-card .name {
  font-size: 32px;
  font-weight: 700;
  letter-spacing: -0.5px;
  margin-bottom: 8px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.top-card .tag {
  display: inline-block;
  padding: 4px 12px;
  border-radius: 500px;
  background: #121212;
  font-weight: 700;
}

.top-card .sub {
  color: var(--muted);
  margin-right: 8px;
}

.top-card .card-play {
  right: 20px;
  bottom: 20px;
}

.section-title {
  font-size: 24px;
  font-weight: 700;
  letter-spacing: -0.5px;
  margin-bottom: 8px;
}

#player {
  grid-area: player;
  display: grid;
  grid-template-columns: minmax(180px, 30%) minmax(280px, 40%) minmax(180px, 30%);
  align-items: center;
  justify-content: space-between;
  height: 72px;
  padding: 0 8px;
}

.np {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
}

.np-cover {
  width: 56px;
  height: 56px;
  flex-shrink: 0;
  border-radius: 4px;
  background: #282828;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6a6a6a;
}

.np-cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.np-cover svg {
  width: 24px;
  height: 24px;
  fill: currentColor;
}

.np-text {
  min-width: 0;
}

.np-title {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.np-title a:hover,
.np-artist a:hover {
  text-decoration: underline;
}

.np-artist {
  margin-top: 2px;
  font-size: 12px;
  color: var(--muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.np-artist a:hover {
  color: #fff;
}

.controls {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  max-width: 722px;
  width: 100%;
  margin: 0 auto;
}

.ctrl-row {
  display: flex;
  align-items: center;
  gap: 16px;
}

.ctrl {
  position: relative;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--muted);
}

.ctrl:hover {
  color: #fff;
}

.ctrl svg {
  width: 18px;
  height: 18px;
  fill: currentColor;
}

.ctrl.on {
  color: var(--green);
}

.ctrl.on::after {
  content: "";
  position: absolute;
  bottom: 1px;
  left: 50%;
  width: 4px;
  height: 4px;
  margin-left: -2px;
  border-radius: 50%;
  background: currentColor;
}

.ctrl.heart-ctrl.liked {
  color: var(--green);
}

.ctrl.heart-ctrl.liked::after {
  display: none;
}

.ctrl.play-main {
  border-radius: 50%;
  background: #fff;
  color: #000;
}

.ctrl.play-main:hover {
  transform: scale(1.06);
  color: #000;
}

.progress-row {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.time {
  min-width: 40px;
  font-size: 11px;
  color: var(--muted);
  text-align: center;
  font-variant-numeric: tabular-nums;
}

.right-ctrl {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 4px;
}

input[type="range"].bar {
  -webkit-appearance: none;
  appearance: none;
  width: 100%;
  height: 12px;
  background: transparent;
  cursor: pointer;
  outline: none;
  --c: #fff;
  --fill: 0%;
}

input[type="range"].bar:hover {
  --c: var(--green);
}

input[type="range"].bar::-webkit-slider-runnable-track {
  height: 4px;
  border-radius: 2px;
  background: linear-gradient(to right, var(--c) var(--fill), #4d4d4d var(--fill));
}

input[type="range"].bar::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 12px;
  height: 12px;
  margin-top: -4px;
  border-radius: 50%;
  background: #fff;
  opacity: 0;
}

input[type="range"].bar:hover::-webkit-slider-thumb {
  opacity: 1;
}

input[type="range"].bar::-moz-range-track {
  height: 4px;
  border-radius: 2px;
  background: #4d4d4d;
}

input[type="range"].bar::-moz-range-progress {
  height: 4px;
  border-radius: 2px;
  background: var(--c);
}

input[type="range"].bar::-moz-range-thumb {
  width: 12px;
  height: 12px;
  border: none;
  border-radius: 50%;
  background: #fff;
  opacity: 0;
}

input[type="range"].bar:hover::-moz-range-thumb {
  opacity: 1;
}

input[type="range"].vol {
  width: 100px;
}

#queue {
  grid-area: queue;
  display: none;
  background: var(--panel);
  border-radius: 8px;
  overflow-y: auto;
  padding: 16px 8px;
}

#app.queue-open #queue {
  display: block;
}

.q-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 8px 16px;
}

.q-head h2 {
  font-size: 16px;
}

.q-label {
  padding: 16px 8px 8px;
  font-size: 16px;
  font-weight: 700;
  color: var(--muted);
}

.q-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px;
  border-radius: 4px;
  cursor: pointer;
}

.q-item:hover {
  background: rgba(255, 255, 255, 0.1);
}

.q-item img {
  width: 40px;
  height: 40px;
  border-radius: 4px;
  object-fit: cover;
  background: #333;
}

.q-item .q-t {
  min-width: 0;
}

.q-item .q-title {
  font-size: 16px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.q-item.now .q-title {
  color: var(--green);
}

.q-item .q-artist {
  color: var(--muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.q-empty {
  padding: 24px 8px;
  color: var(--muted);
}

#menu {
  position: fixed;
  z-index: 200;
  display: none;
  min-width: 220px;
  padding: 4px;
  background: #282828;
  border-radius: 4px;
  box-shadow: 0 16px 24px rgba(0, 0, 0, 0.3);
}

.menu-item {
  display: block;
  width: 100%;
  padding: 12px;
  border-radius: 2px;
  text-align: left;
  color: #e8e8e8;
}

.menu-item:hover {
  background: rgba(255, 255, 255, 0.1);
}

.menu-sep {
  height: 1px;
  margin: 4px 0;
  background: rgba(255, 255, 255, 0.1);
}

#modal-back {
  position: fixed;
  inset: 0;
  z-index: 300;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.7);
}

.modal {
  width: min(480px, 92vw);
  max-height: 80vh;
  overflow-y: auto;
  padding: 24px;
  background: #282828;
  border-radius: 8px;
}

.modal h2 {
  font-size: 24px;
  margin-bottom: 20px;
}

.modal input.text {
  width: 100%;
  padding: 12px;
  border: none;
  border-radius: 4px;
  outline: none;
  background: #3e3e3e;
  color: #fff;
  font-size: 14px;
}

.modal input.text:focus {
  box-shadow: 0 0 0 2px #fff;
}

.modal-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 16px;
  margin-top: 24px;
}

.pick {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 8px;
  border-radius: 4px;
  text-align: left;
}

.pick:hover {
  background: rgba(255, 255, 255, 0.1);
}

.pick .lib-img {
  width: 40px;
  height: 40px;
}

#toast {
  position: fixed;
  left: 50%;
  bottom: 96px;
  z-index: 400;
  padding: 12px 24px;
  border-radius: 6px;
  background: #fff;
  color: #000;
  font-weight: 700;
  opacity: 0;
  transform: translate(-50%, 16px);
  pointer-events: none;
  transition: opacity 0.3s, transform 0.3s;
}

#toast.show {
  opacity: 1;
  transform: translate(-50%, 0);
}

@media (max-width: 1100px) {
  :root {
    --side-w: 72px;
  }

  .lbl,
  .lib-promo,
  .lib-title,
  .lib-text {
    display: none !important;
  }

  .nav-item {
    justify-content: center;
    padding: 0;
  }

  .lib-head {
    justify-content: center;
    padding: 0;
  }

  .lib-item {
    justify-content: center;
  }

  #app.queue-open {
    grid-template-columns: var(--side-w) 1fr 280px;
  }

  .entity-title {
    font-size: 64px;
  }

  .entity-title.mid {
    font-size: 48px;
  }
}

@media (max-width: 760px) {
  #app,
  #app.queue-open {
    grid-template-columns: 1fr;
    grid-template-areas: "main" "player";
  }

  #sidebar,
  #queue {
    display: none !important;
  }

  #player {
    grid-template-columns: 1fr auto;
    height: 64px;
  }

  .right-ctrl,
  .time,
  .progress-row {
    display: none;
  }

  .controls {
    width: auto;
  }

  .ctrl-row .ctrl:not(.play-main):not(.skip) {
    display: none;
  }

  .entity-head {
    flex-direction: column;
    align-items: flex-start;
    min-height: 0;
  }

  .entity-cover {
    width: 160px;
    height: 160px;
  }

  .entity-title {
    font-size: 40px;
  }

  .tracks.album-col .t-head,
  .tracks.album-col .t-row {
    grid-template-columns: 24px minmax(100px, 1fr) 32px 56px 32px;
  }

  .t-album,
  .t-head .album-h {
    display: none;
  }

  .top-grid {
    grid-template-columns: 1fr;
  }

  .search-box {
    width: 200px;
  }
}

.select {
  padding: 8px 10px;
  background: #3e3e3e;
  color: #fff;
  border: none;
  border-radius: 4px;
  font-size: 14px;
  max-width: 220px;
}

.set-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.set-row label {
  font-size: 16px;
}

.set-row input[type="checkbox"] {
  width: 20px;
  height: 20px;
  accent-color: #1ed760;
}

.set-help {
  color: #b3b3b3;
  font-size: 12px;
  margin: 6px 0 0;
}

.set-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 20px;
}

.kbd-table {
  width: 100%;
  border-collapse: collapse;
}

.kbd-table td {
  padding: 8px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.kbd-table td:first-child {
  width: 190px;
}

kbd {
  display: inline-block;
  min-width: 24px;
  padding: 2px 8px;
  border-radius: 4px;
  background: #3e3e3e;
  border-bottom: 2px solid #1a1a1a;
  font: 12px/1.6 monospace;
  text-align: center;
}

.sleep-list {
  display: grid;
  gap: 4px;
}

.sleep-list .pick {
  font-size: 16px;
  padding: 12px;
}

.info-table {
  width: 100%;
  border-collapse: collapse;
}

.info-table td {
  padding: 8px 0;
  vertical-align: top;
}

.info-table td:first-child {
  color: #b3b3b3;
  width: 110px;
}

.page-title {
  font-size: 32px;
  font-weight: 800;
  letter-spacing: -0.5px;
  padding-top: 8px;
}

.page-sub {
  color: var(--muted);
  margin-top: 4px;
}

.stat-tiles {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 16px;
  margin-top: 24px;
}

.stat-tile {
  padding: 20px;
  background: var(--card);
  border-radius: 8px;
}

.stat-tile b {
  display: block;
  font-size: 36px;
  letter-spacing: -1px;
  margin-bottom: 4px;
}

.stat-tile span {
  color: var(--muted);
}

.bar-row {
  display: grid;
  grid-template-columns: 180px 1fr 40px;
  gap: 12px;
  align-items: center;
  margin: 8px 0;
}

.bar-name {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.bar-track {
  height: 8px;
  background: #333;
  border-radius: 4px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  background: var(--green);
  border-radius: 4px;
}

.bar-n {
  text-align: right;
  color: var(--muted);
}

.recent-searches {
  margin: 8px 0 24px;
}

.recent-searches h3 {
  font-size: 16px;
  margin-bottom: 8px;
}

.chip.clear {
  background: transparent;
  border: 1px solid #7c7c7c;
}

@media (max-width: 760px) {
  .bar-row {
    grid-template-columns: 110px 1fr 32px;
  }

  .kbd-table td:first-child {
    width: 130px;
  }
}

@media (prefers-reduced-motion: reduce) {
  * {
    animation: none !important;
    transition: none !important;
  }
}
"""


# ----------------------------------------------------------------------
#  PAGE: HTML
# ----------------------------------------------------------------------

PAGE_HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Spotify Clone - Web Player</title>
  <link rel="icon" href="/favicon.svg" type="image/svg+xml">
  <link rel="stylesheet" href="/style.css">
</head>
<body class="paused">
  <div id="app">
    <aside id="sidebar">
      <nav class="panel nav-panel">
        <a class="nav-item" id="nav-home" href="#/home"><span data-icon="home"></span><span class="lbl">Home</span></a>
        <a class="nav-item" id="nav-search" href="#/search"><span data-icon="search"></span><span class="lbl">Search</span></a>
      </nav>
      <section class="panel lib-panel">
        <div class="lib-head">
          <div class="lib-title"><span data-icon="library"></span><span class="lbl">Your Library</span></div>
          <button class="icon-btn lbl" data-act="new-playlist" title="Create playlist" aria-label="Create playlist"><span data-icon="plus"></span></button>
        </div>
        <div class="lib-list" id="lib-list"></div>
      </section>
    </aside>

    <main id="main">
      <div id="bg"></div>
      <div id="topbar">
        <div class="top-left">
          <button class="circle-btn" data-act="nav-back" title="Go back" aria-label="Go back"><span data-icon="chevL"></span></button>
          <button class="circle-btn" data-act="nav-forward" title="Go forward" aria-label="Go forward"><span data-icon="chevR"></span></button>
          <div class="search-box hidden" id="search-box">
            <span data-icon="search"></span>
            <input id="search-input" type="text" placeholder="What do you want to play?" autocomplete="off" spellcheck="false">
            <button id="search-clear" class="hidden" data-act="clear-search" aria-label="Clear search"><span data-icon="close"></span></button>
          </div>
        </div>
        <div class="top-right">
          <button class="pill small" data-act="premium">Explore Premium</button>
          <button class="avatar" aria-label="Profile" data-act="profile"><span><span data-icon="person"></span></span></button>
        </div>
      </div>
      <div id="view"></div>
    </main>

    <aside id="queue"></aside>

    <footer id="player">
      <div class="np">
        <div class="np-cover" id="np-cover"><span data-icon="music"></span></div>
        <div class="np-text">
          <div class="np-title" id="np-title"></div>
          <div class="np-artist" id="np-artist"></div>
        </div>
        <button class="ctrl heart-ctrl hidden" id="np-heart" data-act="like-current" aria-label="Save to Liked Songs"></button>
      </div>
      <div class="controls">
        <div class="ctrl-row">
          <button class="ctrl" id="btn-shuffle" data-act="shuffle" title="Shuffle" aria-label="Shuffle"></button>
          <button class="ctrl skip" id="btn-prev" data-act="prev" title="Previous" aria-label="Previous"></button>
          <button class="ctrl play-main" id="btn-play" data-act="toggle-play" title="Play" aria-label="Play"></button>
          <button class="ctrl skip" id="btn-next" data-act="next" title="Next" aria-label="Next"></button>
          <button class="ctrl" id="btn-repeat" data-act="repeat" title="Repeat" aria-label="Repeat"></button>
        </div>
        <div class="progress-row">
          <span class="time" id="t-cur">0:00</span>
          <input type="range" class="bar" id="seek" min="0" max="1000" value="0" aria-label="Seek">
          <span class="time" id="t-dur">0:00</span>
        </div>
      </div>
      <div class="right-ctrl">
        <button class="ctrl" id="btn-sleep" data-act="sleep" title="Sleep timer" aria-label="Sleep timer"></button>
        <button class="ctrl" id="btn-queue" data-act="toggle-queue" title="Queue" aria-label="Queue"></button>
        <button class="ctrl" id="btn-mute" data-act="mute" title="Mute" aria-label="Mute"></button>
        <input type="range" class="bar vol" id="volume" min="0" max="100" value="70" aria-label="Volume">
      </div>
    </footer>
  </div>

  <div id="menu"></div>
  <div id="modal-back" class="hidden"><div class="modal" id="modal"></div></div>
  <div id="toast"></div>
  <audio id="audio" preload="auto"></audio>
  <script src="/app.js"></script>
</body>
</html>
"""


# ----------------------------------------------------------------------
#  PAGE: JAVASCRIPT (runs in your browser)
# ----------------------------------------------------------------------

PAGE_JS = r"""
"use strict";

const $ = (sel, parent) => (parent || document).querySelector(sel);
const $$ = (sel, parent) => Array.from((parent || document).querySelectorAll(sel));
// The store country is changeable in Settings, so these are "let" not "const".
let COUNTRY = (function () {
  try {
    const saved = localStorage.getItem("sp_country");
    if (saved) return JSON.parse(saved);
  } catch (e) {}
  return "us";
})();
let CC = "&country=" + COUNTRY;

function esc(text) {
  const map = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  return String(text == null ? "" : text).replace(/[&<>"']/g, c => map[c]);
}
function fmtTime(sec) {
  sec = Math.floor(sec || 0);
  const m = Math.floor(sec / 60), s = sec % 60;
  return m + ":" + (s < 10 ? "0" : "") + s;
}
function fmtLong(sec) {
  sec = sec || 0;
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60);
  return h > 0 ? h + " hr " + m + " min" : m + " min";
}
function art(url, size) {
  if (!url) return "";
  return url.replace(/\/\d+x\d+(bb)?\.(jpg|png|webp)$/i, "/" + size + "x" + size + "bb.jpg");
}
function q(text) { return encodeURIComponent(text); }

const PALETTE = ["#e8115b", "#8d67ab", "#1e3264", "#e13300", "#477d95", "#ba5d07", "#503750", "#dc148c",
  "#148a08", "#0d73ec", "#e91429", "#608108", "#7358ff", "#af2896", "#006450", "#8c1932"];

function hashNumber(text) {
  let h = 0;
  for (let i = 0; i < text.length; i++) h = (h * 31 + text.charCodeAt(i)) >>> 0;
  return h;
}
function hashColor(text) { return "hsl(" + (hashNumber(String(text)) % 360) + ",45%,32%)"; }

const colorCache = {};
function getImageColor(url) {
  if (!url) return Promise.resolve(null);
  if (colorCache[url]) return Promise.resolve(colorCache[url]);
  return new Promise(resolve => {
    const img = new Image();
    img.onload = () => {
      try {
        const size = 12, canvas = document.createElement("canvas");
        canvas.width = size; canvas.height = size;
        const ctx = canvas.getContext("2d");
        ctx.drawImage(img, 0, 0, size, size);
        const data = ctx.getImageData(0, 0, size, size).data;
        let r = 0, g = 0, b = 0, total = 0;
        for (let i = 0; i < data.length; i += 4) {
          const max = Math.max(data[i], data[i + 1], data[i + 2]);
          const min = Math.min(data[i], data[i + 1], data[i + 2]);
          const w = (max - min) + 20;
          r += data[i] * w; g += data[i + 1] * w; b += data[i + 2] * w; total += w;
        }
        r /= total; g /= total; b /= total;
        const light = r * 0.3 + g * 0.59 + b * 0.11;
        if (light > 105) { const f = 105 / light; r *= f; g *= f; b *= f; }
        const color = "rgb(" + Math.round(r) + "," + Math.round(g) + "," + Math.round(b) + ")";
        colorCache[url] = color;
        resolve(color);
      } catch (err) { resolve(null); }
    };
    img.onerror = () => resolve(null);
    img.src = "/img?u=" + encodeURIComponent(url);
  });
}

const ICONS = {
  play: "M8 5v14l11-7z",
  pause: "M6 19h4V5H6v14zm8-14v14h4V5h-4z",
  next: "M6 18l8.5-6L6 6v12zM16 6v12h2V6h-2z",
  prev: "M6 6h2v12H6zm3.5 6l8.5 6V6z",
  shuffle: "M10.59 9.17L5.41 4 4 5.41l5.17 5.17 1.42-1.41zM14.5 4l2.04 2.04L4 18.59 5.41 20 17.96 7.46 20 9.5V4h-5.5zm.33 9.41l-1.41 1.41 3.13 3.13L14.5 20H20v-5.5l-2.04 2.04-3.13-3.13z",
  repeat: "M7 7h10v3l4-4-4-4v3H5v6h2V7zm10 10H7v-3l-4 4 4 4v-3h12v-6h-2v4z",
  repeatOne: "M7 7h10v3l4-4-4-4v3H5v6h2V7zm10 10H7v-3l-4 4 4 4v-3h12v-6h-2v4zm-4-2V9h-1l-2 1v1h1.5v4H13z",
  heart: "M16.5 3c-1.74 0-3.41.81-4.5 2.09C10.91 3.81 9.24 3 7.5 3 4.42 3 2 5.42 2 8.5c0 3.78 3.4 6.86 8.55 11.54L12 21.35l1.45-1.32C18.6 15.36 22 12.28 22 8.5 22 5.42 19.58 3 16.5 3zm-4.4 15.55l-.1.1-.1-.1C7.14 14.24 4 11.39 4 8.5 4 6.5 5.5 5 7.5 5c1.54 0 3.04.99 3.57 2.36h1.87C13.46 5.99 14.96 5 16.5 5c2 0 3.5 1.5 3.5 3.5 0 2.89-3.14 5.74-7.9 10.05z",
  heartFill: "M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z",
  volHigh: "M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z",
  volLow: "M18.5 12c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM5 9v6h4l5 5V4L9 9H5z",
  volMute: "M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z",
  queue: "M15 6H3v2h12V6zm0 4H3v2h12v-2zM3 16h8v-2H3v2zM17 6v8.18c-.31-.11-.65-.18-1-.18-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3V8h3V6h-5z",
  home: "M12 3L2 12h3v8h5v-6h4v6h5v-8h3L12 3z",
  search: "M15.5 14h-.79l-.28-.27A6.471 6.471 0 0016 9.5 6.5 6.5 0 109.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z",
  library: "M4 4h2v16H4zm5 0h2v16H9zm4.2.6l1.9-.5 4.1 15.6-1.9.5z",
  plus: "M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z",
  chevL: "M15.41 7.41L14 6l-6 6 6 6 1.41-1.41L10.83 12z",
  chevR: "M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z",
  close: "M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z",
  music: "M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z",
  dots: "M6 10c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm12 0c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm-6 0c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2z",
  clock: "M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zM12 20c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67z",
  person: "M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"
};
function icon(name) {
  return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="' + ICONS[name] + '"/></svg>';
}

function loadData(key, fallback) {
  try { const t = localStorage.getItem("sp_" + key); if (t) return JSON.parse(t); } catch (e) {}
  return fallback;
}
function saveData(key, value) {
  try { localStorage.setItem("sp_" + key, JSON.stringify(value)); } catch (e) {}
}

const state = {
  queue: [], index: -1, past: [], shuffle: false, repeat: 0,
  volume: loadData("volume", 0.7), muted: false, failCount: 0,
  liked: loadData("liked", []), playlists: loadData("playlists", []),
  following: loadData("following", []), recent: loadData("recent", []),
  pageTracks: [], search: null, searchFilter: "all"
};
const lists = {};
const trackStore = {};
state.liked.forEach(t => { trackStore[t.id] = t; });
state.recent.forEach(t => { trackStore[t.id] = t; });
state.playlists.forEach(p => p.tracks.forEach(t => { trackStore[t.id] = t; }));

/* ---------------- talking to Apple (through our python server) ---------------- */

async function getJson(url) {
  const res = await fetch(url);
  let data = null;
  try { data = await res.json(); } catch (e) {}
  if (!res.ok) throw new Error((data && data.error) || "Request failed (" + res.status + ")");
  return data;
}
async function itunes(path) {
  const data = await getJson("/itunes" + path);
  return data.results || [];
}
async function safeItunes(path) {
  try { return await itunes(path); } catch (e) { return []; }
}
async function rss(path) {
  try {
    const data = await getJson("/rss" + path);
    return (data.feed && data.feed.results) || [];
  } catch (e) { return []; }
}

function mapTrack(r) {
  const t = {
    id: r.trackId,
    title: r.trackName || "Unknown",
    artist: r.artistName || "",
    artistId: r.artistId || 0,
    albumTitle: r.collectionName || "",
    albumId: r.collectionId || 0,
    cover: art(r.artworkUrl100, 300),
    coverSmall: art(r.artworkUrl100, 100),
    preview: r.previewUrl || "",
    duration: Math.round((r.trackTimeMillis || 0) / 1000),
    explicit: r.trackExplicitness === "explicit"
  };
  if (!t.preview) t.noPreview = true;
  trackStore[t.id] = t;
  return t;
}
function mapTracks(list) {
  return list
    .filter(r => r.wrapperType === "track" && r.kind === "song")
    .filter(r => !(settings.hideExplicit && r.trackExplicitness === "explicit"))
    .map(mapTrack);
}
function mapAlbum(r) {
  return {
    id: r.collectionId,
    title: r.collectionName,
    artist: r.artistName || "",
    artistId: r.artistId || 0,
    cover: art(r.artworkUrl100, 300),
    big: art(r.artworkUrl100, 600),
    year: r.releaseDate ? String(r.releaseDate).slice(0, 4) : "",
    count: r.trackCount || 0
  };
}
function mapAlbums(list) {
  return list.filter(r => r.collectionId && r.wrapperType === "collection").map(mapAlbum);
}
function mapRssAlbum(r) {
  return {
    id: r.id, title: r.name, artist: r.artistName || "", artistId: 0,
    cover: art(r.artworkUrl100, 300), big: art(r.artworkUrl100, 600),
    year: r.releaseDate ? String(r.releaseDate).slice(0, 4) : "", count: 0
  };
}
function mapArtist(r) {
  return { id: r.artistId, name: r.artistName, genre: r.primaryGenreName || "", cover: "" };
}

/* ---------------- toast, likes, playlists ---------------- */

let toastTimer = null;
function toast(message) {
  const el = $("#toast");
  el.textContent = message;
  el.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), 2400);
}

function isLiked(id) { return state.liked.some(t => t.id === id); }
function toggleLike(track) {
  if (!track) return;
  if (isLiked(track.id)) {
    state.liked = state.liked.filter(t => t.id !== track.id);
    toast("Removed from Liked Songs");
  } else {
    state.liked.unshift(track);
    toast("Added to Liked Songs");
  }
  saveData("liked", state.liked);
  refreshHearts();
  renderSidebar();
  if (location.hash === "#/liked") router(true);
}

function createPlaylist(name) {
  const clean = (name || "").trim();
  const playlist = { id: "p" + Date.now(), name: clean || "My playlist #" + (state.playlists.length + 1), tracks: [] };
  state.playlists.unshift(playlist);
  saveData("playlists", state.playlists);
  renderSidebar();
  return playlist;
}
function findPlaylist(id) { return state.playlists.find(p => p.id === id) || null; }
function addToPlaylist(playlistId, track) {
  const p = findPlaylist(playlistId);
  if (!p || !track) return;
  if (p.tracks.some(t => t.id === track.id)) { toast("Already in " + p.name); return; }
  p.tracks.push(track);
  saveData("playlists", state.playlists);
  renderSidebar();
  toast("Added to " + p.name);
}
function removeFromPlaylist(playlistId, trackId) {
  const p = findPlaylist(playlistId);
  if (!p) return;
  p.tracks = p.tracks.filter(t => t.id !== trackId);
  saveData("playlists", state.playlists);
  renderSidebar();
  toast("Removed from " + p.name);
  router(true);
}
function deletePlaylist(playlistId) {
  state.playlists = state.playlists.filter(p => p.id !== playlistId);
  saveData("playlists", state.playlists);
  renderSidebar();
  toast("Playlist deleted");
  location.hash = "#/home";
}
function isFollowing(id) { return state.following.some(a => a.id === id); }
function toggleFollow(artist) {
  if (isFollowing(artist.id)) state.following = state.following.filter(a => a.id !== artist.id);
  else state.following.unshift(artist);
  saveData("following", state.following);
  renderSidebar();
}
function addRecent(track) {
  state.recent = state.recent.filter(t => t.id !== track.id);
  state.recent.unshift(track);
  if (state.recent.length > 20) state.recent.length = 20;
  saveData("recent", state.recent);
  saveData("last", track);
}

/* ---------------- building blocks ---------------- */

function artistLink(t) {
  if (!t.artistId) return esc(t.artist);
  return '<a href="#/artist/' + t.artistId + '">' + esc(t.artist) + "</a>";
}

function makeCard(o) {
  let h = '<div class="card' + (o.round ? " round" : "") + '"';
  if (o.link) h += ' data-link="' + o.link + '"';
  if (o.attrs) h += " " + o.attrs;
  h += '><div class="card-img-wrap"><div class="card-img">';
  h += o.img ? '<img src="' + esc(o.img) + '" loading="lazy" alt="">' : icon(o.round ? "person" : "music");
  h += "</div>";
  if (o.play) {
    h += '<button class="card-play" data-act="play-card" data-kind="' + o.play.kind + '" data-id="' + o.play.id + '" aria-label="Play">' + icon("play") + "</button>";
  } else {
    h += '<button class="card-play" aria-label="Play">' + icon("play") + "</button>";
  }
  h += '</div><div class="card-title">' + esc(o.title) + '</div><div class="card-sub">' + esc(o.sub || "") + "</div></div>";
  return h;
}
function albumCard(a) {
  let sub = "Album";
  if (a.year && a.artist) sub = a.year + " \u2022 " + a.artist;
  else if (a.artist) sub = a.artist;
  else if (a.year) sub = a.year;
  return makeCard({ img: a.cover, title: a.title, sub: sub, link: "#/album/" + a.id, play: { kind: "album", id: a.id } });
}
function artistCard(a) {
  return makeCard({ img: a.cover, title: a.name, sub: a.genre || "Artist", link: "#/artist/" + a.id, round: true, play: { kind: "artist", id: a.id } });
}
function trackCard(t, listName, i) {
  return makeCard({ img: t.cover, title: t.title, sub: t.artist, attrs: 'data-act="play-track" data-list="' + listName + '" data-i="' + i + '"' });
}
function cardsFor(items, builder) {
  let h = "";
  for (let i = 0; i < items.length; i++) h += builder(items[i], i);
  return h;
}
function shelf(title, cardsHtml) {
  if (!cardsHtml) return "";
  return '<section class="shelf"><div class="shelf-head"><h2 class="shelf-title">' + esc(title) +
    '</h2><button class="shelf-more" data-act="expand-shelf">Show all</button></div><div class="grid">' + cardsHtml + "</div></section>";
}

function tableHead(withAlbum) {
  let h = '<div class="t-head"><div class="t-num-h">#</div><div>Title</div>';
  if (withAlbum) h += '<div class="album-h">Album</div>';
  return h + '<div></div><div class="t-time-h">' + icon("clock") + "</div><div></div></div>";
}
function trackRow(t, i, listName, opts) {
  const liked = isLiked(t.id);
  let h = '<div class="t-row' + (t.noPreview ? " unavailable" : "") + '" data-list="' + listName + '" data-i="' + i + '" data-id="' + t.id + '">';
  h += '<div class="t-num" data-act="play-track"><span class="num-text">' + (i + 1) + '</span><span class="num-play">' + icon("play") + '</span><span class="eq"><i></i><i></i><i></i></span></div>';
  h += '<div class="t-main">';
  if (opts.cover) h += '<img src="' + esc(t.coverSmall) + '" loading="lazy" alt="">';
  h += '<div class="t-text"><div class="t-title">' + esc(t.title) + '</div><div class="t-artist">';
  if (t.explicit) h += '<span class="explicit">E</span>';
  h += artistLink(t) + "</div></div></div>";
  if (opts.album) h += '<div class="t-album"><a href="#/album/' + t.albumId + '">' + esc(t.albumTitle) + "</a></div>";
  h += '<button class="t-heart' + (liked ? " liked" : "") + '" data-act="like" data-id="' + t.id + '" aria-label="Like">' + icon(liked ? "heartFill" : "heart") + "</button>";
  h += '<div class="t-time">' + fmtTime(t.duration) + "</div>";
  h += '<button class="t-more" data-act="more" data-id="' + t.id + '" aria-label="More options">' + icon("dots") + "</button></div>";
  return h;
}
function trackTable(tracks, listName, opts) {
  opts = opts || {};
  lists[listName] = tracks;
  let cls = "tracks";
  if (opts.album) cls += " album-col";
  if (opts.extra) cls += " " + opts.extra;
  let h = '<div class="' + cls + '">';
  if (opts.head !== false) h += tableHead(opts.album);
  for (let i = 0; i < tracks.length; i++) h += trackRow(tracks[i], i, listName, opts);
  return h + "</div>";
}

function entityHead(o) {
  let size = "";
  if (o.title.length > 40) size = "small";
  else if (o.title.length > 16) size = "mid";
  let h = '<div class="entity-head"><div class="entity-cover ' + (o.coverClass || "") + '">';
  if (o.coverHtml) h += o.coverHtml;
  else if (o.cover) h += '<img src="' + esc(o.cover) + '" alt="">';
  else h += icon("music");
  h += '</div><div class="entity-info"><div class="entity-type">' + esc(o.type) + "</div>";
  h += '<h1 class="entity-title ' + size + '">' + esc(o.title) + "</h1>";
  return h + '<div class="entity-meta">' + o.meta + "</div></div></div>";
}
function actionBar(extraHtml) {
  return '<div class="actions"><button class="big-play" id="page-play" data-act="play-page" aria-label="Play">' + icon("play") +
    '</button><button class="act-btn" data-act="shuffle-page" title="Shuffle play" aria-label="Shuffle play">' + icon("shuffle") + "</button>" + (extraHtml || "") + "</div>";
}
function emptyBox(title, text, buttonHtml) {
  return '<div class="empty"><h2>' + esc(title) + "</h2><p>" + esc(text) + "</p>" + (buttonHtml || "") + "</div>";
}
function footerNote() {
  return '<div class="footer-note">This is a learning project and is not affiliated with any music service. ' +
    "Music data and free 30 second previews come from the Apple iTunes Search API.</div>";
}
function playlistCoverHtml(p) {
  if (!p.tracks.length) return icon("music");
  if (p.tracks.length < 4) return '<img src="' + esc(p.tracks[0].cover) + '" alt="">';
  let h = "";
  for (let i = 0; i < 4; i++) h += '<img src="' + esc(p.tracks[i].cover) + '" alt="">';
  return h;
}

function renderSidebar() {
  let h = '<div class="lib-item" data-link="#/liked"><div class="lib-img liked">' + icon("heartFill") +
    '</div><div class="lib-text"><div class="lib-name">Liked Songs</div><div class="lib-sub">Playlist \u2022 ' + state.liked.length + " songs</div></div></div>";
  state.playlists.forEach(p => {
    h += '<div class="lib-item" data-link="#/mine/' + p.id + '"><div class="lib-img' + (p.tracks.length >= 4 ? " grid4" : "") + '">' + playlistCoverHtml(p) +
      '</div><div class="lib-text"><div class="lib-name">' + esc(p.name) + '</div><div class="lib-sub">Playlist \u2022 You</div></div></div>';
  });
  state.following.forEach(a => {
    h += '<div class="lib-item" data-link="#/artist/' + a.id + '"><div class="lib-img round">' +
      (a.cover ? '<img src="' + esc(a.cover) + '" alt="">' : icon("person")) +
      '</div><div class="lib-text"><div class="lib-name">' + esc(a.name) + '</div><div class="lib-sub">Artist</div></div></div>';
  });
  if (!state.playlists.length) {
    h += '<div class="lib-promo"><b>Create your first playlist</b><p>It\'s easy, we\'ll help you</p><button class="pill small" data-act="new-playlist">Create playlist</button></div>';
  }
  $("#lib-list").innerHTML = h;
  markActiveLinks();
}
function markActiveLinks() {
  $$("#lib-list .lib-item").forEach(el => el.classList.toggle("active", el.dataset.link === location.hash));
}
function refreshHearts() {
  $$(".t-heart").forEach(btn => {
    const liked = isLiked(Number(btn.dataset.id));
    btn.classList.toggle("liked", liked);
    btn.innerHTML = icon(liked ? "heartFill" : "heart");
  });
  updateNowHeart();
}

/* ---------------- menus and popups ---------------- */

function closeMenu() { $("#menu").style.display = "none"; }
function openMenu(x, y, items) {
  const menu = $("#menu");
  menu.innerHTML = "";
  items.forEach(item => {
    if (item === "-") {
      const line = document.createElement("div");
      line.className = "menu-sep";
      menu.appendChild(line);
      return;
    }
    const btn = document.createElement("button");
    btn.className = "menu-item";
    btn.textContent = item.label;
    btn.addEventListener("click", e => { e.stopPropagation(); closeMenu(); item.fn(); });
    menu.appendChild(btn);
  });
  menu.style.display = "block";
  const w = menu.offsetWidth, h = menu.offsetHeight;
  if (x + w > window.innerWidth - 8) x = window.innerWidth - w - 8;
  if (y + h > window.innerHeight - 8) y = window.innerHeight - h - 8;
  menu.style.left = Math.max(8, x) + "px";
  menu.style.top = Math.max(8, y) + "px";
}
function openTrackMenu(track, x, y) {
  if (!track) return;
  const items = [
    { label: "Play next", fn: () => playNext(track) },
    { label: isLiked(track.id) ? "Remove from Liked Songs" : "Save to Liked Songs", fn: () => toggleLike(track) },
    { label: "Add to playlist", fn: () => showPickPlaylist(track) }
  ];
  if (location.hash.indexOf("#/mine/") === 0) {
    const pid = location.hash.slice(7);
    items.push({ label: "Remove from this playlist", fn: () => removeFromPlaylist(pid, track.id) });
  }
  addExtraMenuItems(items, track);
  items.push("-");
  if (track.artistId) items.push({ label: "Go to artist", fn: () => { location.hash = "#/artist/" + track.artistId; } });
  if (track.albumId) items.push({ label: "Go to album", fn: () => { location.hash = "#/album/" + track.albumId; } });
  openMenu(x, y, items);
}
function showModal(html) { $("#modal").innerHTML = html; $("#modal-back").classList.remove("hidden"); }
function closeModal() { $("#modal-back").classList.add("hidden"); $("#modal").innerHTML = ""; }
function showNameModal(title, startValue, buttonText, onDone) {
  showModal("<h2>" + esc(title) + '</h2><input class="text" id="modal-input" type="text" maxlength="60" placeholder="Name" value="' + esc(startValue) +
    '"><div class="modal-actions"><button class="pill ghost" data-act="close-modal">Cancel</button><button class="pill green" id="modal-ok">' + esc(buttonText) + "</button></div>");
  const input = $("#modal-input");
  input.focus(); input.select();
  function finish() { const v = input.value; closeModal(); onDone(v); }
  $("#modal-ok").addEventListener("click", finish);
  input.addEventListener("keydown", e => { if (e.key === "Enter") finish(); });
}
function showNewPlaylistModal() {
  showNameModal("Create playlist", "", "Create", name => {
    const p = createPlaylist(name);
    toast("Created " + p.name);
    location.hash = "#/mine/" + p.id;
  });
}
let pendingTrack = null;
function showPickPlaylist(track) {
  let h = '<h2>Add to playlist</h2><button class="pick" data-act="pick-new"><div class="lib-img">' + icon("plus") + "</div><div>New playlist</div></button>";
  state.playlists.forEach(p => {
    h += '<button class="pick" data-act="pick-playlist" data-pid="' + p.id + '"><div class="lib-img' + (p.tracks.length >= 4 ? " grid4" : "") + '">' +
      playlistCoverHtml(p) + "</div><div>" + esc(p.name) + "</div></button>";
  });
  h += '<div class="modal-actions"><button class="pill ghost" data-act="close-modal">Close</button></div>';
  showModal(h);
  pendingTrack = track;
}

/* ---------------- pages ---------------- */

function greeting() {
  const hour = new Date().getHours();
  return hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
}

const GENRES = [
  ["Pop", "pop hits"], ["Hip-Hop", "hip hop hits"], ["Rock", "rock classics"], ["Bollywood", "bollywood hits"],
  ["Dance", "dance electronic"], ["R&B", "r&b soul"], ["Country", "country hits"], ["Latin", "latin hits"],
  ["Indie", "indie alternative"], ["Jazz", "jazz classics"], ["Classical", "classical music"], ["Metal", "heavy metal"],
  ["K-Pop", "kpop hits"], ["Reggae", "reggae"], ["Blues", "blues"], ["Lo-fi / Chill", "chill lofi"],
  ["Punjabi", "punjabi hits"], ["Tamil", "tamil hits"], ["Telugu", "telugu hits"], ["90s", "90s hits"]
];

async function songsByIds(ids) {
  if (!ids.length) return [];
  const rows = await safeItunes("/lookup?id=" + ids.join(",") + CC);
  const tracks = mapTracks(rows);
  const order = {};
  ids.forEach((id, i) => { order[id] = i; });
  tracks.sort((a, b) => (order[a.id] == null ? 99 : order[a.id]) - (order[b.id] == null ? 99 : order[b.id]));
  return tracks;
}

async function viewHome() {
  const results = await Promise.all([
    rss("/api/v2/" + COUNTRY + "/music/most-played/30/songs.json"),
    rss("/api/v2/" + COUNTRY + "/music/most-played/24/albums.json"),
    safeItunes("/search?term=bollywood%20hits&media=music&entity=song&limit=24" + CC),
    safeItunes("/search?term=hip%20hop%20hits&media=music&entity=song&limit=24" + CC)
  ]);

  let trending = await songsByIds(results[0].map(r => Number(r.id)));
  if (!trending.length) {
    trending = mapTracks(await safeItunes("/search?term=top%20hits&media=music&entity=song&limit=30" + CC));
  }
  const albums = results[1].map(mapRssAlbum);
  const bolly = mapTracks(results[2]);
  const hiphop = mapTracks(results[3]);

  if (!trending.length && !albums.length && !bolly.length) {
    throw new Error("Could not load music from Apple. Check your internet connection, firewall or VPN. The black window running the program shows the exact reason.");
  }

  lists["home-trending"] = trending;
  lists["home-bolly"] = bolly;
  lists["home-hiphop"] = hiphop;
  lists["home-recent"] = state.recent;

  let h = '<div class="greeting">' + greeting() + '</div><div class="quick-grid">';
  h += '<div class="quick" data-link="#/liked"><div class="quick-ph liked">' + icon("heartFill") + '</div><span class="q-name">Liked Songs</span></div>';
  let count = 1;
  state.playlists.slice(0, 2).forEach(p => {
    h += '<div class="quick" data-link="#/mine/' + p.id + '"><div class="quick-ph">' + icon("music") + '</div><span class="q-name">' + esc(p.name) + "</span></div>";
    count++;
  });
  for (let i = 0; i < albums.length && count < 8; i++) {
    const a = albums[i];
    h += '<div class="quick" data-link="#/album/' + a.id + '"><img src="' + esc(a.cover) + '" alt="" loading="lazy"><span class="q-name">' + esc(a.title) +
      '</span><button class="card-play" data-act="play-card" data-kind="album" data-id="' + a.id + '" aria-label="Play">' + icon("play") + "</button></div>";
    count++;
  }
  h += "</div>";

  if (state.recent.length) h += shelf("Recently played", cardsFor(state.recent, (t, i) => trackCard(t, "home-recent", i)));
  h += shelf("Trending songs", cardsFor(trending, (t, i) => trackCard(t, "home-trending", i)));
  h += shelf("Popular albums", cardsFor(albums, albumCard));
  h += shelf("Bollywood hits", cardsFor(bolly, (t, i) => trackCard(t, "home-bolly", i)));
  h += shelf("Hip-hop hits", cardsFor(hiphop, (t, i) => trackCard(t, "home-hiphop", i)));
  h += footerNote();
  return { html: h, tracks: [], color: "#2a3b55" };
}

async function viewSearch(query) {
  if (!query) return viewBrowse();
  const t = q(query);
  const results = await Promise.all([
    safeItunes("/search?term=" + t + "&media=music&entity=song&limit=30" + CC),
    safeItunes("/search?term=" + t + "&media=music&entity=album&limit=15" + CC),
    safeItunes("/search?term=" + t + "&media=music&entity=musicArtist&limit=10" + CC)
  ]);
  const tracks = mapTracks(results[0]);
  const artists = results[2].filter(r => r.artistId).map(mapArtist);
  // iTunes has no artist photos, so borrow the cover of that artist's first song
  artists.forEach(a => {
    const hit = tracks.find(x => x.artistId === a.id);
    if (hit) a.cover = hit.cover;
  });
  state.search = { query: query, tracks: tracks, albums: mapAlbums(results[1]), artists: artists };
  return renderSearchResults();
}

async function viewBrowse() {
  let h = recentSearchesHtml() + '<h2 class="section-title" style="margin-top:8px">Browse all</h2><div class="genre-grid">';
  GENRES.forEach((g, n) => {
    h += '<div class="genre-card" style="background:' + PALETTE[n % PALETTE.length] + '" data-link="#/genre/' + q(g[1]) + "|" + q(g[0]) + '"><span>' + esc(g[0]) + "</span></div>";
  });
  h += "</div>";
  return { html: h + footerNote(), tracks: [], color: "#1f1f1f" };
}

function renderSearchResults() {
  const s = state.search;
  const filter = state.searchFilter;
  if (!s.tracks.length && !s.artists.length && !s.albums.length) {
    return {
      html: emptyBox('No results found for "' + s.query + '"', "Please make sure your words are spelled correctly, or use fewer or different keywords."),
      tracks: [], color: "#1f1f1f"
    };
  }
  const chips = [["all", "All"], ["songs", "Songs"], ["artists", "Artists"], ["albums", "Albums"]];
  let h = '<div class="chips" style="padding-top:8px">';
  chips.forEach(c => {
    h += '<button class="chip' + (filter === c[0] ? " active" : "") + '" data-act="filter" data-filter="' + c[0] + '">' + c[1] + "</button>";
  });
  h += "</div>";

  if (filter === "all") {
    h += '<div class="top-grid">' + topResult(s);
    h += '<div><h2 class="section-title">Songs</h2>' + trackTable(s.tracks.slice(0, 4), "search-top", { cover: true, head: false }) + "</div></div>";
    h += shelf("Artists", cardsFor(s.artists, artistCard));
    h += shelf("Albums", cardsFor(s.albums, albumCard));
  }
  if (filter === "songs") h += '<div style="margin-top:16px">' + trackTable(s.tracks, "search-songs", { cover: true, album: true }) + "</div>";
  if (filter === "artists") h += wrapped(cardsFor(s.artists, artistCard));
  if (filter === "albums") h += wrapped(cardsFor(s.albums, albumCard));
  return { html: h, tracks: s.tracks, color: "#1f1f1f" };
}
function wrapped(cardsHtml) { return '<div class="grid wrap" style="margin-top:16px">' + cardsHtml + "</div>"; }

function topResult(s) {
  const firstArtist = s.artists[0], firstTrack = s.tracks[0];
  const lower = s.query.toLowerCase();
  let h = '<div><h2 class="section-title">Top result</h2>';
  if (firstArtist && (!firstTrack || firstArtist.name.toLowerCase() === lower)) {
    const a = firstArtist;
    h += '<div class="top-card" data-link="#/artist/' + a.id + '">' +
      (a.cover ? '<img src="' + esc(a.cover) + '" alt="" style="border-radius:50%">' : '<div class="ph">' + icon("person") + "</div>") +
      '<div class="name">' + esc(a.name) + '</div><span class="tag">Artist</span>' +
      '<button class="card-play" data-act="play-card" data-kind="artist" data-id="' + a.id + '" aria-label="Play">' + icon("play") + "</button></div>";
  } else if (firstTrack) {
    const t = firstTrack;
    lists["search-songs"] = s.tracks;
    h += '<div class="top-card" data-act="play-track" data-list="search-songs" data-i="0"><img src="' + esc(t.cover) + '" alt=""><div class="name">' + esc(t.title) +
      '</div><span class="sub">' + esc(t.artist) + '</span><span class="tag">Song</span><button class="card-play" aria-label="Play">' + icon("play") + "</button></div>";
  } else if (s.albums[0]) {
    const a = s.albums[0];
    h += '<div class="top-card" data-link="#/album/' + a.id + '"><img src="' + esc(a.cover) + '" alt=""><div class="name">' + esc(a.title) +
      '</div><span class="sub">' + esc(a.artist) + '</span><span class="tag">Album</span><button class="card-play" data-act="play-card" data-kind="album" data-id="' + a.id +
      '" aria-label="Play">' + icon("play") + "</button></div>";
  } else {
    return "<div></div>";
  }
  return h + "</div>";
}

async function viewAlbum(id) {
  const rows = await itunes("/lookup?id=" + encodeURIComponent(id) + "&entity=song" + CC);
  const info = rows.find(r => r.wrapperType === "collection");
  if (!info) throw new Error("Album not found.");
  const tracks = mapTracks(rows);
  const a = mapAlbum(info);
  const total = tracks.reduce((n, t) => n + t.duration, 0);

  let meta = "";
  if (a.artistId) meta += '<a class="bold" href="#/artist/' + a.artistId + '">' + esc(a.artist) + "</a> \u2022 ";
  else meta += '<span class="bold">' + esc(a.artist) + "</span> \u2022 ";
  if (a.year) meta += a.year + " \u2022 ";
  meta += tracks.length + ' songs, <span class="dim">' + fmtLong(total) + "</span>";

  let h = entityHead({ type: info.collectionType === "Album" ? "Album" : "Single / EP", title: a.title, cover: a.big, meta: meta });
  h += actionBar();
  h += trackTable(tracks, "album", { album: false, cover: false });
  if (info.copyright) h += '<div class="footer-note" style="margin-top:32px;border:none;padding:0">' + esc(info.copyright) + "</div>";

  if (a.artistId) {
    const more = mapAlbums(await safeItunes("/lookup?id=" + a.artistId + "&entity=album&limit=20" + CC)).filter(x => x.id !== a.id);
    h += shelf("More by " + a.artist, cardsFor(more, albumCard));
  }
  h += footerNote();
  return { html: h, tracks: tracks, coverUrl: a.cover, color: hashColor(a.title) };
}

async function viewArtist(id) {
  const results = await Promise.all([
    itunes("/lookup?id=" + encodeURIComponent(id) + "&entity=song&limit=25" + CC),
    safeItunes("/lookup?id=" + encodeURIComponent(id) + "&entity=album&limit=50" + CC)
  ]);
  const info = results[0].find(r => r.wrapperType === "artist");
  const tracks = mapTracks(results[0]);
  const albums = mapAlbums(results[1]);
  const name = info ? info.artistName : (tracks[0] ? tracks[0].artist : "Artist");
  const cover = tracks[0] ? art(tracks[0].cover, 600) : (albums[0] ? albums[0].big : "");

  const following = isFollowing(Number(id));
  const followBtn = '<button class="pill outline" id="follow-btn" data-act="follow" data-id="' + esc(id) + '" data-name="' + esc(name) +
    '" data-pic="' + esc(cover) + '">' + (following ? "Following" : "Follow") + "</button>";

  let h = entityHead({
    type: "Artist", title: name, cover: cover, coverClass: "round",
    meta: '<span class="bold">' + esc(info && info.primaryGenreName ? info.primaryGenreName : "Music") + "</span>"
  });
  h += actionBar(followBtn);
  if (tracks.length) {
    h += '<h2 class="section-title">Popular</h2>';
    h += trackTable(tracks, "artist-top", { cover: true, head: false, extra: "collapsed" });
    if (tracks.length > 5) h += '<button class="see-more" data-act="see-more">See more</button>';
  }
  const sorted = albums.slice().sort((x, y) => String(y.year).localeCompare(String(x.year)));
  h += shelf("Discography", cardsFor(sorted, albumCard));
  h += footerNote();
  return { html: h, tracks: tracks, coverUrl: art(cover, 300), color: hashColor(name) };
}

async function viewGenre(arg) {
  const parts = arg.split("|");
  const term = decodeURIComponent(parts[0]);
  const name = parts[1] ? decodeURIComponent(parts[1]) : term;
  const results = await Promise.all([
    safeItunes("/search?term=" + q(term) + "&media=music&entity=song&limit=40" + CC),
    safeItunes("/search?term=" + q(term) + "&media=music&entity=album&limit=20" + CC)
  ]);
  const tracks = mapTracks(results[0]);
  let h = entityHead({ type: "Genre", title: name, cover: tracks[0] ? art(tracks[0].cover, 600) : "", meta: "Top songs and albums right now" });
  h += actionBar();
  if (tracks.length) h += '<h2 class="section-title">Top songs</h2>' + trackTable(tracks, "genre", { album: true, cover: true });
  h += shelf("Albums", cardsFor(mapAlbums(results[1]), albumCard));
  h += footerNote();
  return { html: h, tracks: tracks, color: PALETTE[hashNumber(term) % PALETTE.length] };
}

async function viewLiked() {
  const tracks = state.liked;
  let h = entityHead({ type: "Playlist", title: "Liked Songs", coverHtml: icon("heartFill"), coverClass: "liked", meta: '<span class="bold">You</span> \u2022 ' + tracks.length + " songs" });
  if (!tracks.length) {
    h += emptyBox("Songs you like will appear here", "Save songs by tapping the heart icon.", '<a class="pill" href="#/search">Find songs</a>');
    return { html: h, tracks: [], color: "#4a2fc9" };
  }
  h += actionBar() + trackTable(tracks, "liked", { album: true, cover: true }) + footerNote();
  return { html: h, tracks: tracks, color: "#4a2fc9" };
}

async function viewMine(id) {
  const p = findPlaylist(id);
  if (!p) return { html: emptyBox("Playlist not found", "It may have been deleted.", '<a class="pill" href="#/home">Go home</a>'), tracks: [], color: "#1f1f1f" };
  let h = entityHead({
    type: "Playlist", title: p.name, coverHtml: playlistCoverHtml(p), coverClass: p.tracks.length >= 4 ? "grid4" : "",
    meta: '<span class="bold">You</span> \u2022 ' + p.tracks.length + " songs"
  });
  h += actionBar(
    '<button class="act-btn" data-act="rename-playlist" data-pid="' + p.id + '"><span style="font-size:14px">Rename</span></button>' +
    '<button class="act-btn" data-act="delete-playlist" data-pid="' + p.id + '"><span style="font-size:14px">Delete</span></button>');
  if (!p.tracks.length) {
    h += emptyBox("Let's find something for your playlist", "Use the ... menu on any song and choose Add to playlist.", '<a class="pill" href="#/search">Find songs</a>');
  } else {
    h += trackTable(p.tracks, "mine", { album: true, cover: true });
  }
  return { html: h, tracks: p.tracks, color: hashColor(p.name) };
}

function viewError(err) {
  const text = err && err.message ? err.message : "Something went wrong.";
  return { html: emptyBox("Something went wrong", text, '<button class="pill" data-act="retry">Try again</button>'), tracks: [], color: "#1f1f1f" };
}

let renderToken = 0;
async function router(soft) {
  renderToken++;
  const myToken = renderToken;
  const hash = location.hash || "#/home";
  const parts = hash.slice(2).split("/");
  const name = parts[0] || "home";
  const rawArg = parts.slice(1).join("/");
  const arg = name === "genre" ? rawArg : decodeURIComponent(rawArg);

  updateNav(name, arg);
  const main = $("#main"), view = $("#view");
  if (!soft) {
    view.innerHTML = '<div class="spinner"></div>';
    main.scrollTop = 0;
    main.style.setProperty("--hue", "#2a3b55");
  }

  let result;
  try {
    if (name === "home") result = await viewHome();
    else if (name === "search") result = await viewSearch(arg);
    else if (name === "album") result = await viewAlbum(arg);
    else if (name === "artist") result = await viewArtist(arg);
    else if (name === "genre") result = await viewGenre(arg);
    else if (name === "liked") result = await viewLiked();
    else if (name === "mine") result = await viewMine(arg);
    else if (name === "library") result = await viewLibrary();
    else if (name === "stats") result = await viewStats();
    else result = await viewHome();
  } catch (err) {
    result = viewError(err);
  }
  if (myToken !== renderToken) return;

  const scroll = main.scrollTop;
  view.innerHTML = result.html;
  if (soft) main.scrollTop = scroll;
  main.style.setProperty("--hue", result.color || "#2a3b55");
  state.pageTracks = result.tracks || [];
  if (name === "home") loadMadeForYou(myToken);

  if (result.coverUrl) {
    getImageColor(result.coverUrl).then(color => {
      if (color && myToken === renderToken) main.style.setProperty("--hue", color);
    });
  }
  markPlaying();
  updatePageButton();
  updateTopbar();
}

function updateNav(name, arg) {
  $("#nav-home").classList.toggle("active", name === "home");
  $("#nav-search").classList.toggle("active", name === "search");
  $("#search-box").classList.toggle("hidden", name !== "search");
  const input = $("#search-input");
  if (name === "search" && document.activeElement !== input) input.value = arg;
  $("#search-clear").classList.toggle("hidden", !input.value);
  markActiveLinks();
}
function updateTopbar() {
  $("#topbar").style.setProperty("--a", Math.min($("#main").scrollTop / 200, 1));
}

/* ---------------- the player ---------------- */

const audio = $("#audio");
function currentTrack() { return state.queue[state.index] || null; }

function playList(tracks, startTrack, forceShuffle) {
  const playable = tracks.filter(t => !t.noPreview);
  if (!playable.length) { toast("Nothing to play here"); return; }
  if (forceShuffle) { state.shuffle = true; updateModeButtons(); }
  state.queue = playable.slice();
  state.past = [];
  state.failCount = 0;
  let start = startTrack ? playable.indexOf(startTrack) : 0;
  if (start < 0) start = 0;
  if (!startTrack && state.shuffle) start = Math.floor(Math.random() * playable.length);
  state.index = start;
  startCurrent();
}

function startCurrent() {
  const track = currentTrack();
  if (!track) return;
  addRecent(track);
  updateNowPlaying();
  markPlaying();
  updatePageButton();
  renderQueue();
  audio.src = track.preview;
  audio.play().catch(() => {});
}

function togglePlay() {
  if (!currentTrack()) { toast("Pick a song to play"); return; }
  if (audio.paused) audio.play().catch(() => {});
  else audio.pause();
}

function nextTrack(auto) {
  if (!state.queue.length) return;
  if (auto && state.repeat === 2) { audio.currentTime = 0; audio.play().catch(() => {}); return; }
  let next = state.index;
  if (state.shuffle && state.queue.length > 1) {
    while (next === state.index) next = Math.floor(Math.random() * state.queue.length);
  } else {
    next = state.index + 1;
    if (next >= state.queue.length) {
      if (state.repeat === 1 || !auto) next = 0;
      else { audio.pause(); audio.currentTime = 0; return; }
    }
  }
  state.past.push(state.index);
  state.index = next;
  startCurrent();
}

function prevTrack() {
  if (!state.queue.length) return;
  if (audio.currentTime > 3) { audio.currentTime = 0; return; }
  if (state.past.length) state.index = state.past.pop();
  else if (state.index > 0) state.index--;
  else { audio.currentTime = 0; return; }
  startCurrent();
}

function playNext(track) {
  if (!currentTrack()) { playList([track], track); return; }
  state.queue.splice(state.index + 1, 0, track);
  toast("Added to queue");
  renderQueue();
}

async function playCollection(kind, id) {
  try {
    let tracks = [];
    if (kind === "album") tracks = mapTracks(await itunes("/lookup?id=" + id + "&entity=song" + CC));
    else if (kind === "artist") tracks = mapTracks(await itunes("/lookup?id=" + id + "&entity=song&limit=25" + CC));
    playList(tracks, null);
  } catch (err) {
    toast("Could not load songs");
  }
}

function updateNowPlaying() {
  const t = currentTrack();
  const cover = $("#np-cover");
  if (!t) {
    cover.innerHTML = icon("music");
    $("#np-title").innerHTML = ""; $("#np-artist").innerHTML = "";
    $("#np-heart").classList.add("hidden");
    return;
  }
  cover.innerHTML = t.cover ? '<img src="' + esc(t.cover) + '" alt="">' : icon("music");
  $("#np-title").innerHTML = t.albumId ? '<a href="#/album/' + t.albumId + '">' + esc(t.title) + "</a>" : esc(t.title);
  $("#np-artist").innerHTML = artistLink(t);
  $("#np-heart").classList.remove("hidden");
  updateNowHeart();
  document.title = t.title + " \u2022 " + t.artist;
  setMediaSession(t);
}
function updateNowHeart() {
  const t = currentTrack();
  if (!t) return;
  const liked = isLiked(t.id);
  $("#np-heart").classList.toggle("liked", liked);
  $("#np-heart").innerHTML = icon(liked ? "heartFill" : "heart");
}
function updateModeButtons() {
  $("#btn-shuffle").classList.toggle("on", state.shuffle);
  $("#btn-repeat").classList.toggle("on", state.repeat > 0);
  $("#btn-repeat").innerHTML = icon(state.repeat === 2 ? "repeatOne" : "repeat");
}
function updatePlayButton() {
  const playing = !audio.paused && !!audio.src;
  $("#btn-play").innerHTML = icon(playing ? "pause" : "play");
  $("#btn-play").title = playing ? "Pause" : "Play";
  document.body.classList.toggle("paused", !playing);
  updatePageButton();
}
function updatePageButton() {
  const btn = $("#page-play");
  if (!btn) return;
  const t = currentTrack();
  const here = t && state.pageTracks.indexOf(t) >= 0;
  btn.innerHTML = icon(here && !audio.paused ? "pause" : "play");
}
function markPlaying() {
  const t = currentTrack();
  $$(".t-row").forEach(row => {
    const id = Number(row.dataset.id);
    const track = trackStore[id];
    row.classList.toggle("playing", !!t && id === t.id);
    row.classList.toggle("unavailable", !!(track && track.noPreview));
  });
}
function setFill(input) {
  const min = Number(input.min) || 0, max = Number(input.max) || 100;
  input.style.setProperty("--fill", ((input.value - min) / (max - min)) * 100 + "%");
}
function updateVolumeIcon() {
  let name = "volHigh";
  if (state.muted || state.volume === 0) name = "volMute";
  else if (state.volume < 0.5) name = "volLow";
  $("#btn-mute").innerHTML = icon(name);
}
function setMediaSession(t) {
  if (!("mediaSession" in navigator)) return;
  try {
    navigator.mediaSession.metadata = new MediaMetadata({
      title: t.title, artist: t.artist, album: t.albumTitle,
      artwork: [{ src: t.cover, sizes: "300x300", type: "image/jpeg" }]
    });
  } catch (e) {}
}

function queueItem(t, i, now) {
  return '<div class="q-item' + (now ? " now" : "") + '" data-act="queue-jump" data-i="' + i + '"><img src="' + esc(t.coverSmall) +
    '" alt=""><div class="q-t"><div class="q-title">' + esc(t.title) + '</div><div class="q-artist">' + esc(t.artist) + "</div></div></div>";
}
function renderQueue() {
  if (!$("#app").classList.contains("queue-open")) return;
  let h = '<div class="q-head"><h2>Queue</h2><button class="icon-btn" data-act="toggle-queue" aria-label="Close queue">' + icon("close") + "</button></div>";
  const now = currentTrack();
  if (!now) {
    h += '<div class="q-empty">Play something and your queue will show up here.</div>';
  } else {
    h += '<div class="q-label">Now playing</div>' + queueItem(now, state.index, true);
    if (state.index + 1 < state.queue.length) {
      h += '<div class="q-label">Next up</div>';
      const last = Math.min(state.queue.length, state.index + 51);
      for (let i = state.index + 1; i < last; i++) h += queueItem(state.queue[i], i, false);
    }
  }
  $("#queue").innerHTML = h;
}

let seeking = false;
const seekBar = $("#seek");
const volumeBar = $("#volume");

audio.addEventListener("play", updatePlayButton);
audio.addEventListener("pause", updatePlayButton);
audio.addEventListener("playing", () => { state.failCount = 0; updatePlayButton(); });
audio.addEventListener("loadedmetadata", () => { $("#t-dur").textContent = fmtTime(audio.duration); });
audio.addEventListener("timeupdate", () => {
  if (!audio.duration || seeking) return;
  seekBar.value = (audio.currentTime / audio.duration) * 1000;
  setFill(seekBar);
  $("#t-cur").textContent = fmtTime(audio.currentTime);
});
audio.addEventListener("ended", () => {
  if (sleepEndOfTrackHit()) return;
  nextTrack(true);
});
audio.addEventListener("error", () => {
  const t = currentTrack();
  if (!t || !audio.src) return;
  state.failCount++;
  toast('Could not play "' + t.title + '"');
  if (state.failCount < 4) nextTrack(true);
});

seekBar.addEventListener("input", () => {
  seeking = true;
  setFill(seekBar);
  if (audio.duration) $("#t-cur").textContent = fmtTime((seekBar.value / 1000) * audio.duration);
});
seekBar.addEventListener("change", () => {
  if (audio.duration) audio.currentTime = (seekBar.value / 1000) * audio.duration;
  seeking = false;
});
volumeBar.addEventListener("input", () => {
  state.volume = volumeBar.value / 100;
  state.muted = false;
  audio.volume = state.volume;
  audio.muted = false;
  setFill(volumeBar);
  updateVolumeIcon();
  saveData("volume", state.volume);
});
function toggleMute() {
  state.muted = !state.muted;
  audio.muted = state.muted;
  updateVolumeIcon();
}

/* ---------------- clicks and keys ---------------- */

function handleAction(el) {
  const act = el.dataset.act;
  if (handleExtraAction(act, el)) return;

  if (act === "play-track") {
    const source = el.closest("[data-list]");
    if (!source) return;
    const list = lists[source.dataset.list] || [];
    const track = list[Number(source.dataset.i)];
    if (!track) return;
    if (track.noPreview) { toast("No preview available for this song"); return; }
    if (currentTrack() === track) togglePlay();
    else playList(list, track);
    return;
  }
  if (act === "like") { toggleLike(trackStore[Number(el.dataset.id)]); return; }
  if (act === "like-current") { toggleLike(currentTrack()); return; }
  if (act === "more") {
    const box = el.getBoundingClientRect();
    openTrackMenu(trackStore[Number(el.dataset.id)], box.left - 190, box.bottom + 4);
    return;
  }
  if (act === "play-card") { playCollection(el.dataset.kind, el.dataset.id); return; }
  if (act === "play-page") {
    const t = currentTrack();
    if (t && state.pageTracks.indexOf(t) >= 0) togglePlay();
    else playList(state.pageTracks, null);
    return;
  }
  if (act === "shuffle-page") { playList(state.pageTracks, null, true); return; }

  if (act === "toggle-play") togglePlay();
  else if (act === "next") nextTrack(false);
  else if (act === "prev") prevTrack();
  else if (act === "shuffle") { state.shuffle = !state.shuffle; updateModeButtons(); }
  else if (act === "repeat") { state.repeat = (state.repeat + 1) % 3; updateModeButtons(); }
  else if (act === "mute") toggleMute();
  else if (act === "toggle-queue") {
    $("#app").classList.toggle("queue-open");
    $("#btn-queue").classList.toggle("on", $("#app").classList.contains("queue-open"));
    renderQueue();
  } else if (act === "queue-jump") {
    state.past.push(state.index);
    state.index = Number(el.dataset.i);
    startCurrent();
  }
  else if (act === "nav-back") history.back();
  else if (act === "nav-forward") history.forward();
  else if (act === "retry") router();
  else if (act === "clear-search") { $("#search-input").value = ""; $("#search-input").focus(); goSearch(""); }
  else if (act === "filter") {
    state.searchFilter = el.dataset.filter;
    if (state.search) {
      const result = renderSearchResults();
      $("#view").innerHTML = result.html;
      state.pageTracks = result.tracks;
      markPlaying();
    }
  }
  else if (act === "expand-shelf") {
    const grid = el.closest(".shelf").querySelector(".grid");
    el.textContent = grid.classList.toggle("wrap") ? "Show less" : "Show all";
  }
  else if (act === "see-more") {
    const box = $(".tracks.collapsed, .tracks.expanded");
    if (box) {
      const collapsed = box.classList.toggle("collapsed");
      box.classList.toggle("expanded", !collapsed);
      el.textContent = collapsed ? "See more" : "Show less";
    }
  }
  else if (act === "follow") {
    const id = Number(el.dataset.id);
    toggleFollow({ id: id, name: el.dataset.name, cover: el.dataset.pic });
    el.textContent = isFollowing(id) ? "Following" : "Follow";
  }
  else if (act === "new-playlist") showNewPlaylistModal();
  else if (act === "rename-playlist") {
    const p = findPlaylist(el.dataset.pid);
    if (!p) return;
    showNameModal("Rename playlist", p.name, "Save", name => {
      if (name.trim()) p.name = name.trim();
      saveData("playlists", state.playlists);
      renderSidebar();
      router(true);
    });
  }
  else if (act === "delete-playlist") {
    const p = findPlaylist(el.dataset.pid);
    if (!p) return;
    showModal("<h2>Delete playlist?</h2><p style='color:#b3b3b3'>This will delete " + esc(p.name) +
      ' from your library.</p><div class="modal-actions"><button class="pill ghost" data-act="close-modal">Cancel</button><button class="pill green" data-act="confirm-delete" data-pid="' + p.id + '">Delete</button></div>');
  }
  else if (act === "confirm-delete") { closeModal(); deletePlaylist(el.dataset.pid); }
  else if (act === "pick-playlist") { closeModal(); addToPlaylist(el.dataset.pid, pendingTrack); }
  else if (act === "pick-new") {
    const track = pendingTrack;
    closeModal();
    showNameModal("Create playlist", "", "Create", name => {
      const p = createPlaylist(name);
      addToPlaylist(p.id, track);
    });
  }
  else if (act === "close-modal") closeModal();
  else if (act === "premium") toast("This clone is free forever");
  else if (act === "profile") toast("Signed in as a guest");
}

document.addEventListener("click", event => {
  if (!event.target.closest("#menu")) closeMenu();
  if (event.target.id === "modal-back") { closeModal(); return; }

  const actEl = event.target.closest("[data-act]");
  if (actEl) { handleAction(actEl); return; }

  const linkEl = event.target.closest("[data-link]");
  if (linkEl && !event.target.closest("a, button")) { location.hash = linkEl.dataset.link; return; }

  const row = event.target.closest(".t-row");
  if (row && !event.target.closest("a, button")) {
    $$(".t-row.selected").forEach(r => r.classList.remove("selected"));
    row.classList.add("selected");
  }
});
document.addEventListener("dblclick", event => {
  const row = event.target.closest(".t-row");
  if (!row || event.target.closest("a, button")) return;
  const list = lists[row.dataset.list] || [];
  const track = list[Number(row.dataset.i)];
  if (track && !track.noPreview) playList(list, track);
});
document.addEventListener("contextmenu", event => {
  const row = event.target.closest(".t-row");
  if (!row) return;
  event.preventDefault();
  openTrackMenu(trackStore[Number(row.dataset.id)], event.clientX, event.clientY);
});
document.addEventListener("keydown", event => {
  const tag = event.target.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA") {
    if (event.key === "Escape") event.target.blur();
    return;
  }
  if (event.key === "Escape") { closeMenu(); closeModal(); }
  else if (event.code === "Space") { event.preventDefault(); togglePlay(); }
  else if (event.shiftKey && event.key === "ArrowRight") nextTrack(false);
  else if (event.shiftKey && event.key === "ArrowLeft") prevTrack();
  else if (event.shiftKey && event.key === "ArrowUp") { volumeBar.value = Math.min(100, Number(volumeBar.value) + 10); volumeBar.dispatchEvent(new Event("input")); }
  else if (event.shiftKey && event.key === "ArrowDown") { volumeBar.value = Math.max(0, Number(volumeBar.value) - 10); volumeBar.dispatchEvent(new Event("input")); }
  else if (event.key === "m") toggleMute();
  else if (event.key === "/") { event.preventDefault(); location.hash = "#/search"; setTimeout(() => $("#search-input").focus(), 50); }
});

let searchTimer = null;
function goSearch(text) {
  const clean = text.trim();
  history.replaceState(null, "", clean ? "#/search/" + encodeURIComponent(clean) : "#/search");
  router(true);
}
$("#search-input").addEventListener("input", event => {
  const text = event.target.value;
  $("#search-clear").classList.toggle("hidden", !text);
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => goSearch(text), 400);
});
$("#main").addEventListener("scroll", updateTopbar);
window.addEventListener("hashchange", () => router());

if ("mediaSession" in navigator) {
  try {
    navigator.mediaSession.setActionHandler("play", () => audio.play());
    navigator.mediaSession.setActionHandler("pause", () => audio.pause());
    navigator.mediaSession.setActionHandler("nexttrack", () => nextTrack(false));
    navigator.mediaSession.setActionHandler("previoustrack", () => prevTrack());
  } catch (e) {}
}

/* =====================================================================
   EXTRA FEATURES
   Everything below sits on top of the core player: settings, library and
   stats pages, a sleep timer, search history, "made for you" shelves,
   extra keyboard shortcuts, library import / export, song info, playlist
   re-ordering, and a few small conveniences.
   ===================================================================== */

Object.assign(ICONS, {
  moon: "M12 3a9 9 0 109 9c0-.46-.04-.92-.1-1.36a5.389 5.389 0 01-4.4 2.26 5.403 5.403 0 01-3.14-9.8c-.44-.06-.9-.1-1.36-.1z",
  gear: "M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58a.49.49 0 00.12-.61l-1.92-3.32a.488.488 0 00-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54a.484.484 0 00-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.09.63-.09.94s.02.64.07.94l-2.03 1.58a.49.49 0 00-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z",
  chart: "M5 9.2h3V19H5zM10.6 5h2.8v14h-2.8zm5.6 8H19v6h-2.8z"
});

const COUNTRIES = [
  ["us", "United States"],
  ["in", "India"],
  ["gb", "United Kingdom"],
  ["ca", "Canada"],
  ["au", "Australia"],
  ["de", "Germany"],
  ["fr", "France"],
  ["es", "Spain"],
  ["it", "Italy"],
  ["jp", "Japan"],
  ["kr", "South Korea"],
  ["br", "Brazil"],
  ["mx", "Mexico"],
  ["ae", "United Arab Emirates"],
  ["sg", "Singapore"]
];

const settings = Object.assign({ hideExplicit: false }, loadData("settings", {}));

function saveSettings() {
  saveData("settings", settings);
}

function countryName(code) {
  for (let i = 0; i < COUNTRIES.length; i++) {
    if (COUNTRIES[i][0] === code) return COUNTRIES[i][1];
  }
  return code.toUpperCase();
}

function setCountry(code) {
  COUNTRY = code;
  CC = "&country=" + code;
  saveData("country", code);
  toast("Store set to " + countryName(code));
  router();
}

/* ---------------------------------------------------------------------
   Settings window
   --------------------------------------------------------------------- */

function openSettings() {
  let options = "";
  COUNTRIES.forEach(c => {
    options += '<option value="' + c[0] + '"' + (c[0] === COUNTRY ? " selected" : "") + ">" + esc(c[1]) + "</option>";
  });

  let h = "<h2>Settings</h2>";
  h += '<div class="set-row"><label for="set-country">Store country</label>';
  h += '<select id="set-country" class="select">' + options + "</select></div>";
  h += '<p class="set-help">Changes which songs and charts you see.</p>';
  h += '<div class="set-row"><label for="set-explicit">Hide explicit songs</label>';
  h += '<input type="checkbox" id="set-explicit"' + (settings.hideExplicit ? " checked" : "") + "></div>";
  h += '<div class="set-actions">';
  h += '<button class="pill outline small" data-act="export-library">Export library</button>';
  h += '<button class="pill outline small" data-act="import-library">Import library</button>';
  h += '<button class="pill outline small" data-act="clear-data">Clear all data</button>';
  h += "</div>";
  h += '<input type="file" id="import-file" accept="application/json,.json" class="hidden">';
  h += '<div class="modal-actions"><button class="pill green" data-act="close-modal">Done</button></div>';
  showModal(h);

  $("#set-country").addEventListener("change", event => {
    closeModal();
    setCountry(event.target.value);
  });
  $("#set-explicit").addEventListener("change", event => {
    settings.hideExplicit = event.target.checked;
    saveSettings();
    toast(settings.hideExplicit ? "Explicit songs hidden" : "Explicit songs shown");
    router(true);
  });
  $("#import-file").addEventListener("change", event => {
    importLibrary(event.target.files[0]);
  });
}

/* ---------------------------------------------------------------------
   Export / import / clear
   --------------------------------------------------------------------- */

function exportLibrary() {
  const data = {
    app: "spotify-clone",
    version: 1,
    exportedAt: new Date().toISOString(),
    liked: state.liked,
    playlists: state.playlists,
    following: state.following,
    recent: state.recent
  };
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "spotify-clone-library.json";
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
  toast("Library exported");
}

function importLibrary(file) {
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    try {
      const data = JSON.parse(reader.result);
      let added = 0;

      (data.liked || []).forEach(t => {
        if (t && t.id && !isLiked(t.id)) {
          state.liked.push(t);
          trackStore[t.id] = t;
          added++;
        }
      });

      (data.playlists || []).forEach(p => {
        if (p && p.id && Array.isArray(p.tracks) && !findPlaylist(p.id)) {
          state.playlists.push(p);
          p.tracks.forEach(t => { trackStore[t.id] = t; });
          added++;
        }
      });

      (data.following || []).forEach(a => {
        if (a && a.id && !isFollowing(a.id)) {
          state.following.push(a);
          added++;
        }
      });

      saveData("liked", state.liked);
      saveData("playlists", state.playlists);
      saveData("following", state.following);
      renderSidebar();
      closeModal();
      toast("Imported " + added + " items");
      router(true);
    } catch (err) {
      toast("That file could not be read");
    }
  };
  reader.readAsText(file);
}

function confirmClearData() {
  let h = "<h2>Clear all data?</h2>";
  h += "<p style='color:#b3b3b3'>This removes your liked songs, playlists, followed artists and history from this browser. It cannot be undone.</p>";
  h += '<div class="modal-actions"><button class="pill ghost" data-act="close-modal">Cancel</button>';
  h += '<button class="pill green" data-act="confirm-clear">Clear everything</button></div>';
  showModal(h);
}

function clearAllData() {
  state.liked = [];
  state.playlists = [];
  state.following = [];
  state.recent = [];
  ["liked", "playlists", "following", "recent", "last", "searches"].forEach(key => {
    try { localStorage.removeItem("sp_" + key); } catch (e) {}
  });
  renderSidebar();
  closeModal();
  toast("All data cleared");
  router();
}

/* ---------------------------------------------------------------------
   Sleep timer
   --------------------------------------------------------------------- */

const sleep = { timer: null, endsAt: 0, endOfTrack: false };

function sleepActive() {
  return !!sleep.timer || sleep.endOfTrack;
}

function updateSleepButton() {
  const btn = $("#btn-sleep");
  if (!btn) return;
  btn.classList.toggle("on", sleepActive());
  btn.title = sleepActive() ? "Sleep timer is on" : "Sleep timer";
}

function cancelSleep(silent) {
  clearTimeout(sleep.timer);
  sleep.timer = null;
  sleep.endsAt = 0;
  sleep.endOfTrack = false;
  updateSleepButton();
  if (!silent) toast("Sleep timer off");
}

function startSleep(minutes) {
  cancelSleep(true);
  sleep.endsAt = Date.now() + minutes * 60000;
  sleep.timer = setTimeout(() => {
    audio.pause();
    cancelSleep(true);
    toast("Sleep timer: music paused");
  }, minutes * 60000);
  updateSleepButton();
  toast("Music will pause in " + minutes + " minutes");
}

function startSleepEndOfTrack() {
  cancelSleep(true);
  sleep.endOfTrack = true;
  updateSleepButton();
  toast("Music will pause after this song");
}

function sleepEndOfTrackHit() {
  if (!sleep.endOfTrack) return false;
  cancelSleep(true);
  toast("Sleep timer: music paused");
  return true;
}

function openSleepModal() {
  let h = "<h2>Sleep timer</h2>";
  if (sleep.timer) {
    const left = Math.max(0, Math.round((sleep.endsAt - Date.now()) / 60000));
    h += "<p style='color:#b3b3b3;margin-bottom:12px'>Music will pause in about " + left + " min.</p>";
  } else if (sleep.endOfTrack) {
    h += "<p style='color:#b3b3b3;margin-bottom:12px'>Music will pause after the current song.</p>";
  }
  h += '<div class="sleep-list">';
  [5, 15, 30, 45, 60].forEach(minutes => {
    h += '<button class="pick" data-act="sleep-set" data-min="' + minutes + '"><div>' + minutes + " minutes</div></button>";
  });
  h += '<button class="pick" data-act="sleep-end"><div>End of this song</div></button>';
  if (sleepActive()) h += '<button class="pick" data-act="sleep-off"><div>Turn off timer</div></button>';
  h += "</div>";
  h += '<div class="modal-actions"><button class="pill ghost" data-act="close-modal">Close</button></div>';
  showModal(h);
}

/* ---------------------------------------------------------------------
   Keyboard shortcuts window and extra keys
   --------------------------------------------------------------------- */

function showShortcuts() {
  const rows = [
    ["Space", "Play or pause"],
    ["Shift + Right / Left", "Next / previous song"],
    ["Right / Left", "Skip 5 seconds forward / back"],
    ["Shift + Up / Down", "Volume up / down"],
    ["M", "Mute"],
    ["S", "Shuffle"],
    ["R", "Repeat"],
    ["L", "Like the current song"],
    ["Q", "Open or close the queue"],
    ["/", "Search"],
    ["?", "Show this list"]
  ];
  let h = "<h2>Keyboard shortcuts</h2><table class=\"kbd-table\">";
  rows.forEach(r => {
    h += "<tr><td><kbd>" + esc(r[0]) + "</kbd></td><td>" + esc(r[1]) + "</td></tr>";
  });
  h += '</table><div class="modal-actions"><button class="pill green" data-act="close-modal">Got it</button></div>';
  showModal(h);
}

function seekBy(seconds) {
  if (!audio.duration) return;
  audio.currentTime = Math.max(0, Math.min(audio.duration, audio.currentTime + seconds));
}

document.addEventListener("keydown", event => {
  const tag = event.target.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
  if (event.ctrlKey || event.metaKey || event.altKey) return;

  if (event.key === "?") showShortcuts();
  else if (event.key === "ArrowRight" && !event.shiftKey) seekBy(5);
  else if (event.key === "ArrowLeft" && !event.shiftKey) seekBy(-5);
  else if (event.key === "s") $("#btn-shuffle").click();
  else if (event.key === "r") $("#btn-repeat").click();
  else if (event.key === "q") $("#btn-queue").click();
  else if (event.key === "l") toggleLike(currentTrack());
});

/* ---------------------------------------------------------------------
   Profile menu (the round icon, top right)
   --------------------------------------------------------------------- */

function openProfileMenu(el) {
  const box = el.getBoundingClientRect();
  openMenu(box.right - 230, box.bottom + 8, [
    { label: "Your library", fn: () => { location.hash = "#/library"; } },
    { label: "Your stats", fn: () => { location.hash = "#/stats"; } },
    "-",
    { label: "Sleep timer", fn: openSleepModal },
    { label: "Keyboard shortcuts", fn: showShortcuts },
    { label: "Settings", fn: openSettings }
  ]);
}

/* ---------------------------------------------------------------------
   Search history
   --------------------------------------------------------------------- */

function rememberSearch(term) {
  const clean = String(term || "").trim();
  if (clean.length < 2) return;
  const terms = loadData("searches", []).filter(t => t.toLowerCase() !== clean.toLowerCase());
  terms.unshift(clean);
  if (terms.length > 8) terms.length = 8;
  saveData("searches", terms);
}

function recentSearchesHtml() {
  const terms = loadData("searches", []);
  if (!terms.length) return "";
  let h = '<div class="recent-searches"><h3>Recent searches</h3><div class="chips">';
  terms.forEach(term => {
    h += '<button class="chip" data-act="search-again" data-term="' + esc(term) + '">' + esc(term) + "</button>";
  });
  h += '<button class="chip clear" data-act="clear-searches">Clear</button></div></div>';
  return h;
}

$("#search-input").addEventListener("keydown", event => {
  if (event.key === "Enter") rememberSearch(event.target.value);
});

/* ---------------------------------------------------------------------
   Track menu extras: song info and playlist re-ordering
   --------------------------------------------------------------------- */

function addExtraMenuItems(items, track) {
  if (location.hash.indexOf("#/mine/") === 0) {
    const pid = location.hash.slice(7);
    items.push({ label: "Move up in playlist", fn: () => movePlaylistTrack(pid, track.id, -1) });
    items.push({ label: "Move down in playlist", fn: () => movePlaylistTrack(pid, track.id, 1) });
  }
  items.push({ label: "Song info", fn: () => showSongInfo(track) });
}

function movePlaylistTrack(playlistId, trackId, direction) {
  const playlist = findPlaylist(playlistId);
  if (!playlist) return;
  const from = playlist.tracks.findIndex(t => t.id === trackId);
  const to = from + direction;
  if (from < 0 || to < 0 || to >= playlist.tracks.length) return;
  const moved = playlist.tracks[from];
  playlist.tracks[from] = playlist.tracks[to];
  playlist.tracks[to] = moved;
  saveData("playlists", state.playlists);
  renderSidebar();
  router(true);
}

function showSongInfo(track) {
  const rows = [
    ["Title", track.title],
    ["Artist", track.artist],
    ["Album", track.albumTitle || "Unknown"],
    ["Length", fmtTime(track.duration)],
    ["Playable", track.noPreview ? "No preview available" : "30 second preview"],
    ["Explicit", track.explicit ? "Yes" : "No"]
  ];
  let h = "<h2>Song info</h2><table class=\"info-table\">";
  rows.forEach(r => {
    h += "<tr><td>" + esc(r[0]) + "</td><td>" + esc(r[1]) + "</td></tr>";
  });
  h += '</table><div class="modal-actions"><button class="pill green" data-act="close-modal">Close</button></div>';
  showModal(h);
}

/* ---------------------------------------------------------------------
   "Made for you" shelves on the home page
   Looks at the artists you like and play most, then adds a shelf with
   more songs from them. It loads after the page so Home stays fast.
   --------------------------------------------------------------------- */

async function loadMadeForYou(token) {
  const pool = state.liked.concat(state.recent);
  if (!pool.length) return;

  const counts = {};
  pool.forEach(t => {
    if (!t.artistId) return;
    if (!counts[t.artistId]) counts[t.artistId] = { id: t.artistId, name: t.artist, n: 0 };
    counts[t.artistId].n++;
  });
  const top = Object.keys(counts).map(k => counts[k]).sort((a, b) => b.n - a.n).slice(0, 2);
  if (!top.length) return;

  const sections = [];
  for (let i = 0; i < top.length; i++) {
    const rows = await safeItunes("/lookup?id=" + top[i].id + "&entity=song&limit=20" + CC);
    const tracks = mapTracks(rows);
    if (tracks.length) sections.push({ title: "More from " + top[i].name, tracks: tracks, key: "made-" + top[i].id });
  }

  if (token !== renderToken || !sections.length) return;
  const view = $("#view");
  const footer = view.querySelector(".footer-note");
  if (!footer) return;

  let h = "";
  sections.forEach(s => {
    lists[s.key] = s.tracks;
    h += shelf(s.title, cardsFor(s.tracks, (t, i) => trackCard(t, s.key, i)));
  });
  const holder = document.createElement("div");
  holder.innerHTML = h;
  footer.parentNode.insertBefore(holder, footer);
}

/* ---------------------------------------------------------------------
   Library page (also the way to reach your library on small screens)
   --------------------------------------------------------------------- */

async function viewLibrary() {
  let h = '<div class="page-title">Your Library</div>';
  h += '<div class="page-sub">Everything you have saved in this browser.</div>';
  h += '<div class="actions"><button class="pill green" data-act="new-playlist">Create playlist</button></div>';

  let cards = makeCard({ img: "", title: "Liked Songs", sub: state.liked.length + " songs", link: "#/liked" });
  state.playlists.forEach(p => {
    cards += makeCard({
      img: p.tracks.length ? p.tracks[0].cover : "",
      title: p.name,
      sub: "Playlist • " + p.tracks.length + " songs",
      link: "#/mine/" + p.id
    });
  });
  state.following.forEach(a => {
    cards += makeCard({ img: a.cover, title: a.name, sub: "Artist", link: "#/artist/" + a.id, round: true });
  });

  h += '<div class="grid wrap">' + cards + "</div>";

  if (!state.playlists.length && !state.following.length) {
    h += emptyBox("Nothing here yet", "Like some songs, follow artists and create playlists to fill your library.",
                  '<a class="pill" href="#/search">Find music</a>');
  }
  return { html: h + footerNote(), tracks: [], color: "#1f1f1f" };
}

/* ---------------------------------------------------------------------
   Stats page
   --------------------------------------------------------------------- */

async function viewStats() {
  const seen = {};
  const unique = [];
  state.liked.concat(state.recent).forEach(t => {
    if (!seen[t.id]) {
      seen[t.id] = true;
      unique.push(t);
    }
  });

  const artistCounts = {};
  unique.forEach(t => {
    if (!t.artist) return;
    artistCounts[t.artist] = (artistCounts[t.artist] || 0) + 1;
  });
  const topArtists = Object.keys(artistCounts)
    .map(name => ({ name: name, n: artistCounts[name] }))
    .sort((a, b) => b.n - a.n)
    .slice(0, 8);

  const likedSeconds = state.liked.reduce((sum, t) => sum + (t.duration || 0), 0);

  let h = '<div class="page-title">Your stats</div>';
  h += '<div class="page-sub">Based on what you have liked and played in this browser.</div>';
  h += '<div class="stat-tiles">';
  h += '<div class="stat-tile"><b>' + state.liked.length + "</b><span>Liked songs</span></div>";
  h += '<div class="stat-tile"><b>' + state.playlists.length + "</b><span>Playlists</span></div>";
  h += '<div class="stat-tile"><b>' + state.following.length + "</b><span>Artists followed</span></div>";
  h += '<div class="stat-tile"><b>' + state.recent.length + "</b><span>Recently played</span></div>";
  h += '<div class="stat-tile"><b>' + fmtLong(likedSeconds) + "</b><span>Of liked music</span></div>";
  h += "</div>";

  if (topArtists.length) {
    const max = topArtists[0].n;
    h += '<h2 class="section-title" style="margin-top:32px">Top artists</h2>';
    topArtists.forEach(a => {
      const width = Math.max(6, Math.round((a.n / max) * 100));
      h += '<div class="bar-row"><span class="bar-name">' + esc(a.name) + '</span>';
      h += '<div class="bar-track"><div class="bar-fill" style="width:' + width + '%"></div></div>';
      h += '<span class="bar-n">' + a.n + "</span></div>";
    });
  } else {
    h += emptyBox("No stats yet", "Play and like a few songs and your top artists will show up here.",
                  '<a class="pill" href="#/home">Go home</a>');
  }

  if (state.recent.length) {
    h += '<h2 class="section-title" style="margin-top:32px">Recently played</h2>';
    h += trackTable(state.recent.slice(0, 10), "stats-recent", { album: true, cover: true });
  }
  return { html: h + footerNote(), tracks: state.recent.slice(0, 10), color: "#1e3264" };
}

/* ---------------------------------------------------------------------
   Action handler for everything above
   --------------------------------------------------------------------- */

function handleExtraAction(act, el) {
  switch (act) {
    case "profile":
      openProfileMenu(el);
      return true;
    case "sleep":
      openSleepModal();
      return true;
    case "sleep-set":
      closeModal();
      startSleep(Number(el.dataset.min));
      return true;
    case "sleep-end":
      closeModal();
      startSleepEndOfTrack();
      return true;
    case "sleep-off":
      closeModal();
      cancelSleep(false);
      return true;
    case "export-library":
      exportLibrary();
      return true;
    case "import-library": {
      const input = $("#import-file");
      if (input) input.click();
      return true;
    }
    case "clear-data":
      confirmClearData();
      return true;
    case "confirm-clear":
      clearAllData();
      return true;
    case "search-again":
      location.hash = "#/search/" + encodeURIComponent(el.dataset.term);
      return true;
    case "clear-searches":
      saveData("searches", []);
      router(true);
      return true;
    default:
      return false;
  }
}

/* ---------------------------------------------------------------------
   Small conveniences
   --------------------------------------------------------------------- */

window.addEventListener("offline", () => toast("You are offline"));
window.addEventListener("online", () => toast("Back online"));

// Show the song you were last playing (paused) when you reopen the page.
function restoreLastTrack() {
  const last = loadData("last", null);
  if (!last || !last.preview || currentTrack()) return;
  trackStore[last.id] = last;
  state.queue = [last];
  state.index = 0;
  audio.src = last.preview;
  updateNowPlaying();
  markPlaying();
}

window.addEventListener("load", restoreLastTrack);


function start() {
  $$("[data-icon]").forEach(el => { el.innerHTML = icon(el.dataset.icon); });
  $("#btn-shuffle").innerHTML = icon("shuffle");
  $("#btn-prev").innerHTML = icon("prev");
  $("#btn-play").innerHTML = icon("play");
  $("#btn-next").innerHTML = icon("next");
  $("#btn-repeat").innerHTML = icon("repeat");
  $("#btn-queue").innerHTML = icon("queue");
  $("#btn-sleep").innerHTML = icon("moon");
  audio.volume = state.volume;
  volumeBar.value = Math.round(state.volume * 100);
  setFill(volumeBar);
  setFill(seekBar);
  updateVolumeIcon();
  updateModeButtons();
  updateNowPlaying();
  updatePlayButton();
  renderSidebar();
  router();
}

start();
"""


if __name__ == "__main__":
    main()
