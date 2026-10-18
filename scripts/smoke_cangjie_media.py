"""Verify signed file streaming and confinement without involving Python serving."""

import hashlib
import hmac
import os
import socket
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen


def media(endpoint, env, pid):
    root = Path(env["CANGJIE_MEDIA_ROOT"])
    uploads = root / "uploads"
    reports = root / "reports"
    uploads.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)
    image = b"\x89PNG\r\n\x1a\n\x00\xfffixture"
    relative = "/uploads/中文 空格.png"
    (root / relative.lstrip("/")).write_bytes(image)
    report = bytes(range(256)) * 20000
    (reports / "large.pdf").write_bytes(report)
    (uploads / "empty.png").write_bytes(b"")
    outside = root.parent / "outside.txt"
    outside.write_bytes(b"must never be served")
    (uploads / "link.txt").symlink_to(outside)
    (uploads / "linked-dir").symlink_to(root.parent, target_is_directory=True)
    os.mkfifo(uploads / "pipe")

    def signed(path, expires=None):
        expires = int(time.time()) + 300 if expires is None else expires
        signature = hmac.new(
            env["CANGJIE_AUTH_SECRET"].encode(),
            f"media:v1:{expires}:{path}".encode(),
            hashlib.sha256,
        ).hexdigest()
        return quote(path, safe="/") + f"?expires={expires}&signature={signature}"

    def fetch(path, status=200, method="GET", headers=None):
        try:
            response = urlopen(
                Request(endpoint + path, method=method, headers=headers or {}),
                timeout=10,
            )
        except HTTPError as error:
            response = error
        with response:
            assert response.status == status, (path, response.status, status)
            return response.headers, response.read()

    url = signed(relative)
    headers, body = fetch(url)
    assert body == image and headers.get_content_type() == "image/png"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["Accept-Ranges"] == "bytes"
    etag = headers["ETag"]
    head, body = fetch(url, method="HEAD")
    assert body == b"" and int(head["Content-Length"]) == len(image)
    assert head["ETag"] == etag
    assert fetch(url, 304, headers={"If-None-Match": etag})[1] == b""
    assert fetch(url, 304, headers={"If-None-Match": "W/" + etag})[1] == b""
    assert fetch(url, 304, headers={"If-None-Match": "*"})[1] == b""
    fetch(quote(relative), 403, headers={"If-None-Match": etag})
    fetch(signed(relative, int(time.time()) - 1), 403)
    fetch(signed(relative, int(time.time()) + 15000), 403)
    fetch(url + "x", 403)
    fetch(
        "/uploads/中文.png?expires=invalid&signature=x".replace(
            "中文", "%E4%B8%AD%E6%96%87"
        ),
        403,
    )
    fetch(url, 405, method="POST")
    for path in (
        "/uploads/missing.png",
        "/uploads/link.txt",
        "/uploads/linked-dir/outside.txt",
        "/uploads/pipe",
        "/uploads/../outside.txt",
        "/uploads/../../outside.txt",
        "/uploads/",
        "/uploads/bad\x00name",
    ):
        fetch(signed(path), 404)
    fetch(signed("/uploads/../outside.txt").replace("../", "%2E%2E/"), 404)
    for value, expected in (
        ("bytes=0-0", image[:1]),
        ("bytes=3-", image[3:]),
        ("bytes=-5", image[-5:]),
        ("bytes=2-99999", image[2:]),
    ):
        response, part = fetch(url, 206, headers={"Range": value})
        assert part == expected and response["Content-Range"].endswith(
            "/" + str(len(image))
        )
    for value in (
        "bytes=999999-",
        "bytes=3-1",
        "bytes=-0",
        "bytes=999999999999999999999999999999-",
        "nonsense",
    ):
        response, _ = fetch(url, 416, headers={"Range": value})
        assert response["Content-Range"] == f"bytes */{len(image)}"
    assert (
        fetch(url, headers={"Range": "bytes=0-0", "If-Range": '"outdated"'})[1] == image
    )
    assert (
        fetch(url, 206, headers={"Range": "bytes=0-0", "If-Range": etag})[1]
        == image[:1]
    )
    assert fetch(url, headers={"Range": "bytes=0-0,2-2"})[1] == image
    assert fetch(signed("/uploads/empty.png"))[1] == b""
    fetch(signed("/uploads/empty.png"), 416, headers={"Range": "bytes=0-0"})
    large_url = signed("/reports/large.pdf")
    assert fetch(large_url)[1] == report
    assert (
        fetch(large_url, 206, headers={"Range": "bytes=65000-70000"})[1]
        == report[65000:70001]
    )

    # File handles close even when clients stop reading a response partway through.
    def file_fds():
        count = 0
        for path in Path(f"/proc/{pid}/fd").iterdir():
            try:
                if str(root) in os.readlink(path):
                    count += 1
            except FileNotFoundError:
                pass
        return count

    assert file_fds() == 0
    host = urlsplit(endpoint)

    def abort(_):
        with socket.create_connection(
            (host.hostname, host.port), timeout=5
        ) as connection:
            connection.sendall(
                f"GET {large_url} HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n".encode()
            )
            connection.recv(1024)

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(abort, range(12)))
    deadline = time.monotonic() + 10
    while file_fds() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert file_fds() == 0
    (root / relative.lstrip("/")).write_bytes(image + b"changed")
    changed_headers, changed_body = fetch(url, headers={"If-None-Match": etag})
    assert changed_headers["ETag"] != etag and changed_body == image + b"changed"
    assert fetch("/livez")[0].get_content_type() == "application/json"
    print(
        "Cangjie media passed: signature expiry, Unicode paths, confinement, ranges, HEAD, ETag, streaming and disconnect cleanup"
    )
