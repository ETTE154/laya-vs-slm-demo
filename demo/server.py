"""Single input, sequential local models, and flushed NDJSON streaming."""
from pathlib import Path
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import socket
import webbrowser
from live_inference import LiveEngines
from shared_task import parse_task

ROOT = Path(__file__).resolve().parent


def make_handler(engine):
    class Handler(BaseHTTPRequestHandler):
        def send_json(self, obj, status=200):
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/api/meta":
                return self.send_json(engine.metadata())
            if self.path not in ("/", "/index.html"):
                return self.send_json({"error": "Not found"}, 404)
            body = (ROOT / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            if self.path != "/api/stream":
                return self.send_json({"error": "Not found"}, 404)
            try:
                origin, host = self.headers.get("Origin"), self.headers.get("Host")
                if origin and origin != "http://" + str(host):
                    return self.send_json({"error": "다른 사이트에서의 요청은 허용하지 않습니다."}, 403)
                if self.headers.get_content_type() != "application/json":
                    return self.send_json({"error": "JSON 요청이 필요합니다."}, 415)
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 16384:
                    raise ValueError("입력이 비어 있거나 너무 깁니다.")
                self.connection.settimeout(30)
                data = json.loads(self.rfile.read(length).decode("utf-8"))
                text = data.get("input") if isinstance(data, dict) else None
                if not isinstance(text, str) or not text.strip():
                    raise ValueError("입력할 내용을 작성해 주세요.")
                if len(text) > 2000:
                    raise ValueError("입력은 2,000자 이내로 작성해 주세요.")
                # Reject missing/malformed candidates before loading any model.
                parse_task(text)
            except (ValueError, UnicodeError, socket.timeout) as exc:
                return self.send_json({"error": str(exc)}, 400)
            if not engine.run_lock.acquire(blocking=False):
                return self.send_json({"error": "현재 추론이 진행 중입니다. 완료 후 다시 실행해 주세요."}, 409)
            try:
                self.send_response(200)
                self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
                self.send_header("Cache-Control", "no-store, no-transform")
                self.send_header("X-Accel-Buffering", "no")
                self.send_header("Connection", "close")
                self.end_headers()
                self.close_connection = True
                self.connection.settimeout(30)

                def emit(event):
                    self.wfile.write((json.dumps(event, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8"))
                    self.wfile.flush()

                engine.run(text, emit)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, socket.timeout):
                # A callback failure unwinds generate on this same thread before unlock.
                print("Client disconnected; current comparison stopped.", flush=True)
            except Exception as exc:
                try:
                    emit({"type": "error", "message": f"{type(exc).__name__}: {exc}"})
                except OSError:
                    pass
            finally:
                engine.run_lock.release()

        def log_message(self, fmt, *args):
            print(fmt % args, flush=True)
    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8776)
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--open", action="store_true")
    args = parser.parse_args()
    engine = LiveEngines(threads=args.threads)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(engine))
    url = f"http://127.0.0.1:{args.port}/"
    print("Local comparison:", url, flush=True)
    print("Models load on first run. Order: Laya -> SLM 1B -> SLM 3B. Ctrl+C to stop.", flush=True)
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
