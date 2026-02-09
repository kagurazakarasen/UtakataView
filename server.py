from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import re
import urllib.parse
import urllib.request


class TankaHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/api/"):
            if self.path.startswith("/api/tanka-page"):
                self._proxy_tanka_page()
                return
            if self.path.startswith("/api/tanka"):
                self._proxy_tanka_list()
                return
            if self.path.startswith("/api/asset"):
                self._proxy_asset()
                return
        super().do_GET()

    def _proxy_tanka_list(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        source = params.get("source", ["popular"])[0]
        url = "https://utakatanka.jp/"
        if source == "new":
            url = "https://utakatanka.jp/tanka"
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                body = response.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        except Exception as exc:
            message = f"Proxy fetch failed: {exc}"
            self.send_response(502)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(message.encode("utf-8"))

    def _proxy_tanka_page(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        path = params.get("path", [""])[0]
        if not path.startswith("/tanka/"):
            self.send_response(400)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Invalid path")
            return

        url = urllib.parse.urljoin("https://utakatanka.jp", path)
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                body = response.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        except Exception as exc:
            message = f"Proxy fetch failed: {exc}"
            self.send_response(502)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(message.encode("utf-8"))

    def _proxy_asset(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        raw_url = params.get("url", [""])[0]
        if not raw_url:
            self.send_response(400)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Missing url")
            return

        parsed_url = urllib.parse.urlparse(raw_url)
        if parsed_url.scheme not in ("http", "https"):
            self.send_response(400)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Invalid url")
            return

        request = urllib.request.Request(
            raw_url,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                body = response.read()
                content_type = response.headers.get("Content-Type", "application/octet-stream")
            if content_type.startswith("text/css"):
                body = self._rewrite_css(body, raw_url)
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        except Exception as exc:
            message = f"Proxy fetch failed: {exc}"
            self.send_response(502)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(message.encode("utf-8"))

    def _rewrite_css(self, body, base_url):
        try:
            text = body.decode("utf-8")
        except UnicodeDecodeError:
            return body

        def replace_url(match):
            raw = match.group(1).strip().strip('"\'')
            if raw.startswith("data:") or raw.startswith("http:") or raw.startswith("https:"):
                absolute = raw
            else:
                absolute = urllib.parse.urljoin(base_url, raw)
            proxied = f"/api/asset?url={urllib.parse.quote(absolute, safe='') }"
            return f"url('{proxied}')"

        rewritten = re.sub(r"url\(([^)]+)\)", replace_url, text)
        return rewritten.encode("utf-8")


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 8000), TankaHandler)
    print("Serving on http://127.0.0.1:8000")
    server.serve_forever()
