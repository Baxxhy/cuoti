"""Local acceptance-only proxy: forwards real computation, can delay its reply."""

import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def main():
    port, upstream, control_path, event_path = sys.argv[1:]
    lock = threading.Lock()

    def event(**fields):
        with lock, Path(event_path).open("a") as stream:
            stream.write(json.dumps(fields) + "\n")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            try:
                count = int(self.headers.get("Content-Length", "0"))
                if not 0 < count <= 128 * 1024 * 1024 or self.path != "/v1/compute":
                    self.send_error(400)
                    return
                body = self.rfile.read(count)
                value = json.loads(body)
                try:
                    rules = json.loads(Path(control_path).read_text()).get("rules", [])
                except (OSError, ValueError):
                    rules = []
                operation = value.get("operation")
                question = value.get("task_context", {}).get("question_id")
                task = value.get("learning_evidence", {}).get("learning_task_id")
                rule = next(
                    (
                        r
                        for r in rules
                        if r.get("operation") == operation
                        and (
                            (question and r.get("question_id") == question)
                            or (task and r.get("task_id") == task)
                        )
                    ),
                    None,
                )
                started = time.monotonic()
                if rule:
                    event(
                        kind="accepted",
                        key=rule["key"],
                        operation=operation,
                        task_budget_ms=value.get("task_budget_ms"),
                    )
                try:
                    response = urlopen(
                        Request(
                            upstream + self.path,
                            data=body,
                            headers={
                                "Authorization": self.headers.get("Authorization", ""),
                                "Content-Type": "application/json",
                            },
                        ),
                        timeout=55,
                    )
                except HTTPError as error:
                    response = error
                with response:
                    status = response.status
                    payload = response.read(128 * 1024 * 1024 + 1)
                if len(payload) > 128 * 1024 * 1024:
                    raise ValueError("response too large")
                # Acceptance-only corruption after real Python/Pydantic validation:
                # the native business boundary must independently reject it.
                if (
                    rule
                    and rule.get("invalid_tool")
                    and operation == "learning_task"
                    and status == 200
                ):
                    result = json.loads(payload)
                    trace = dict(result["result"]["traces"][-1])
                    trace["tool_name"] = "delete_database"
                    result["result"]["traces"].append(trace)
                    payload = json.dumps(result).encode()
                if rule:
                    time.sleep(min(50, max(0, float(rule.get("delay_seconds", 0)))))
                try:
                    self.send_response(status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                except (BrokenPipeError, ConnectionResetError):
                    pass
                if rule:
                    event(
                        kind="released",
                        key=rule["key"],
                        operation=operation,
                        elapsed_ms=int((time.monotonic() - started) * 1000),
                    )
            except Exception as error:  # noqa: BLE001 -- record only an exception class in this local test fixture
                event(kind="error", error_type=type(error).__name__)
                try:
                    self.send_error(503)
                except (BrokenPipeError, ConnectionResetError):
                    pass

    server = ThreadingHTTPServer(("127.0.0.1", int(port)), Handler)
    server.daemon_threads = True
    server.serve_forever()


if __name__ == "__main__":
    main()
