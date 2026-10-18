"""Isolated BGE and Qdrant wire fixture for verify-cangjie; never a runtime fallback."""

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def main():
    port, state_file = int(sys.argv[1]), Path(sys.argv[2])

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            self.respond(200, {"title": "qdrant", "version": "1.15.0"})

        def respond(self, status, data):
            encoded = json.dumps(data).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            state = json.loads(state_file.read_text())
            with state_file.with_suffix(".calls.jsonl").open("a") as output:
                output.write(json.dumps({"path": self.path, "body": body}) + "\n")
            if state.get("unavailable"):
                self.respond(503, {"error": "isolated retrieval unavailable"})
            elif self.path == "/embed":
                self.respond(
                    200,
                    {
                        "dense": [[0.1, 0.9] for _ in body["texts"]],
                        "sparse": [{"3": 0.5, "1": 0.3} for _ in body["texts"]],
                    },
                )
            elif self.path == "/rerank":
                self.respond(
                    200,
                    {
                        "scores": [
                            0.95 - index * 0.03
                            for index, _ in enumerate(body["documents"])
                        ]
                    },
                )
            elif self.path.endswith("/points/query"):
                hits = state.get("hits", [])
                if body.get("using") in {"dense", "sparse"}:
                    hits = sorted(
                        hits, key=lambda item: item.get(body["using"] + "_rank", 100)
                    )
                points = [
                    {
                        "id": item["id"],
                        "version": 1,
                        "score": item.get("fusion_score", 0.9),
                        "payload": {"question_id": item["id"]},
                    }
                    for item in hits
                ]
                self.respond(
                    200, {"result": {"points": points}, "status": "ok", "time": 0.001}
                )
            else:
                self.respond(404, {"error": "unknown fixture operation"})

    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
