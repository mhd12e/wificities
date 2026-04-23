"""wificities serve — local development server with mock APIs and hot reload."""
import json
import time
import threading
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import click

from .build import _build_theme_mode, _build_raw_mode, _process_plugins, _dir_size
from .project import enter_project_dir


# In-memory mock data
_guestbook_entries = []
_guestbook_next_id = 1
_visitor_total = 0
_visitor_current = 1

# Hot-reload script injected into HTML responses
HOT_RELOAD_SCRIPT = """
<script>
(function() {
  let lastCheck = Date.now();
  setInterval(function() {
    fetch('/__wificities_reload?t=' + lastCheck)
      .then(r => r.json())
      .then(d => { if (d.reload) location.reload(); })
      .catch(() => {});
  }, 1000);
})();
</script>
"""


class DevHandler(SimpleHTTPRequestHandler):
    """HTTP handler that serves the built site + mock APIs."""

    build_dir = None
    _last_build_time = 0

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # Hot reload check
        if path == "/__wificities_reload":
            t = float(parse_qs(parsed.query).get("t", [0])[0])
            reload_needed = self.__class__._last_build_time > t
            self._json_response(200, {"reload": reload_needed})
            return

        # Mock APIs
        if path == "/api/guestbook":
            self._json_response(200, {
                "entries": _guestbook_entries,
                "count": len(_guestbook_entries),
                "max": 100,
            })
            return

        if path == "/api/visitors":
            self._json_response(200, {
                "total": _visitor_total,
                "current": _visitor_current,
            })
            return

        if path == "/api/info":
            build_dir = self.__class__.build_dir
            self._json_response(200, {
                "name": "Dev Server",
                "ssid": "WifiCity-Dev",
                "uptime": int(time.time()),
                "version": "dev",
                "storage": {
                    "total": 2500000,
                    "used": _dir_size(build_dir) if build_dir else 0,
                    "free": 2500000,
                },
            })
            return

        # Serve static files with folder-based routing
        self._serve_file(path)

    def do_POST(self):
        global _guestbook_entries, _guestbook_next_id
        global _visitor_total

        parsed = urlparse(self.path)
        path = parsed.path

        body = self._read_body()

        if path == "/api/guestbook":
            data = json.loads(body) if body else {}
            name = data.get("name", "").strip()[:32]
            message = data.get("message", "").strip()[:256]

            if not name:
                self._json_response(400, {
                    "ok": False, "error": "validation",
                    "message": "name is required"
                })
                return
            if not message:
                self._json_response(400, {
                    "ok": False, "error": "validation",
                    "message": "message is required"
                })
                return

            entry = {
                "id": _guestbook_next_id,
                "name": name,
                "message": message,
                "timestamp": int(time.time()),
            }
            _guestbook_entries.append(entry)
            _guestbook_next_id += 1

            self._json_response(201, {"ok": True, "id": entry["id"]})
            return

        if path == "/api/visitors/reset":
            _visitor_total = 0
            self._json_response(200, {"ok": True})
            return

        self._json_response(404, {"error": "not_found"})

    def do_DELETE(self):
        global _guestbook_entries

        parsed = urlparse(self.path)
        path = parsed.path

        body = self._read_body()

        if path == "/api/guestbook":
            _guestbook_entries = []
            self._json_response(200, {"ok": True})
            return

        # DELETE /api/guestbook/:id
        if path.startswith("/api/guestbook/"):
            try:
                entry_id = int(path.split("/")[-1])
                _guestbook_entries = [e for e in _guestbook_entries
                                      if e["id"] != entry_id]
                self._json_response(200, {"ok": True})
            except ValueError:
                self._json_response(400, {"error": "invalid id"})
            return

        self._json_response(404, {"error": "not_found"})

    def _serve_file(self, url_path: str):
        """Folder-based routing file server."""
        build_dir = self.__class__.build_dir
        if not build_dir:
            self.send_error(500, "No build directory")
            return

        public_dir = build_dir / "public"

        # Normalize
        if url_path.endswith("/") and url_path != "/":
            url_path = url_path.rstrip("/")

        # Try exact file
        if url_path == "/":
            file_path = public_dir / "index.html"
        else:
            rel = url_path.lstrip("/")
            file_path = public_dir / rel

        # Rule 1: Exact file match
        if file_path.is_file():
            self._send_file(file_path)
            return

        # Rule 2: Directory index
        index_path = file_path / "index.html"
        if index_path.is_file():
            self._send_file(index_path)
            return

        # Rule 3: .html fallback
        html_path = file_path.with_suffix(".html")
        if html_path.is_file():
            self._send_file(html_path)
            return

        # 404
        custom_404 = public_dir / "404.html"
        if custom_404.is_file():
            self._send_file(custom_404, status=404)
        else:
            self.send_error(404, "Not Found")

    def _send_file(self, path: Path, status: int = 200):
        """Send a file with appropriate MIME type."""
        mime = self._get_mime(path)
        content = path.read_bytes()

        # Inject hot-reload script into HTML
        if mime == "text/html":
            content = content.replace(
                b"</body>",
                HOT_RELOAD_SCRIPT.encode() + b"</body>"
            )

        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", len(content))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(content)

    def _json_response(self, status: int, data: dict):
        """Send a JSON response."""
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> str:
        """Read the request body."""
        length = int(self.headers.get("Content-Length", 0))
        if length > 0:
            return self.rfile.read(length).decode("utf-8")
        return ""

    @staticmethod
    def _get_mime(path: Path) -> str:
        ext = path.suffix.lower()
        mimes = {
            ".html": "text/html", ".css": "text/css",
            ".js": "application/javascript", ".json": "application/json",
            ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".gif": "image/gif", ".ico": "image/x-icon",
            ".svg": "image/svg+xml", ".woff": "font/woff",
            ".woff2": "font/woff2", ".mp3": "audio/mpeg",
            ".wav": "audio/wav", ".mid": "audio/midi",
            ".txt": "text/plain",
        }
        return mimes.get(ext, "application/octet-stream")

    def log_message(self, format, *args):
        """Suppress default logging, use our own."""
        pass


def _rebuild(project_dir: Path, build_dir: Path):
    """Rebuild the site."""
    import shutil

    config_path = project_dir / "config.json"
    wificities_path = project_dir / "wificities.json"

    if build_dir.exists():
        shutil.rmtree(build_dir)
    build_dir.mkdir()
    (build_dir / "data").mkdir()

    if config_path.exists():
        shutil.copy2(config_path, build_dir / "config.json")

    manifest = None
    if wificities_path.exists():
        manifest = json.loads(wificities_path.read_text(encoding="utf-8"))

    mode = manifest.get("mode", "raw") if manifest else "raw"

    if mode == "theme":
        _build_theme_mode(project_dir, build_dir, manifest)
    else:
        _build_raw_mode(project_dir, build_dir, manifest)

    _process_plugins(project_dir, build_dir, manifest)


@click.command("serve")
@click.option("--port", default=8080, help="Port to serve on")
def serve_cmd(port: int):
    """Run a local dev server with mock APIs and hot reload."""
    global _visitor_total
    _visitor_total = 42  # Mock visitor count

    project_dir = enter_project_dir()
    build_dir = project_dir / "build"

    # Initial build
    click.echo("Building site...")
    _rebuild(project_dir, build_dir)
    DevHandler.build_dir = build_dir
    DevHandler._last_build_time = time.time() * 1000

    # Start file watcher for hot reload
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler

        class RebuildHandler(FileSystemEventHandler):
            def __init__(self):
                self._debounce = 0

            def on_any_event(self, event):
                # Ignore build dir changes and hidden files
                src = event.src_path
                if "build" in src or "/." in src:
                    return

                now = time.time()
                if now - self._debounce < 0.5:
                    return
                self._debounce = now

                click.echo(f"  Change detected, rebuilding...")
                try:
                    _rebuild(project_dir, build_dir)
                    DevHandler._last_build_time = time.time() * 1000
                    click.echo(f"  Rebuilt.")
                except Exception as e:
                    click.echo(f"  Build error: {e}")

        observer = Observer()
        # Watch content, public, config
        for watch_dir in ("content", "public"):
            d = project_dir / watch_dir
            if d.exists():
                observer.schedule(RebuildHandler(), str(d), recursive=True)
        # Watch config files
        observer.schedule(RebuildHandler(), str(project_dir), recursive=False)
        observer.start()
        click.echo("  Hot reload enabled (watching for file changes)")

    except ImportError:
        click.echo("  Hot reload unavailable (watchdog not installed).")

    # Start server
    server = HTTPServer(("0.0.0.0", port), DevHandler)
    click.echo(f"\n\U0001f310 Dev server running at http://localhost:{port}/")
    click.echo(f"   Press Ctrl+C to stop\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        click.echo("\nStopped.")
        server.server_close()
