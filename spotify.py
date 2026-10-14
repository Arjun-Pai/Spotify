import os
import sys
import time
import json
import threading
import webbrowser
import urllib.request
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn


SITE_NAME = "spotify.local"
FIRST_PORT = 80
BACKUP_PORT = 8080
DEEZER_URL = "https://api.deezer.com"
CACHE_SECONDS = 300


api_cache = {}
image_cache = {}


def get_hosts_file_path():
    if sys.platform.startswith("win"):
        return r"C:\Windows\System32\drivers\etc\hosts"
    return "/etc/hosts"


def hosts_file_already_has_name(text):
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("#"):
            continue
        if SITE_NAME in line:
            return True
    return False


def setup_hosts_file():
    path = get_hosts_file_path()

    try:
        file = open(path, "r")
        text = file.read()
        file.close()
    except Exception:
        return False

    if hosts_file_already_has_name(text):
        return True

    try:
        file = open(path, "a")
        file.write("\n127.0.0.1 " + SITE_NAME + "\n")
        file.write("::1 " + SITE_NAME + "\n")
        file.close()
        print("  Added " + SITE_NAME + " to your hosts file.")
        return True
    except Exception:
        return False


def get_from_deezer(path_and_query):
    now = time.time()

    if path_and_query in api_cache:
        saved = api_cache[path_and_query]
        saved_time = saved["time"]
        if now - saved_time < CACHE_SECONDS:
            return saved["data"]

    if len(api_cache) > 600:
        api_cache.clear()

    url = DEEZER_URL + path_and_query
    headers = {"User-Agent": "Mozilla/5.0"}
    request = urllib.request.Request(url, headers=headers)
    answer = urllib.request.urlopen(request, timeout=15)
    data = answer.read()

    api_cache[path_and_query] = {"time": now, "data": data}
    return data


def get_picture(url):
    host = urllib.parse.urlparse(url).hostname
    if host is None:
        return None

    if not (host.endswith("dzcdn.net") or host.endswith("deezer.com")):
        return None

    if url in image_cache:
        return image_cache[url]

    if len(image_cache) > 300:
        image_cache.clear()

    headers = {"User-Agent": "Mozilla/5.0"}
    request = urllib.request.Request(url, headers=headers)
    answer = urllib.request.urlopen(request, timeout=15)
    data = answer.read()
    kind = answer.headers.get("Content-Type", "image/jpeg")

    result = {"data": data, "kind": kind}
    image_cache[url] = result
    return result


class MyHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def send_answer(self, code, kind, body):
        try:
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        except Exception:
            pass

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
        elif path.startswith("/api/"):
            deezer_path = path[4:]
            try:
                data = get_from_deezer(deezer_path)
                self.send_answer(200, "application/json", data)
            except Exception as error:
                message = json.dumps({"error": "Could not reach Deezer: " + str(error)})
                self.send_answer(502, "application/json", message.encode("utf-8"))
        elif path.startswith("/img?"):
            query = urllib.parse.urlparse(path).query
            options = urllib.parse.parse_qs(query)
            if "u" not in options:
                self.send_answer(400, "text/plain", b"missing picture address")
                return
            try:
                picture = get_picture(options["u"][0])
                if picture is None:
                    self.send_answer(403, "text/plain", b"not allowed")
                else:
                    self.send_answer(200, picture["kind"], picture["data"])
            except Exception:
                self.send_answer(502, "text/plain", b"picture failed")
        else:
            self.send_answer(404, "text/plain", b"Not found")


class MyServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


def make_server():
    try:
        server = MyServer(("127.0.0.1", FIRST_PORT), MyHandler)
        return server, FIRST_PORT
    except Exception:
        pass

    try:
        server = MyServer(("127.0.0.1", BACKUP_PORT), MyHandler)
        return server, BACKUP_PORT
    except Exception:
        return None, 0


def main():
    print("")
    print("  ==============================")
    print("    SPOTIFY CLONE  (Deezer)")
    print("  ==============================")
    print("")

    name_works = setup_hosts_file()

    server, port = make_server()
    if server is None:
        print("  Could not start. Ports 80 and 8080 are both busy.")
        print("  Close other programs and try again.")
        return

    if name_works:
        address = "http://" + SITE_NAME
        if port != 80:
            address = address + ":" + str(port)
    else:
        address = "http://localhost:" + str(port)
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

    timer = threading.Timer(0.5, webbrowser.open, [address])
    timer.start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("")
        print("  Goodbye!")
        server.server_close()


FAVICON = r"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><circle cx="16" cy="16" r="16" fill="#1ed760"/><path d="M18 7v11.2a3.6 3.6 0 1 0 2 3.2V11h4V7z" fill="#000"/></svg>"""

PAGE_CSS = r"""
:root {
  --bg: #000000;
  --panel: #121212;
  --card: #181818;
  --card-hover: #282828;
  --elevated: #1f1f1f;
  --text: #ffffff;
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
  font-family: "Circular Std", "Circular", "Inter", "Segoe UI", "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-size: 14px;
  overflow: hidden;
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

ul {
  list-style: none;
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
#queue::-webkit-scrollbar,
.modal::-webkit-scrollbar {
  width: 12px;
}

#main::-webkit-scrollbar-thumb,
.lib-list::-webkit-scrollbar-thumb,
#queue::-webkit-scrollbar-thumb,
.modal::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.28);
  border: 3px solid transparent;
  background-clip: padding-box;
  border-radius: 6px;
}

#main::-webkit-scrollbar-thumb:hover,
.lib-list::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.45);
  background-clip: padding-box;
}

#app {
  display: grid;
  height: 100vh;
  padding: 8px;
  gap: 8px;
  grid-template-columns: var(--side-w) 1fr;
  grid-template-rows: minmax(0, 1fr) auto;
  grid-template-areas:
    "side main"
    "player player";
}

#app.queue-open {
  grid-template-columns: var(--side-w) 1fr 330px;
  grid-template-areas:
    "side main queue"
    "player player player";
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
  transition: background 0.2s, color 0.2s, transform 0.1s;
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
  transition: background 0.2s;
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
  font-size: 14px;
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
  font-size: 14px;
  margin-bottom: 20px;
}

.pill {
  display: inline-block;
  padding: 8px 32px;
  border-radius: 500px;
  background: #fff;
  color: #000;
  font-weight: 700;
  font-size: 14px;
  transition: transform 0.1s, background 0.2s;
}

.pill:hover {
  transform: scale(1.04);
  background: #f0f0f0;
}

.pill.small {
  padding: 6px 16px;
  font-size: 14px;
}

.pill.ghost {
  background: transparent;
  color: #fff;
}

.pill.ghost:hover {
  background: transparent;
}

.pill.outline {
  background: transparent;
  color: #fff;
  border: 1px solid #7c7c7c;
  padding: 7px 16px;
}

.pill.outline:hover {
  border-color: #fff;
  background: transparent;
}

.pill.green {
  background: var(--green);
}

.pill.green:hover {
  background: var(--green-hover);
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
}

#main.flush #bg {
  opacity: 0;
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
  transition: background 0.2s;
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

.search-box button:hover {
  color: #fff;
}

.avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #1f1f1f;
  border: 4px solid #1f1f1f;
  box-sizing: content-box;
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
  font-weight: 700;
}

.avatar svg {
  width: 20px;
  height: 20px;
  fill: #fff;
}

#view {
  position: relative;
  z-index: 1;
  padding: calc(var(--topbar-h) + 0px) 24px 32px;
  min-height: 100%;
}

#view.flush {
  padding-top: 0;
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
  padding: 100px 20px;
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
  transition: background 0.3s;
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

.quick span.q-name {
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
  font-size: 14px;
  font-weight: 700;
  padding-bottom: 2px;
}

.shelf-more:hover {
  text-decoration: underline;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(176px, 1fr));
  grid-template-rows: auto;
  grid-auto-rows: 0;
  overflow: hidden;
  margin: 0 -6px;
  padding: 0;
}

.grid.wrap {
  grid-auto-rows: auto;
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

.grid > .card {
  margin: 6px;
}

.card-img-wrap {
  position: relative;
  margin-bottom: 16px;
}

.card-img {
  width: 100%;
  aspect-ratio: 1 / 1;
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
  font-size: 14px;
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
  transition: opacity 0.3s, transform 0.3s, background 0.2s;
}

.card:hover .card-play,
.quick:hover .card-play,
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
  font-size: 14px;
  font-weight: 700;
}

.entity-title {
  margin: 8px 0 12px;
  font-size: 96px;
  font-weight: 900;
  letter-spacing: -0.04em;
  line-height: 1.05;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.entity-title.mid {
  font-size: 64px;
}

.entity-title.small {
  font-size: 40px;
}

.entity-desc {
  color: var(--muted);
  font-size: 14px;
  margin-bottom: 8px;
  max-width: 640px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.entity-meta {
  font-size: 14px;
  color: #e6e6e6;
  line-height: 1.5;
}

.entity-meta a.bold,
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

.artist-banner {
  position: relative;
  height: 340px;
  margin: 0 -24px;
  display: flex;
  align-items: flex-end;
  padding: 24px;
  background-color: #333;
  background-size: cover;
  background-position: center 25%;
}

.artist-banner::after {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, rgba(0, 0, 0, 0.15) 0%, rgba(18, 18, 18, 0.95) 100%);
}

.artist-banner > div {
  position: relative;
  z-index: 1;
}

.verified {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 500;
}

.verified i {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #3d91f4;
  display: flex;
  align-items: center;
  justify-content: center;
}

.verified svg {
  width: 14px;
  height: 14px;
  fill: #fff;
}

.artist-name {
  font-size: 96px;
  font-weight: 900;
  letter-spacing: -0.04em;
  line-height: 1.05;
  margin: 4px 0 8px;
  text-shadow: 0 2px 16px rgba(0, 0, 0, 0.4);
}

.artist-name.mid {
  font-size: 64px;
}

.artist-fans {
  font-size: 16px;
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
  transition: transform 0.1s, background 0.2s;
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
  transition: color 0.2s, transform 0.1s;
}

.act-btn:hover {
  color: #fff;
  transform: scale(1.06);
}

.act-btn svg {
  width: 32px;
  height: 32px;
  fill: currentColor;
}

.act-btn.on {
  color: var(--green);
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
  font-size: 14px;
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
  position: relative;
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
  font-size: 14px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.t-row:hover .t-artist {
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
  font-size: 14px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.t-row:hover .t-album {
  color: #fff;
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
  font-size: 14px;
  font-variant-numeric: tabular-nums;
}

.tracks.collapsed .t-row:nth-child(n + 6) {
  display: none;
}

.see-more {
  margin: 8px 0 0 16px;
  color: var(--muted);
  font-weight: 700;
  font-size: 14px;
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
  font-size: 14px;
  transition: background 0.2s;
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
  aspect-ratio: 1 / 1;
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

.genre-card span {
  position: relative;
  z-index: 1;
  word-break: break-word;
}

.genre-card img {
  position: absolute;
  right: -16px;
  bottom: -6px;
  width: 45%;
  aspect-ratio: 1 / 1;
  object-fit: cover;
  border-radius: 4px;
  transform: rotate(25deg);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
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
  transition: background 0.3s;
}

.top-card:hover {
  background: var(--card-hover);
}

.top-card img {
  width: 100px;
  height: 100px;
  margin-bottom: 20px;
  border-radius: 4px;
  object-fit: cover;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
}

.top-card.round img {
  border-radius: 50%;
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
  font-size: 14px;
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

.top-card:hover .card-play {
  opacity: 1;
  transform: none;
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
  font-size: 14px;
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
  transition: color 0.2s, transform 0.1s;
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

.ctrl.on:hover {
  color: var(--green-hover);
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
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #fff;
  color: #000;
}

.ctrl.play-main:hover {
  transform: scale(1.06);
  color: #000;
}

.ctrl.play-main svg {
  width: 18px;
  height: 18px;
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
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.5);
}

input[type="range"].bar:hover::-webkit-slider-thumb,
input[type="range"].bar:focus-visible::-webkit-slider-thumb {
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
  font-size: 14px;
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
  box-shadow: 0 16px 24px rgba(0, 0, 0, 0.3), 0 6px 8px rgba(0, 0, 0, 0.2);
}

.menu-item {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 12px;
  border-radius: 2px;
  font-size: 14px;
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
  box-shadow: 0 16px 24px rgba(0, 0, 0, 0.5);
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
  .lib-promo {
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

  .lib-title {
    display: none;
  }

  .lib-item {
    justify-content: center;
  }

  .lib-text {
    display: none;
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
    grid-template-areas:
      "main"
      "player";
  }

  #sidebar {
    display: none;
  }

  #queue {
    display: none !important;
  }

  #player {
    grid-template-columns: 1fr auto;
    height: 64px;
  }

  .right-ctrl,
  .time {
    display: none;
  }

  .controls {
    width: auto;
  }

  .progress-row {
    display: none;
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

  .entity-title,
  .artist-name {
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

@media (prefers-reduced-motion: reduce) {
  * {
    animation: none !important;
    transition: none !important;
  }
}
"""


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
        <a class="nav-item" id="nav-home" href="#/home">
          <span data-icon="home"></span>
          <span class="lbl">Home</span>
        </a>
        <a class="nav-item" id="nav-search" href="#/search">
          <span data-icon="search"></span>
          <span class="lbl">Search</span>
        </a>
      </nav>

      <section class="panel lib-panel">
        <div class="lib-head">
          <div class="lib-title">
            <span data-icon="library"></span>
            <span class="lbl">Your Library</span>
          </div>
          <button class="icon-btn lbl" data-act="new-playlist" title="Create playlist" aria-label="Create playlist">
            <span data-icon="plus"></span>
          </button>
        </div>
        <div class="lib-list" id="lib-list"></div>
      </section>
    </aside>

    <main id="main">
      <div id="bg"></div>

      <div id="topbar">
        <div class="top-left">
          <button class="circle-btn" data-act="nav-back" title="Go back" aria-label="Go back">
            <span data-icon="chevL"></span>
          </button>
          <button class="circle-btn" data-act="nav-forward" title="Go forward" aria-label="Go forward">
            <span data-icon="chevR"></span>
          </button>

          <div class="search-box hidden" id="search-box">
            <span data-icon="search"></span>
            <input id="search-input" type="text" placeholder="What do you want to play?" autocomplete="off" spellcheck="false">
            <button id="search-clear" class="hidden" data-act="clear-search" aria-label="Clear search">
              <span data-icon="close"></span>
            </button>
          </div>
        </div>

        <div class="top-right">
          <button class="pill small" data-act="premium">Explore Premium</button>
          <button class="avatar" aria-label="Profile" data-act="profile">
            <span><span data-icon="person"></span></span>
          </button>
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


PAGE_JS = r"""
"use strict";

/* ==========================================================
   FRONT END  -  runs inside your browser
   The python server only passes our questions on to Deezer.
   ========================================================== */

const $ = (sel, parent) => (parent || document).querySelector(sel);
const $$ = (sel, parent) => Array.from((parent || document).querySelectorAll(sel));

function esc(text) {
  const map = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  return String(text == null ? "" : text).replace(/[&<>"']/g, c => map[c]);
}

function fmtTime(sec) {
  sec = Math.floor(sec || 0);
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return m + ":" + (s < 10 ? "0" : "") + s;
}

function fmtLong(sec) {
  sec = sec || 0;
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  if (h > 0) return h + " hr " + m + " min";
  return m + " min";
}

function fmtNum(n) {
  return Number(n || 0).toLocaleString("en-US");
}

const PALETTE = [
  "#e8115b", "#8d67ab", "#1e3264", "#e13300", "#477d95", "#ba5d07",
  "#503750", "#dc148c", "#148a08", "#0d73ec", "#e91429", "#608108",
  "#7358ff", "#af2896", "#006450", "#8c1932"
];

function hashNumber(text) {
  let h = 0;
  for (let i = 0; i < text.length; i++) {
    h = (h * 31 + text.charCodeAt(i)) >>> 0;
  }
  return h;
}

function hashColor(text) {
  return "hsl(" + (hashNumber(String(text)) % 360) + ",45%,32%)";
}

const colorCache = {};

function getImageColor(url) {
  if (!url) return Promise.resolve(null);
  if (colorCache[url]) return Promise.resolve(colorCache[url]);

  return new Promise(resolve => {
    const img = new Image();
    img.onload = () => {
      try {
        const size = 12;
        const canvas = document.createElement("canvas");
        canvas.width = size;
        canvas.height = size;
        const ctx = canvas.getContext("2d");
        ctx.drawImage(img, 0, 0, size, size);
        const data = ctx.getImageData(0, 0, size, size).data;

        let r = 0, g = 0, b = 0, total = 0;
        for (let i = 0; i < data.length; i += 4) {
          const max = Math.max(data[i], data[i + 1], data[i + 2]);
          const min = Math.min(data[i], data[i + 1], data[i + 2]);
          const weight = (max - min) + 20;
          r += data[i] * weight;
          g += data[i + 1] * weight;
          b += data[i + 2] * weight;
          total += weight;
        }
        r /= total;
        g /= total;
        b /= total;

        const light = r * 0.3 + g * 0.59 + b * 0.11;
        if (light > 105) {
          const f = 105 / light;
          r *= f;
          g *= f;
          b *= f;
        }
        const color = "rgb(" + Math.round(r) + "," + Math.round(g) + "," + Math.round(b) + ")";
        colorCache[url] = color;
        resolve(color);
      } catch (err) {
        resolve(null);
      }
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
  person: "M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z",
  check: "M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z",
  trash: "M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"
};

function icon(name) {
  return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="' + ICONS[name] + '"/></svg>';
}

function loadData(key, fallback) {
  try {
    const text = localStorage.getItem("sp_" + key);
    if (text) return JSON.parse(text);
  } catch (err) {

  }
  return fallback;
}

function saveData(key, value) {
  try {
    localStorage.setItem("sp_" + key, JSON.stringify(value));
  } catch (err) {

  }
}

const state = {
  queue: [],
  index: -1,
  past: [],
  shuffle: false,
  repeat: 0,
  volume: loadData("volume", 0.7),
  muted: false,
  failCount: 0,

  liked: loadData("liked", []),
  playlists: loadData("playlists", []),
  following: loadData("following", []),
  recent: loadData("recent", []),

  pageTracks: [],
  search: null,
  searchFilter: "all"
};

const lists = {};
const trackStore = {};

state.liked.forEach(t => { trackStore[t.id] = t; });
state.recent.forEach(t => { trackStore[t.id] = t; });
state.playlists.forEach(p => p.tracks.forEach(t => { trackStore[t.id] = t; }));

async function api(path) {
  const res = await fetch("/api" + path);
  if (!res.ok) throw new Error("Could not reach Deezer");
  const data = await res.json();
  if (data.error) {
    const msg = typeof data.error === "string" ? data.error : (data.error.message || "Deezer error");
    throw new Error(msg);
  }
  return data;
}

async function safeApi(path) {
  try {
    const data = await api(path);
    if (!data.data) data.data = [];
    return data;
  } catch (err) {
    return { data: [] };
  }
}

function cleanTrack(t, album) {
  const alb = t.album || album || {};
  const artist = t.artist || {};
  const track = {
    id: t.id,
    title: t.title_short || t.title || "Unknown",
    artist: artist.name || "",
    artistId: artist.id || 0,
    albumTitle: alb.title || "",
    albumId: alb.id || 0,
    cover: alb.cover_medium || alb.cover_big || alb.cover || "",
    coverSmall: alb.cover_small || alb.cover_medium || alb.cover || "",
    preview: t.preview || "",
    duration: t.duration || 0,
    explicit: !!t.explicit_lyrics
  };
  trackStore[track.id] = track;
  return track;
}

function cleanTracks(list, album) {
  const out = [];
  for (let i = 0; i < list.length; i++) {
    out.push(cleanTrack(list[i], album));
  }
  return out;
}

let toastTimer = null;

function toast(message) {
  const el = $("#toast");
  el.textContent = message;
  el.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), 2400);
}

function isLiked(id) {
  return state.liked.some(t => t.id === id);
}

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
  const playlist = {
    id: "p" + Date.now(),
    name: clean || "My playlist #" + (state.playlists.length + 1),
    tracks: []
  };
  state.playlists.unshift(playlist);
  saveData("playlists", state.playlists);
  renderSidebar();
  return playlist;
}

function findPlaylist(id) {
  for (let i = 0; i < state.playlists.length; i++) {
    if (state.playlists[i].id === id) return state.playlists[i];
  }
  return null;
}

function addToPlaylist(playlistId, track) {
  const playlist = findPlaylist(playlistId);
  if (!playlist || !track) return;
  if (playlist.tracks.some(t => t.id === track.id)) {
    toast("Already in " + playlist.name);
    return;
  }
  playlist.tracks.push(track);
  saveData("playlists", state.playlists);
  renderSidebar();
  toast("Added to " + playlist.name);
}

function removeFromPlaylist(playlistId, trackId) {
  const playlist = findPlaylist(playlistId);
  if (!playlist) return;
  playlist.tracks = playlist.tracks.filter(t => t.id !== trackId);
  saveData("playlists", state.playlists);
  renderSidebar();
  toast("Removed from " + playlist.name);
  router(true);
}

function deletePlaylist(playlistId) {
  state.playlists = state.playlists.filter(p => p.id !== playlistId);
  saveData("playlists", state.playlists);
  renderSidebar();
  toast("Playlist deleted");
  location.hash = "#/home";
}

function isFollowing(id) {
  return state.following.some(a => a.id === id);
}

function toggleFollow(artist) {
  if (isFollowing(artist.id)) {
    state.following = state.following.filter(a => a.id !== artist.id);
  } else {
    state.following.unshift(artist);
  }
  saveData("following", state.following);
  renderSidebar();
}

function addRecent(track) {
  state.recent = state.recent.filter(t => t.id !== track.id);
  state.recent.unshift(track);
  if (state.recent.length > 20) state.recent.length = 20;
  saveData("recent", state.recent);
}

/* ==========================================================
   BUILDING BLOCKS  (small functions that make pieces of HTML)
   ========================================================== */

function artistLink(t) {
  if (!t.artistId) return esc(t.artist);
  return '<a href="#/artist/' + t.artistId + '">' + esc(t.artist) + '</a>';
}

function makeCard(o) {
  let h = '<div class="card' + (o.round ? " round" : "") + '"';
  if (o.link) h += ' data-link="' + o.link + '"';
  if (o.attrs) h += " " + o.attrs;
  h += ">";
  h += '<div class="card-img-wrap"><div class="card-img">';
  if (o.img) {
    h += '<img src="' + esc(o.img) + '" loading="lazy" alt="">';
  } else {
    h += icon("music");
  }
  h += "</div>";
  if (o.play) {
    h += '<button class="card-play" data-act="play-card" data-kind="' + o.play.kind +
         '" data-id="' + o.play.id + '" aria-label="Play">' + icon("play") + "</button>";
  } else {
    h += '<button class="card-play" aria-label="Play">' + icon("play") + "</button>";
  }
  h += "</div>";
  h += '<div class="card-title">' + esc(o.title) + "</div>";
  h += '<div class="card-sub">' + esc(o.sub || "") + "</div>";
  h += "</div>";
  return h;
}

function albumCard(a) {
  let sub = "Album";
  const year = a.release_date ? a.release_date.slice(0, 4) : "";
  const who = a.artist ? a.artist.name : "";
  if (year && who) sub = year + " \u2022 " + who;
  else if (who) sub = who;
  else if (year) sub = year;
  return makeCard({
    img: a.cover_medium || a.cover_big || a.cover,
    title: a.title,
    sub: sub,
    link: "#/album/" + a.id,
    play: { kind: "album", id: a.id }
  });
}

function artistCard(a) {
  return makeCard({
    img: a.picture_medium || a.picture_big || a.picture,
    title: a.name,
    sub: "Artist",
    link: "#/artist/" + a.id,
    round: true,
    play: { kind: "artist", id: a.id }
  });
}

function playlistCard(p) {
  let sub = "Playlist";
  const owner = p.user ? p.user.name : (p.creator ? p.creator.name : "");
  if (owner) sub = "By " + owner;
  else if (p.nb_tracks) sub = p.nb_tracks + " songs";
  return makeCard({
    img: p.picture_medium || p.picture_big || p.picture,
    title: p.title,
    sub: sub,
    link: "#/playlist/" + p.id,
    play: { kind: "playlist", id: p.id }
  });
}

function trackCard(t, listName, i) {
  return makeCard({
    img: t.cover,
    title: t.title,
    sub: t.artist,
    attrs: 'data-act="play-track" data-list="' + listName + '" data-i="' + i + '"'
  });
}

function cardsFor(items, builder) {
  let h = "";
  for (let i = 0; i < items.length; i++) {
    h += builder(items[i], i);
  }
  return h;
}

function shelf(title, cardsHtml) {
  if (!cardsHtml) return "";
  let h = '<section class="shelf"><div class="shelf-head">';
  h += '<h2 class="shelf-title">' + esc(title) + "</h2>";
  h += '<button class="shelf-more" data-act="expand-shelf">Show all</button>';
  h += '</div><div class="grid">' + cardsHtml + "</div></section>";
  return h;
}

function tableHead(withAlbum) {
  let h = '<div class="t-head"><div class="t-num-h">#</div><div>Title</div>';
  if (withAlbum) h += '<div class="album-h">Album</div>';
  h += '<div></div><div class="t-time-h">' + icon("clock") + "</div><div></div></div>";
  return h;
}

function trackRow(t, i, listName, opts) {
  const liked = isLiked(t.id);
  let cls = "t-row";
  if (!t.preview) cls += " unavailable";

  let h = '<div class="' + cls + '" data-list="' + listName + '" data-i="' + i + '" data-id="' + t.id + '">';

  h += '<div class="t-num" data-act="play-track">';
  h += '<span class="num-text">' + (i + 1) + "</span>";
  h += '<span class="num-play">' + icon("play") + "</span>";
  h += '<span class="eq"><i></i><i></i><i></i></span></div>';

  h += '<div class="t-main">';
  if (opts.cover) {
    h += '<img src="' + esc(t.coverSmall) + '" loading="lazy" alt="">';
  }
  h += '<div class="t-text"><div class="t-title">' + esc(t.title) + "</div>";
  h += '<div class="t-artist">';
  if (t.explicit) h += '<span class="explicit">E</span>';
  h += artistLink(t) + "</div></div></div>";

  if (opts.album) {
    h += '<div class="t-album"><a href="#/album/' + t.albumId + '">' + esc(t.albumTitle) + "</a></div>";
  }

  h += '<button class="t-heart' + (liked ? " liked" : "") + '" data-act="like" data-id="' + t.id +
       '" aria-label="Like">' + icon(liked ? "heartFill" : "heart") + "</button>";
  h += '<div class="t-time">' + fmtTime(t.duration) + "</div>";
  h += '<button class="t-more" data-act="more" data-id="' + t.id + '" aria-label="More options">' + icon("dots") + "</button>";
  h += "</div>";
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
  for (let i = 0; i < tracks.length; i++) {
    h += trackRow(tracks[i], i, listName, opts);
  }
  h += "</div>";
  return h;
}

function entityHead(o) {
  let size = "";
  if (o.title.length > 40) size = "small";
  else if (o.title.length > 16) size = "mid";

  let h = '<div class="entity-head">';
  h += '<div class="entity-cover ' + (o.coverClass || "") + '">';
  if (o.coverHtml) h += o.coverHtml;
  else if (o.cover) h += '<img src="' + esc(o.cover) + '" alt="">';
  else h += icon("music");
  h += "</div>";
  h += '<div class="entity-info"><div class="entity-type">' + esc(o.type) + "</div>";
  h += '<h1 class="entity-title ' + size + '">' + esc(o.title) + "</h1>";
  if (o.desc) h += '<div class="entity-desc">' + esc(o.desc) + "</div>";
  h += '<div class="entity-meta">' + o.meta + "</div></div></div>";
  return h;
}

function actionBar(extraHtml) {
  let h = '<div class="actions">';
  h += '<button class="big-play" id="page-play" data-act="play-page" aria-label="Play">' + icon("play") + "</button>";
  h += '<button class="act-btn" data-act="shuffle-page" title="Shuffle play" aria-label="Shuffle play">' + icon("shuffle") + "</button>";
  h += extraHtml || "";
  h += "</div>";
  return h;
}

function emptyBox(title, text, buttonHtml) {
  return '<div class="empty"><h2>' + esc(title) + "</h2><p>" + esc(text) + "</p>" + (buttonHtml || "") + "</div>";
}

function footerNote() {
  return '<div class="footer-note">This is a learning project and is not affiliated with any music service. ' +
         "Music data and 30 second previews are provided by the free Deezer API.</div>";
}

function playlistCoverHtml(p) {
  if (!p.tracks.length) return icon("music");
  if (p.tracks.length < 4) return '<img src="' + esc(p.tracks[0].cover) + '" alt="">';
  let h = "";
  for (let i = 0; i < 4; i++) {
    h += '<img src="' + esc(p.tracks[i].cover) + '" alt="">';
  }
  return h;
}

function renderSidebar() {
  let h = "";

  h += '<div class="lib-item" data-link="#/liked">';
  h += '<div class="lib-img liked">' + icon("heartFill") + "</div>";
  h += '<div class="lib-text"><div class="lib-name">Liked Songs</div>';
  h += '<div class="lib-sub">Playlist \u2022 ' + state.liked.length + " songs</div></div></div>";

  state.playlists.forEach(p => {
    const grid = p.tracks.length >= 4 ? " grid4" : "";
    h += '<div class="lib-item" data-link="#/mine/' + p.id + '">';
    h += '<div class="lib-img' + grid + '">' + playlistCoverHtml(p) + "</div>";
    h += '<div class="lib-text"><div class="lib-name">' + esc(p.name) + "</div>";
    h += '<div class="lib-sub">Playlist \u2022 You</div></div></div>';
  });

  state.following.forEach(a => {
    h += '<div class="lib-item" data-link="#/artist/' + a.id + '">';
    h += '<div class="lib-img round">' + (a.picture ? '<img src="' + esc(a.picture) + '" alt="">' : icon("person")) + "</div>";
    h += '<div class="lib-text"><div class="lib-name">' + esc(a.name) + "</div>";
    h += '<div class="lib-sub">Artist</div></div></div>';
  });

  if (!state.playlists.length) {
    h += '<div class="lib-promo"><b>Create your first playlist</b>';
    h += "<p>It's easy, we'll help you</p>";
    h += '<button class="pill small" data-act="new-playlist">Create playlist</button></div>';
  }

  $("#lib-list").innerHTML = h;
  markActiveLinks();
}

function markActiveLinks() {
  $$("#lib-list .lib-item").forEach(el => {
    el.classList.toggle("active", el.dataset.link === location.hash);
  });
}

function refreshHearts() {
  $$(".t-heart").forEach(btn => {
    const liked = isLiked(Number(btn.dataset.id));
    btn.classList.toggle("liked", liked);
    btn.innerHTML = icon(liked ? "heartFill" : "heart");
  });
  updateNowHeart();
}

function closeMenu() {
  $("#menu").style.display = "none";
}

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
    btn.addEventListener("click", e => {
      e.stopPropagation();
      closeMenu();
      item.fn();
    });
    menu.appendChild(btn);
  });

  menu.style.display = "block";

  const w = menu.offsetWidth;
  const h = menu.offsetHeight;
  if (x + w > window.innerWidth - 8) x = window.innerWidth - w - 8;
  if (y + h > window.innerHeight - 8) y = window.innerHeight - h - 8;
  menu.style.left = Math.max(8, x) + "px";
  menu.style.top = Math.max(8, y) + "px";
}

function openTrackMenu(track, x, y) {
  if (!track) return;
  const items = [];
  items.push({ label: "Play next", fn: () => playNext(track) });
  items.push({
    label: isLiked(track.id) ? "Remove from Liked Songs" : "Save to Liked Songs",
    fn: () => toggleLike(track)
  });
  items.push({ label: "Add to playlist", fn: () => showPickPlaylist(track) });

  const hash = location.hash;
  if (hash.indexOf("#/mine/") === 0) {
    const pid = hash.slice(7);
    items.push({ label: "Remove from this playlist", fn: () => removeFromPlaylist(pid, track.id) });
  }

  items.push("-");
  if (track.artistId) items.push({ label: "Go to artist", fn: () => { location.hash = "#/artist/" + track.artistId; } });
  if (track.albumId) items.push({ label: "Go to album", fn: () => { location.hash = "#/album/" + track.albumId; } });
  openMenu(x, y, items);
}

function showModal(html) {
  $("#modal").innerHTML = html;
  $("#modal-back").classList.remove("hidden");
}

function closeModal() {
  $("#modal-back").classList.add("hidden");
  $("#modal").innerHTML = "";
}

function showNameModal(title, startValue, buttonText, onDone) {
  let h = "<h2>" + esc(title) + "</h2>";
  h += '<input class="text" id="modal-input" type="text" maxlength="60" placeholder="Name" value="' + esc(startValue) + '">';
  h += '<div class="modal-actions"><button class="pill ghost" data-act="close-modal">Cancel</button>';
  h += '<button class="pill green" id="modal-ok">' + esc(buttonText) + "</button></div>";
  showModal(h);

  const input = $("#modal-input");
  input.focus();
  input.select();

  function finish() {
    const value = input.value;
    closeModal();
    onDone(value);
  }
  $("#modal-ok").addEventListener("click", finish);
  input.addEventListener("keydown", e => {
    if (e.key === "Enter") finish();
  });
}

function showNewPlaylistModal() {
  showNameModal("Create playlist", "", "Create", name => {
    const p = createPlaylist(name);
    toast("Created " + p.name);
    location.hash = "#/mine/" + p.id;
  });
}

function showPickPlaylist(track) {
  let h = "<h2>Add to playlist</h2>";
  h += '<button class="pick" data-act="pick-new"><div class="lib-img">' + icon("plus") + '</div><div>New playlist</div></button>';
  state.playlists.forEach(p => {
    h += '<button class="pick" data-act="pick-playlist" data-pid="' + p.id + '">';
    h += '<div class="lib-img' + (p.tracks.length >= 4 ? " grid4" : "") + '">' + playlistCoverHtml(p) + "</div>";
    h += "<div>" + esc(p.name) + "</div></button>";
  });
  h += '<div class="modal-actions"><button class="pill ghost" data-act="close-modal">Close</button></div>';
  showModal(h);
  pendingTrack = track;
}

let pendingTrack = null;

/* ==========================================================
   PAGES  (every page is a function that returns some HTML)
   Each one gives back:  { html, tracks, color, coverUrl, flush }
   ========================================================== */

function greeting() {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

async function viewHome() {
  const results = await Promise.all([
    safeApi("/chart/0/tracks?limit=30"),
    safeApi("/chart/0/albums?limit=20"),
    safeApi("/chart/0/artists?limit=20"),
    safeApi("/chart/0/playlists?limit=20"),
    safeApi("/editorial/0/releases?limit=20")
  ]);
  const songs = results[0].data;
  const albums = results[1].data;
  const artists = results[2].data;
  const playlists = results[3].data;
  const releases = results[4].data;

  if (!songs.length && !albums.length && !playlists.length) {
    throw new Error("Could not load music from Deezer. Check your internet connection.");
  }

  const trending = cleanTracks(songs);
  lists["home-trending"] = trending;
  lists["home-recent"] = state.recent;

  let h = '<div class="greeting">' + greeting() + "</div>";

  h += '<div class="quick-grid">';
  h += '<div class="quick" data-link="#/liked"><div class="quick-ph liked">' + icon("heartFill") +
       '</div><span class="q-name">Liked Songs</span></div>';
  let count = 1;

  state.playlists.slice(0, 2).forEach(p => {
    h += '<div class="quick" data-link="#/mine/' + p.id + '">';
    h += '<div class="quick-ph">' + icon("music") + "</div>";
    h += '<span class="q-name">' + esc(p.name) + "</span></div>";
    count++;
  });

  for (let i = 0; i < playlists.length && count < 8; i++) {
    const p = playlists[i];
    h += '<div class="quick" data-link="#/playlist/' + p.id + '">';
    h += '<img src="' + esc(p.picture_medium || p.picture) + '" alt="" loading="lazy">';
    h += '<span class="q-name">' + esc(p.title) + "</span>";
    h += '<button class="card-play" data-act="play-card" data-kind="playlist" data-id="' + p.id +
         '" aria-label="Play">' + icon("play") + "</button></div>";
    count++;
  }
  h += "</div>";

  if (state.recent.length) {
    h += shelf("Recently played", cardsFor(state.recent, (t, i) => trackCard(t, "home-recent", i)));
  }
  h += shelf("Trending songs", cardsFor(trending, (t, i) => trackCard(t, "home-trending", i)));
  h += shelf("Popular albums", cardsFor(albums, albumCard));
  h += shelf("Popular artists", cardsFor(artists, artistCard));
  h += shelf("Featured playlists", cardsFor(playlists, playlistCard));
  h += shelf("New releases", cardsFor(releases, albumCard));
  h += footerNote();

  return { html: h, tracks: [], color: "#2a3b55" };
}

const GENRE_CACHE = { list: null };

async function viewSearch(query) {
  if (!query) return viewBrowse();

  const q = encodeURIComponent(query);
  const results = await Promise.all([
    safeApi("/search?q=" + q + "&limit=30"),
    safeApi("/search/artist?q=" + q + "&limit=12"),
    safeApi("/search/album?q=" + q + "&limit=12"),
    safeApi("/search/playlist?q=" + q + "&limit=12")
  ]);

  state.search = {
    query: query,
    tracks: cleanTracks(results[0].data),
    artists: results[1].data,
    albums: results[2].data,
    playlists: results[3].data
  };
  return renderSearchResults();
}

async function viewBrowse() {
  if (!GENRE_CACHE.list) {
    const data = await safeApi("/genre");
    GENRE_CACHE.list = data.data;
  }
  let h = '<h2 class="section-title" style="margin-top:8px">Browse all</h2><div class="genre-grid">';
  let n = 0;
  GENRE_CACHE.list.forEach(g => {
    if (g.id === 0) return;
    const color = PALETTE[n % PALETTE.length];
    n++;
    h += '<div class="genre-card" style="background:' + color + '" data-link="#/genre/' + g.id + '">';
    h += "<span>" + esc(g.name) + "</span>";
    h += '<img src="' + esc(g.picture_medium || g.picture) + '" alt="" loading="lazy"></div>';
  });
  h += "</div>";
  if (!n) h = emptyBox("Could not load genres", "Check your internet connection and try again.");
  return { html: h + footerNote(), tracks: [], color: "#1f1f1f" };
}

function renderSearchResults() {
  const s = state.search;
  const filter = state.searchFilter;
  const nothing = !s.tracks.length && !s.artists.length && !s.albums.length && !s.playlists.length;

  if (nothing) {
    const text = 'No results found for "' + s.query + '"';
    return {
      html: emptyBox(text, "Please make sure your words are spelled correctly, or use fewer or different keywords."),
      tracks: [],
      color: "#1f1f1f"
    };
  }

  const chips = [
    ["all", "All"], ["songs", "Songs"], ["artists", "Artists"],
    ["albums", "Albums"], ["playlists", "Playlists"]
  ];
  let h = '<div class="chips" style="padding-top:8px">';
  chips.forEach(c => {
    h += '<button class="chip' + (filter === c[0] ? " active" : "") + '" data-act="filter" data-filter="' + c[0] + '">' + c[1] + "</button>";
  });
  h += "</div>";

  if (filter === "all") {
    h += '<div class="top-grid">';
    h += topResult(s);
    h += "<div><h2 class=\"section-title\">Songs</h2>";
    h += trackTable(s.tracks.slice(0, 4), "search-top", { cover: true, head: false });
    h += "</div></div>";
    h += shelf("Artists", cardsFor(s.artists, artistCard));
    h += shelf("Albums", cardsFor(s.albums, albumCard));
    h += shelf("Playlists", cardsFor(s.playlists, playlistCard));
  }

  if (filter === "songs") {
    h += '<div style="margin-top:16px">';
    h += trackTable(s.tracks, "search-songs", { cover: true, album: true });
    h += "</div>";
  }
  if (filter === "artists") h += wrapped(cardsFor(s.artists, artistCard));
  if (filter === "albums") h += wrapped(cardsFor(s.albums, albumCard));
  if (filter === "playlists") h += wrapped(cardsFor(s.playlists, playlistCard));

  return { html: h, tracks: s.tracks, color: "#1f1f1f" };
}

function wrapped(cardsHtml) {
  return '<div class="grid wrap" style="margin-top:16px">' + cardsHtml + "</div>";
}

function topResult(s) {
  let top = null;
  const firstArtist = s.artists[0];
  const firstTrack = s.tracks[0];
  const lower = s.query.toLowerCase();

  if (firstArtist && (!firstTrack || firstArtist.name.toLowerCase() === lower)) {
    top = { kind: "artist", item: firstArtist };
  } else if (firstTrack) {
    top = { kind: "track", item: firstTrack };
  } else if (s.albums[0]) {
    top = { kind: "album", item: s.albums[0] };
  } else {
    return "<div></div>";
  }

  let h = '<div><h2 class="section-title">Top result</h2>';
  if (top.kind === "artist") {
    const a = top.item;
    h += '<div class="top-card round" data-link="#/artist/' + a.id + '">';
    h += '<img src="' + esc(a.picture_medium) + '" alt=""><div class="name">' + esc(a.name) + '</div>';
    h += '<span class="tag">Artist</span>';
    h += '<button class="card-play" data-act="play-card" data-kind="artist" data-id="' + a.id + '" aria-label="Play">' + icon("play") + "</button></div>";
  }
  if (top.kind === "track") {
    const t = top.item;
    h += '<div class="top-card" data-act="play-track" data-list="search-songs" data-i="0">';
    lists["search-songs"] = s.tracks;
    h += '<img src="' + esc(t.cover) + '" alt=""><div class="name">' + esc(t.title) + "</div>";
    h += '<span class="sub">' + esc(t.artist) + '</span><span class="tag">Song</span>';
    h += '<button class="card-play" aria-label="Play">' + icon("play") + "</button></div>";
  }
  if (top.kind === "album") {
    const a = top.item;
    h += '<div class="top-card" data-link="#/album/' + a.id + '">';
    h += '<img src="' + esc(a.cover_medium) + '" alt=""><div class="name">' + esc(a.title) + "</div>";
    h += '<span class="sub">' + esc(a.artist ? a.artist.name : "") + '</span><span class="tag">Album</span>';
    h += '<button class="card-play" data-act="play-card" data-kind="album" data-id="' + a.id + '" aria-label="Play">' + icon("play") + "</button></div>";
  }
  return h + "</div>";
}

async function viewAlbum(id) {
  const a = await api("/album/" + id);
  const tracks = cleanTracks(a.tracks ? a.tracks.data : [], a);

  const kind = a.record_type === "single" ? "Single" : (a.record_type === "ep" ? "EP" : "Album");
  const year = a.release_date ? a.release_date.slice(0, 4) : "";

  let meta = "";
  if (a.artist) {
    meta += '<a class="bold" href="#/artist/' + a.artist.id + '">' + esc(a.artist.name) + "</a> \u2022 ";
  }
  if (year) meta += year + " \u2022 ";
  meta += tracks.length + " songs, <span class=\"dim\">" + fmtLong(a.duration) + "</span>";

  let h = entityHead({ type: kind, title: a.title, cover: a.cover_big || a.cover_medium, meta: meta });
  h += actionBar();
  h += trackTable(tracks, "album", { album: false, cover: false });

  if (a.release_date) {
    const date = new Date(a.release_date).toLocaleDateString("en-US", {
      year: "numeric", month: "long", day: "numeric", timeZone: "UTC"
    });
    h += '<div class="footer-note" style="margin-top:32px;border:none;padding:0">' + date;
    if (a.label) h += "<br>" + esc(a.label);
    h += "</div>";
  }

  if (a.artist) {
    const more = await safeApi("/artist/" + a.artist.id + "/albums?limit=20");
    const others = more.data.filter(x => x.id !== a.id);
    h += shelf("More by " + a.artist.name, cardsFor(others, albumCard));
  }
  h += footerNote();

  return { html: h, tracks: tracks, coverUrl: a.cover_medium, color: hashColor(a.title) };
}

async function viewArtist(id) {
  const [a, top, albums, related] = await Promise.all([
    api("/artist/" + id),
    safeApi("/artist/" + id + "/top?limit=10"),
    safeApi("/artist/" + id + "/albums?limit=50"),
    safeApi("/artist/" + id + "/related?limit=15")
  ]);
  const tracks = cleanTracks(top.data);

  const nameClass = a.name.length > 14 ? "artist-name mid" : "artist-name";
  let h = '<div class="artist-banner" style="background-image:url(' + esc(a.picture_xl || a.picture_big) + ')"><div>';
  h += '<div class="verified"><i>' + icon("check") + "</i>Verified Artist</div>";
  h += '<h1 class="' + nameClass + '">' + esc(a.name) + "</h1>";
  h += '<div class="artist-fans">' + fmtNum(a.nb_fan) + " fans</div></div></div>";

  const following = isFollowing(a.id);
  const followBtn = '<button class="pill outline" id="follow-btn" data-act="follow" data-id="' + a.id +
                    '" data-name="' + esc(a.name) + '" data-pic="' + esc(a.picture_medium) + '">' +
                    (following ? "Following" : "Follow") + "</button>";
  h += actionBar(followBtn);

  if (tracks.length) {
    h += '<h2 class="section-title">Popular</h2>';
    h += trackTable(tracks, "artist-top", { cover: true, head: false, extra: "collapsed" });
    if (tracks.length > 5) {
      h += '<button class="see-more" data-act="see-more">See more</button>';
    }
  }

  const sorted = albums.data.slice().sort((x, y) => String(y.release_date).localeCompare(String(x.release_date)));
  h += shelf("Discography", cardsFor(sorted, albumCard));
  h += shelf("Fans also like", cardsFor(related.data, artistCard));
  h += footerNote();

  return {
    html: h,
    tracks: tracks,
    flush: true,
    color: hashColor(a.name)
  };
}

async function viewPlaylist(id) {
  const p = await api("/playlist/" + id);
  const list = await safeApi("/playlist/" + id + "/tracks?limit=100");
  let source = list.data;
  if (!source.length && p.tracks) source = p.tracks.data;
  const tracks = cleanTracks(source);

  let meta = "";
  if (p.creator) meta += '<span class="bold">' + esc(p.creator.name) + "</span> \u2022 ";
  if (p.fans) meta += fmtNum(p.fans) + " likes \u2022 ";
  meta += (p.nb_tracks || tracks.length) + " songs";
  if (p.duration) meta += ', <span class="dim">' + fmtLong(p.duration) + "</span>";

  let h = entityHead({
    type: "Playlist",
    title: p.title,
    cover: p.picture_big || p.picture_medium,
    desc: p.description,
    meta: meta
  });
  h += actionBar();
  h += trackTable(tracks, "playlist", { album: true, cover: true });
  h += footerNote();

  return { html: h, tracks: tracks, coverUrl: p.picture_medium, color: hashColor(p.title) };
}

async function viewGenre(id) {
  const results = await Promise.all([
    safeApi("/genre"),
    safeApi("/chart/" + id + "/tracks?limit=20"),
    safeApi("/chart/" + id + "/artists?limit=20"),
    safeApi("/chart/" + id + "/albums?limit=20"),
    safeApi("/chart/" + id + "/playlists?limit=20")
  ]);

  let name = "Genre";
  let picture = "";
  results[0].data.forEach(g => {
    if (String(g.id) === String(id)) {
      name = g.name;
      picture = g.picture_medium;
    }
  });

  const tracks = cleanTracks(results[1].data);
  const meta = "Top songs, artists and playlists right now";

  let h = entityHead({ type: "Genre", title: name, cover: picture, meta: meta });
  h += actionBar();
  if (tracks.length) {
    h += '<h2 class="section-title">Top songs</h2>';
    h += trackTable(tracks, "genre", { album: true, cover: true });
  }
  h += shelf("Popular artists", cardsFor(results[2].data, artistCard));
  h += shelf("Popular albums", cardsFor(results[3].data, albumCard));
  h += shelf("Playlists", cardsFor(results[4].data, playlistCard));
  h += footerNote();

  const index = hashNumber(String(id)) % PALETTE.length;
  return { html: h, tracks: tracks, color: PALETTE[index] };
}

async function viewLiked() {
  const tracks = state.liked;
  const meta = '<span class="bold">You</span> \u2022 ' + tracks.length + " songs";

  let h = entityHead({
    type: "Playlist",
    title: "Liked Songs",
    coverHtml: icon("heartFill"),
    coverClass: "liked",
    meta: meta
  });

  if (!tracks.length) {
    h += emptyBox("Songs you like will appear here", "Save songs by tapping the heart icon.",
                  '<a class="pill" href="#/search">Find songs</a>');
    return { html: h, tracks: [], color: "#4a2fc9" };
  }
  h += actionBar();
  h += trackTable(tracks, "liked", { album: true, cover: true });
  h += footerNote();
  return { html: h, tracks: tracks, color: "#4a2fc9" };
}

async function viewMine(id) {
  const p = findPlaylist(id);
  if (!p) {
    return { html: emptyBox("Playlist not found", "It may have been deleted.", '<a class="pill" href="#/home">Go home</a>'), tracks: [], color: "#1f1f1f" };
  }

  const grid = p.tracks.length >= 4 ? "grid4" : "";
  const meta = '<span class="bold">You</span> \u2022 ' + p.tracks.length + " songs";
  let h = entityHead({
    type: "Playlist",
    title: p.name,
    coverHtml: playlistCoverHtml(p),
    coverClass: grid,
    meta: meta
  });

  const buttons =
    '<button class="act-btn" data-act="rename-playlist" data-pid="' + p.id + '" title="Rename" aria-label="Rename">' +
    '<span style="font-size:14px;font-weight:700">Rename</span></button>' +
    '<button class="act-btn" data-act="delete-playlist" data-pid="' + p.id + '" title="Delete" aria-label="Delete playlist">' +
    '<span style="font-size:14px;font-weight:700">Delete</span></button>';
  h += actionBar(buttons);

  if (!p.tracks.length) {
    h += emptyBox("Let's find something for your playlist", "Use the ... menu on any song and choose Add to playlist.",
                  '<a class="pill" href="#/search">Find songs</a>');
  } else {
    h += trackTable(p.tracks, "mine", { album: true, cover: true });
  }
  return { html: h, tracks: p.tracks, color: hashColor(p.name) };
}

function viewError(err) {
  const text = err && err.message ? err.message : "Something went wrong.";
  return {
    html: emptyBox("Something went wrong", text, '<button class="pill" data-act="retry">Try again</button>'),
    tracks: [],
    color: "#1f1f1f"
  };
}

let renderToken = 0;

async function router(soft) {
  renderToken++;
  const myToken = renderToken;

  const hash = location.hash || "#/home";
  const parts = hash.slice(2).split("/");
  const name = parts[0] || "home";
  const arg = decodeURIComponent(parts.slice(1).join("/"));

  updateNav(name, arg);

  const main = $("#main");
  const view = $("#view");
  if (!soft) {
    view.innerHTML = '<div class="spinner"></div>';
    view.classList.remove("flush");
    main.classList.remove("flush");
    main.scrollTop = 0;
    main.style.setProperty("--hue", "#2a3b55");
  }

  let result;
  try {
    if (name === "home") result = await viewHome();
    else if (name === "search") result = await viewSearch(arg);
    else if (name === "album") result = await viewAlbum(arg);
    else if (name === "artist") result = await viewArtist(arg);
    else if (name === "playlist") result = await viewPlaylist(arg);
    else if (name === "genre") result = await viewGenre(arg);
    else if (name === "liked") result = await viewLiked();
    else if (name === "mine") result = await viewMine(arg);
    else result = await viewHome();
  } catch (err) {
    result = viewError(err);
  }

  if (myToken !== renderToken) return;

  const scroll = main.scrollTop;
  view.innerHTML = result.html;
  if (soft) main.scrollTop = scroll;

  view.classList.toggle("flush", !!result.flush);
  main.classList.toggle("flush", !!result.flush);
  main.style.setProperty("--hue", result.color || "#2a3b55");
  state.pageTracks = result.tracks || [];

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

  const box = $("#search-box");
  box.classList.toggle("hidden", name !== "search");
  const input = $("#search-input");
  if (name === "search" && document.activeElement !== input) {
    input.value = arg;
  }
  $("#search-clear").classList.toggle("hidden", !input.value);
  markActiveLinks();
}

function updateTopbar() {
  const top = $("#main").scrollTop;
  const alpha = Math.min(top / 200, 1);
  $("#topbar").style.setProperty("--a", alpha);
}

/* ==========================================================
   THE PLAYER
   ========================================================== */

const audio = $("#audio");

function currentTrack() {
  return state.queue[state.index] || null;
}

function playList(tracks, startTrack, forceShuffle) {
  const playable = tracks.filter(t => t.preview);
  if (!playable.length) {
    toast("No previews available here");
    return;
  }

  if (startTrack && !startTrack.preview) {
    toast("No preview available for this song");
    return;
  }

  if (forceShuffle) {
    state.shuffle = true;
    updateModeButtons();
  }

  state.queue = playable.slice();
  state.past = [];
  state.failCount = 0;

  let start = startTrack ? playable.indexOf(startTrack) : 0;
  if (start < 0) start = 0;
  if (!startTrack && state.shuffle) {
    start = Math.floor(Math.random() * playable.length);
  }
  state.index = start;
  startCurrent();
}

function startCurrent() {
  const track = currentTrack();
  if (!track) return;
  track.retried = false;
  audio.src = track.preview;
  audio.play().catch(() => {});
  addRecent(track);
  updateNowPlaying();
  markPlaying();
  updatePageButton();
  renderQueue();
}

function togglePlay() {
  if (!currentTrack()) {
    toast("Pick a song to play");
    return;
  }
  if (audio.paused) audio.play().catch(() => {});
  else audio.pause();
}

function nextTrack(auto) {
  if (!state.queue.length) return;

  if (auto && state.repeat === 2) {
    audio.currentTime = 0;
    audio.play().catch(() => {});
    return;
  }

  let next = state.index;
  if (state.shuffle && state.queue.length > 1) {
    while (next === state.index) {
      next = Math.floor(Math.random() * state.queue.length);
    }
  } else {
    next = state.index + 1;
    if (next >= state.queue.length) {
      if (state.repeat === 1 || !auto) {
        next = 0;
      } else {

        audio.pause();
        audio.currentTime = 0;
        return;
      }
    }
  }

  state.past.push(state.index);
  state.index = next;
  startCurrent();
}

function prevTrack() {
  if (!state.queue.length) return;

  if (audio.currentTime > 3) {
    audio.currentTime = 0;
    return;
  }

  if (state.past.length) {
    state.index = state.past.pop();
  } else if (state.index > 0) {
    state.index = state.index - 1;
  } else {
    audio.currentTime = 0;
    return;
  }
  startCurrent();
}

function playNext(track) {
  if (!track.preview) {
    toast("No preview available for this song");
    return;
  }
  if (!currentTrack()) {
    playList([track], track);
    return;
  }
  state.queue.splice(state.index + 1, 0, track);
  toast("Added to queue");
  renderQueue();
}

async function playCollection(kind, id) {
  try {
    let tracks = [];
    if (kind === "album") {
      const a = await api("/album/" + id);
      tracks = cleanTracks(a.tracks.data, a);
    } else if (kind === "playlist") {
      const r = await api("/playlist/" + id + "/tracks?limit=100");
      tracks = cleanTracks(r.data);
    } else if (kind === "artist") {
      const r = await api("/artist/" + id + "/top?limit=50");
      tracks = cleanTracks(r.data);
    }
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
    $("#np-title").innerHTML = "";
    $("#np-artist").innerHTML = "";
    $("#np-heart").classList.add("hidden");
    return;
  }
  cover.innerHTML = t.cover ? '<img src="' + esc(t.cover) + '" alt="">' : icon("music");
  $("#np-title").innerHTML = '<a href="#/album/' + t.albumId + '">' + esc(t.title) + "</a>";
  $("#np-artist").innerHTML = artistLink(t);
  $("#np-heart").classList.remove("hidden");
  updateNowHeart();
  document.title = t.title + " \u2022 " + t.artist;
  setMediaSession(t);
}

function updateNowHeart() {
  const t = currentTrack();
  const btn = $("#np-heart");
  if (!t) return;
  const liked = isLiked(t.id);
  btn.classList.toggle("liked", liked);
  btn.innerHTML = icon(liked ? "heartFill" : "heart");
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
  const playing = here && !audio.paused;
  btn.innerHTML = icon(playing ? "pause" : "play");
}

function markPlaying() {
  const t = currentTrack();
  $$(".t-row").forEach(row => {
    row.classList.toggle("playing", !!t && Number(row.dataset.id) === t.id);
  });
}

function setFill(input) {
  const min = Number(input.min) || 0;
  const max = Number(input.max) || 100;
  const percent = ((input.value - min) / (max - min)) * 100;
  input.style.setProperty("--fill", percent + "%");
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
      title: t.title,
      artist: t.artist,
      album: t.albumTitle,
      artwork: [{ src: t.cover, sizes: "250x250", type: "image/jpeg" }]
    });
  } catch (err) {

  }
}

function queueItem(t, i, now) {
  let h = '<div class="q-item' + (now ? " now" : "") + '" data-act="queue-jump" data-i="' + i + '">';
  h += '<img src="' + esc(t.coverSmall) + '" alt="">';
  h += '<div class="q-t"><div class="q-title">' + esc(t.title) + '</div>';
  h += '<div class="q-artist">' + esc(t.artist) + "</div></div></div>";
  return h;
}

function renderQueue() {
  if (!$("#app").classList.contains("queue-open")) return;

  let h = '<div class="q-head"><h2>Queue</h2>';
  h += '<button class="icon-btn" data-act="toggle-queue" aria-label="Close queue">' + icon("close") + "</button></div>";

  const now = currentTrack();
  if (!now) {
    h += '<div class="q-empty">Play something and your queue will show up here.</div>';
  } else {
    h += '<div class="q-label">Now playing</div>' + queueItem(now, state.index, true);
    if (state.index + 1 < state.queue.length) {
      h += '<div class="q-label">Next up</div>';
      const last = Math.min(state.queue.length, state.index + 51);
      for (let i = state.index + 1; i < last; i++) {
        h += queueItem(state.queue[i], i, false);
      }
    }
  }
  $("#queue").innerHTML = h;
}

audio.addEventListener("play", updatePlayButton);
audio.addEventListener("pause", updatePlayButton);

audio.addEventListener("playing", () => {
  state.failCount = 0;
  updatePlayButton();
});

audio.addEventListener("loadedmetadata", () => {
  $("#t-dur").textContent = fmtTime(audio.duration);
});

audio.addEventListener("timeupdate", () => {
  const seek = $("#seek");
  if (!audio.duration) return;
  if (seeking) return;
  seek.value = (audio.currentTime / audio.duration) * 1000;
  setFill(seek);
  $("#t-cur").textContent = fmtTime(audio.currentTime);
});

audio.addEventListener("ended", () => {
  nextTrack(true);
});

audio.addEventListener("error", async () => {
  const t = currentTrack();
  if (!t || !audio.src) return;

  if (!t.retried) {
    t.retried = true;
    try {
      const fresh = await api("/track/" + t.id);
      if (fresh.preview) {
        t.preview = fresh.preview;
        audio.src = t.preview;
        audio.play().catch(() => {});
        return;
      }
    } catch (err) {

    }
  }

  state.failCount++;
  toast("Could not play \"" + t.title + "\"");
  if (state.failCount < 4) nextTrack(true);
});

let seeking = false;
const seekBar = $("#seek");

seekBar.addEventListener("input", () => {
  seeking = true;
  setFill(seekBar);
  if (audio.duration) {
    $("#t-cur").textContent = fmtTime((seekBar.value / 1000) * audio.duration);
  }
});

seekBar.addEventListener("change", () => {
  if (audio.duration) {
    audio.currentTime = (seekBar.value / 1000) * audio.duration;
  }
  seeking = false;
});

const volumeBar = $("#volume");

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

function handleAction(el, event) {
  const act = el.dataset.act;

  if (act === "play-track") {
    const source = el.closest("[data-list]");
    if (!source) return;
    const list = lists[source.dataset.list] || [];
    const track = list[Number(source.dataset.i)];
    if (!track) return;
    if (currentTrack() === track) togglePlay();
    else playList(list, track);
    return;
  }

  if (act === "like") {
    toggleLike(trackStore[Number(el.dataset.id)]);
    return;
  }

  if (act === "like-current") {
    toggleLike(currentTrack());
    return;
  }

  if (act === "more") {
    const box = el.getBoundingClientRect();
    openTrackMenu(trackStore[Number(el.dataset.id)], box.left - 190, box.bottom + 4);
    return;
  }

  if (act === "play-card") {
    playCollection(el.dataset.kind, el.dataset.id);
    return;
  }

  if (act === "play-page") {
    const t = currentTrack();
    const here = t && state.pageTracks.indexOf(t) >= 0;
    if (here) togglePlay();
    else playList(state.pageTracks, null);
    return;
  }

  if (act === "shuffle-page") {
    playList(state.pageTracks, null, true);
    return;
  }

  if (act === "toggle-play") togglePlay();
  else if (act === "next") nextTrack(false);
  else if (act === "prev") prevTrack();
  else if (act === "shuffle") {
    state.shuffle = !state.shuffle;
    updateModeButtons();
  } else if (act === "repeat") {
    state.repeat = (state.repeat + 1) % 3;
    updateModeButtons();
  } else if (act === "mute") toggleMute();
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
  else if (act === "clear-search") {
    $("#search-input").value = "";
    $("#search-input").focus();
    goSearch("");
  }

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
    const open = grid.classList.toggle("wrap");
    el.textContent = open ? "Show less" : "Show all";
  } else if (act === "see-more") {
    const box = $(".tracks.collapsed, .tracks.expanded");
    if (box) {
      const collapsed = box.classList.toggle("collapsed");
      box.classList.toggle("expanded", !collapsed);
      el.textContent = collapsed ? "See more" : "Show less";
    }
  } else if (act === "follow") {
    toggleFollow({
      id: Number(el.dataset.id),
      name: el.dataset.name,
      picture: el.dataset.pic
    });
    el.textContent = isFollowing(Number(el.dataset.id)) ? "Following" : "Follow";
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
  } else if (act === "delete-playlist") {
    const p = findPlaylist(el.dataset.pid);
    if (!p) return;
    let h = "<h2>Delete playlist?</h2><p style='color:#b3b3b3'>This will delete " + esc(p.name) + " from your library.</p>";
    h += '<div class="modal-actions"><button class="pill ghost" data-act="close-modal">Cancel</button>';
    h += '<button class="pill green" data-act="confirm-delete" data-pid="' + p.id + '">Delete</button></div>';
    showModal(h);
  } else if (act === "confirm-delete") {
    closeModal();
    deletePlaylist(el.dataset.pid);
  } else if (act === "pick-playlist") {
    closeModal();
    addToPlaylist(el.dataset.pid, pendingTrack);
  } else if (act === "pick-new") {
    const track = pendingTrack;
    closeModal();
    showNameModal("Create playlist", "", "Create", name => {
      const p = createPlaylist(name);
      addToPlaylist(p.id, track);
    });
  } else if (act === "close-modal") closeModal();

  else if (act === "premium") toast("This clone is free forever");
  else if (act === "profile") toast("Signed in as a guest");
}

document.addEventListener("click", event => {

  if (!event.target.closest("#menu")) closeMenu();

  if (event.target.id === "modal-back") {
    closeModal();
    return;
  }

  const actEl = event.target.closest("[data-act]");
  if (actEl) {
    handleAction(actEl, event);
    return;
  }

  const linkEl = event.target.closest("[data-link]");
  if (linkEl && !event.target.closest("a, button")) {
    location.hash = linkEl.dataset.link;
    return;
  }

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
  if (track) playList(list, track);
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

  if (event.key === "Escape") {
    closeMenu();
    closeModal();
  } else if (event.code === "Space") {
    event.preventDefault();
    togglePlay();
  } else if (event.shiftKey && event.key === "ArrowRight") {
    nextTrack(false);
  } else if (event.shiftKey && event.key === "ArrowLeft") {
    prevTrack();
  } else if (event.key === "ArrowUp" && event.shiftKey) {
    volumeBar.value = Math.min(100, Number(volumeBar.value) + 10);
    volumeBar.dispatchEvent(new Event("input"));
  } else if (event.key === "ArrowDown" && event.shiftKey) {
    volumeBar.value = Math.max(0, Number(volumeBar.value) - 10);
    volumeBar.dispatchEvent(new Event("input"));
  } else if (event.key === "m") {
    toggleMute();
  } else if (event.key === "/") {
    event.preventDefault();
    location.hash = "#/search";
    setTimeout(() => $("#search-input").focus(), 50);
  }
});

let searchTimer = null;

function goSearch(text) {
  const clean = text.trim();
  const newHash = clean ? "#/search/" + encodeURIComponent(clean) : "#/search";
  history.replaceState(null, "", newHash);
  router(true);
}

$("#search-input").addEventListener("input", event => {
  const text = event.target.value;
  $("#search-clear").classList.toggle("hidden", !text);
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => goSearch(text), 350);
});

$("#main").addEventListener("scroll", updateTopbar);
window.addEventListener("hashchange", () => router());

if ("mediaSession" in navigator) {
  try {
    navigator.mediaSession.setActionHandler("play", () => audio.play());
    navigator.mediaSession.setActionHandler("pause", () => audio.pause());
    navigator.mediaSession.setActionHandler("nexttrack", () => nextTrack(false));
    navigator.mediaSession.setActionHandler("previoustrack", () => prevTrack());
  } catch (err) {

  }
}

function start() {

  $$("[data-icon]").forEach(el => {
    el.innerHTML = icon(el.dataset.icon);
  });

  $("#btn-shuffle").innerHTML = icon("shuffle");
  $("#btn-prev").innerHTML = icon("prev");
  $("#btn-play").innerHTML = icon("play");
  $("#btn-next").innerHTML = icon("next");
  $("#btn-repeat").innerHTML = icon("repeat");
  $("#btn-queue").innerHTML = icon("queue");

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
