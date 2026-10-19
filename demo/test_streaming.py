r"""Transport/control-flow tests only: no torch imports or model loading.

Run from the workspace with: demo\.venv\Scripts\python.exe -B demo\test_streaming.py
"""
from contextlib import contextmanager
import http.client
import json
import os
from pathlib import Path
import socket
import struct
import sys
import threading
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from live_inference import LiveEngines, MODEL_ORDER, SharedTaskLimitError
from shared_task import parse_task
from server import make_handler
from http.server import ThreadingHTTPServer

VALID_INPUT = "2+3?\nA. 4\nB. 5\nC. 6"
VALID_BODY = json.dumps({"input": VALID_INPUT}).encode("utf-8")


class FakeEngine:
    def __init__(self, behavior=None):
        self.run_lock = threading.Lock()
        self.calls = []
        self.behavior = behavior

    def metadata(self):
        return {"app": "fake-test-engine"}

    def run(self, text, emit):
        self.calls.append(text)
        if self.behavior:
            return self.behavior(text, emit)
        emit({"type": "run_start", "order": list(MODEL_ORDER)})
        emit({"type": "run_end"})


@contextmanager
def serving(engine):
    class QuietHandler(make_handler(engine)):
        def log_message(self, *args):
            pass

    class TestServer(ThreadingHTTPServer):
        def handle_error(self, request, address):
            self.errors.append(sys.exc_info()[1])

    server = TestServer(("127.0.0.1", 0), QuietHandler)
    server.errors = []
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def request(server, body=VALID_BODY, headers=None):
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
    connection.request("POST", "/api/stream", body=body,
                       headers=headers or {"Content-Type": "application/json"})
    response = connection.getresponse()
    return connection, response


def read_all(server, body=VALID_BODY, headers=None):
    connection, response = request(server, body, headers)
    try:
        return response.status, response.read(), dict(response.getheaders())
    finally:
        response.close()
        connection.close()


class TransportTests(unittest.TestCase):
    def assert_unlocked(self, engine):
        acquired = engine.run_lock.acquire(timeout=3)
        self.assertTrue(acquired, "run lock was not released after the request")
        if acquired:
            engine.run_lock.release()

    def test_validation_precedes_inference(self):
        engine = FakeEngine()
        invalid = [
            (b"not-json", {}),
            (b"[]", {}),
            (b"{}", {}),
            (b'{"input":null}', {}),
            (b'{"input":17}', {}),
            (b'{"input":""}', {}),
            (b'{"input":"2+3?"}', {}),
            (b'{"input":"  \\n  "}', {}),
            (json.dumps({"input": "a" * 2001}).encode(), {}),
            (b'{"input":"\xff"}', {}),
            (b"", {"Content-Length": "0"}),
            (b"", {"Content-Length": "16385"}),
            (b"", {"Content-Length": "invalid"}),
        ]
        with serving(engine) as server:
            for body, extra_headers in invalid:
                with self.subTest(body=body[:50], headers=extra_headers):
                    status, payload, _ = read_all(
                        server, body, {"Content-Type": "application/json", **extra_headers})
                    self.assertEqual(status, 400)
                    self.assertIn("error", json.loads(payload))
            status, payload, _ = read_all(server, b"hello", {"Content-Type": "text/plain"})
            self.assertEqual(status, 415)
            self.assertIn("error", json.loads(payload))
            self.assertEqual(engine.calls, [])
            self.assert_unlocked(engine)
            self.assertEqual(server.errors, [])

    def test_incremental_lines_and_busy_rejection(self):
        gate = threading.Event()
        started = threading.Event()
        completed = threading.Event()

        def behavior(text, emit):
            emit({"type": "run_start", "order": list(MODEL_ORDER)})
            started.set()
            if not gate.wait(timeout=4):
                raise RuntimeError("test did not release the inference gate")
            for key in MODEL_ORDER:
                emit({"type": "model_start", "model": key})
                if key != "laya":
                    emit({"type": "token", "model": key, "text": "한글 답변"})
                emit({"type": "model_result", "model": key})
            emit({"type": "run_end"})
            completed.set()

        engine = FakeEngine(behavior)
        with serving(engine) as server:
            shared_input = "  공통 질문\nA. 첫 답\nB. 둘째 답  "
            connection, response = request(server, json.dumps({"input": shared_input}).encode())
            try:
                self.assertEqual(response.status, 200)
                self.assertTrue(response.getheader("Content-Type").startswith("application/x-ndjson"))
                self.assertIsNone(response.getheader("Content-Length"))
                first = json.loads(response.readline())
                self.assertEqual(first["type"], "run_start")
                self.assertTrue(started.wait(timeout=1))
                self.assertFalse(completed.is_set(), "first line was buffered until completion")
                status, payload, _ = read_all(server)
                self.assertEqual(status, 409)
                self.assertIn("error", json.loads(payload))
                self.assertEqual(len(engine.calls), 1)
                gate.set()
                events = [first] + [json.loads(line) for line in response if line.strip()]
                expected_types = ["run_start", "model_start", "model_result",
                                  "model_start", "token", "model_result",
                                  "model_start", "token", "model_result", "run_end"]
                self.assertEqual([event["type"] for event in events], expected_types)
                self.assertEqual([event["model"] for event in events if event["type"] == "model_start"],
                                 list(MODEL_ORDER))
                self.assertEqual(events[4]["text"], "한글 답변")
                self.assertEqual(engine.calls, [shared_input])
                self.assert_unlocked(engine)
                self.assertEqual(server.errors, [])
            finally:
                gate.set()
                response.close()
                connection.close()

    def test_disconnected_client_unwinds_before_unlock(self):
        gate = threading.Event()
        started = threading.Event()
        unwound = threading.Event()
        fully_completed = threading.Event()

        def behavior(text, emit):
            try:
                emit({"type": "run_start"})
                started.set()
                if not gate.wait(timeout=4):
                    raise RuntimeError("test disconnect gate was not released")
                # A reset client must fail a callback rather than finish the run.
                for _ in range(8):
                    emit({"type": "token", "text": "x" * 262144})
                fully_completed.set()
            finally:
                unwound.set()

        engine = FakeEngine(behavior)
        with serving(engine) as server:
            client = socket.create_connection(("127.0.0.1", server.server_port), timeout=3)
            try:
                body = VALID_BODY
                client.sendall((f"POST /api/stream HTTP/1.0\r\nHost: 127.0.0.1:{server.server_port}\r\n"
                                f"Content-Type: application/json\r\nContent-Length: {len(body)}\r\n\r\n").encode() + body)
                received = b""
                while b'"type": "run_start"' not in received:
                    chunk = client.recv(4096)
                    self.assertTrue(chunk)
                    received += chunk
                self.assertTrue(started.wait(timeout=1))
                linger = struct.pack("hh" if os.name == "nt" else "ii", 1, 0)
                client.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, linger)
                client.close()
                gate.set()
                self.assertTrue(unwound.wait(timeout=3), "generation did not unwind after disconnect")
                self.assertFalse(fully_completed.is_set())
                self.assert_unlocked(engine)
                self.assertEqual(server.errors, [])
            finally:
                gate.set()
                client.close()

    def test_unexpected_engine_exception_releases_lock_for_next_request(self):
        def fail(text, emit):
            emit({"type": "run_start"})
            raise RuntimeError("synthetic engine-level failure")

        engine = FakeEngine(fail)
        with serving(engine) as server:
            status, payload, _ = read_all(server)
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(payload.splitlines()[0])["type"], "run_start")
            self.assert_unlocked(engine)
            engine.behavior = None
            status, payload, _ = read_all(server)
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(payload.splitlines()[-1])["type"], "run_end")
            self.assertEqual(len(engine.calls), 2)


class RunControlFlowTests(unittest.TestCase):
    def test_task_limit_aborts_all_models_instead_of_comparing_truncated_content(self):
        engine = LiveEngines()
        engine.load = Mock(return_value=0)
        engine.classify = Mock(side_effect=SharedTaskLimitError("candidate too long"))
        engine.generate = Mock()
        events = []
        engine.run(VALID_INPUT, events.append)
        self.assertEqual(engine.load.call_count, 1)
        engine.generate.assert_not_called()
        self.assertEqual(events[-1]["type"], "error")
        self.assertNotIn("run_end", [event["type"] for event in events])

    def test_same_input_is_forwarded_sequentially_and_model_error_continues(self):
        engine = LiveEngines()
        text = "  물체를 들어 올려 줘.\nA. 들어 올린다\nB. 기다린다  "
        task = parse_task(text)
        calls, events = [], []

        def load(key, emit):
            calls.append(("load", key))
            return 12.5

        def classify(value, load_ms, emit):
            calls.append(("classify", "laya", value, load_ms))
            emit({"type": "model_result", "model": "laya"})

        def generate(key, value, load_ms, emit):
            calls.append(("generate", key, value, load_ms))
            if key == "llama1b":
                raise ValueError("synthetic per-model failure")
            emit({"type": "model_result", "model": key})

        engine.load, engine.classify, engine.generate = Mock(side_effect=load), Mock(side_effect=classify), Mock(side_effect=generate)
        engine.run(text, events.append)
        self.assertEqual(calls, [("load", "laya"), ("classify", "laya", task, 12.5),
                                 ("load", "llama1b"), ("generate", "llama1b", task, 12.5),
                                 ("load", "llama3b"), ("generate", "llama3b", task, 12.5)])
        self.assertEqual([event["model"] for event in events if event["type"] == "model_start"], list(MODEL_ORDER))
        self.assertEqual([event["model"] for event in events if event["type"] == "model_error"], ["llama1b"])
        self.assertIn("synthetic per-model failure", next(event["message"] for event in events if event["type"] == "model_error"))
        self.assertEqual(events[0]["type"], "run_start")
        self.assertEqual(events[-1]["type"], "run_end")

    def test_callback_disconnect_aborts_remaining_models(self):
        engine = LiveEngines()
        engine.load = Mock(return_value=0)
        engine.classify = Mock(side_effect=BrokenPipeError("closed client"))
        engine.generate = Mock()
        events = []
        with self.assertRaises(BrokenPipeError):
            engine.run(VALID_INPUT, events.append)
        self.assertEqual(engine.load.call_count, 1)
        engine.generate.assert_not_called()
        self.assertNotIn("run_end", [event["type"] for event in events])
        self.assertNotIn("model_error", [event["type"] for event in events])


if __name__ == "__main__":
    unittest.main(verbosity=2)
