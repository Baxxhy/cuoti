import importlib.util
import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]


def module(name):
    spec = importlib.util.spec_from_file_location(
        "delivery_" + name, ROOT / "deployment/competition" / (name + ".py")
    )
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def test_secrets_reuse_and_missing_secret_refusal(tmp_path, monkeypatch):
    entry = module("entry")
    monkeypatch.setattr(entry, "DATA", tmp_path)
    first = entry.credentials()
    assert entry.credentials() == first
    assert (tmp_path / "secrets.json").stat().st_mode & 0o777 == 0o600
    (tmp_path / "secrets.json").unlink()
    (tmp_path / "mysql/mysql").mkdir(parents=True)
    with pytest.raises(RuntimeError, match="缺少原密钥"):
        entry.credentials()
    assert not (tmp_path / "secrets.json").exists()


def test_existing_database_never_reinitialized_and_upgrade_is_explicit(
    tmp_path, monkeypatch
):
    entry = module("entry")
    monkeypatch.setattr(entry, "DATA", tmp_path)
    monkeypatch.delenv("CUOTI_UPGRADE_DB", raising=False)
    calls = []

    def output(args, **kwargs):
        if "-NBe" in args:
            return "50"
        return json.dumps({"missing": ["013_bank_grade_index"]})

    monkeypatch.setattr(entry.subprocess, "check_output", output)
    monkeypatch.setattr(entry, "run", lambda args, **kwargs: calls.append(args))
    with pytest.raises(RuntimeError, match="需升级"):
        entry.prepare_database(["mysql"], {})
    assert calls == [] and not (tmp_path / "initialized").exists()
    monkeypatch.setenv("CUOTI_UPGRADE_DB", "true")
    entry.prepare_database(["mysql"], {})
    assert len(calls) == 1 and calls[0][-1] == "upgrade"
    assert (tmp_path / "initialized").exists()


def test_delivery_environment_has_no_compiler_or_separate_algorithm_process(
    tmp_path, monkeypatch
):
    entry = module("entry")
    monkeypatch.setattr(entry, "DATA", tmp_path)
    value = {key: "a" * 64 for key in ["db", "root", "auth", "algorithm"]}
    env = entry.environment(value)
    assert env["CUOTI_PROJECT_ROOT"] == str(tmp_path)
    assert env["CUOTI_AUTH_SECRET"] == value["auth"]
    assert "backend-python" in env["PYTHONPATH"]
    assert env["CUOTI_PORT"] == "8002"
    source = (ROOT / "deployment/competition/entry.py").read_text()
    assert "backend-cangjie/main" not in source and '"8012"' not in source
    assert "cuoti_backend" in source


def test_gateway_keeps_auth_query_binary_and_static_boundaries(tmp_path, monkeypatch):
    gateway = module("gateway")
    monkeypatch.setattr(gateway, "ROOT", tmp_path)
    (tmp_path / "index.html").write_text("<h1>Cuoti</h1>")
    seen = []

    def upstream(request):
        seen.append(request)
        assert request.headers["authorization"] == "Bearer test-token"
        if request.url.path == "/reports/test.pdf":
            return httpx.Response(
                200,
                content=b"%PDF-test",
                headers={
                    "content-type": "application/pdf",
                    "content-disposition": 'attachment; filename="test.pdf"',
                },
            )
        return httpx.Response(200, json={"ok": True})

    with TestClient(gateway.app) as client:
        gateway.app.state.client._transport = httpx.MockTransport(upstream)
        headers = {"Authorization": "Bearer test-token"}
        response = client.get("/api/v1/papers?kind=a&kind=b", headers=headers)
        assert response.status_code == 200
        assert seen[-1].url.params.get_list("kind") == ["a", "b"]
        binary = client.get(
            "/reports/test.pdf?expires=123&signature=abc", headers=headers
        )
        assert (
            binary.content == b"%PDF-test"
            and "attachment" in binary.headers["content-disposition"]
        )
        assert seen[-1].url.params["signature"] == "abc"
        assert client.get("/").text == "<h1>Cuoti</h1>"
        outside = tmp_path.parent / (tmp_path.name + "-outside.txt")
        outside.write_text("private")
        try:
            (tmp_path / "escape").symlink_to(outside)
            assert client.get("/escape").status_code == 403
        finally:
            outside.unlink()


def test_payload_copy_omits_private_configuration_and_backups(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "deployment/competition"))
    payload = module("prepare_payload")
    source, target = tmp_path / "source", tmp_path / "payload"
    source.mkdir()
    (source / "public.py").write_text("print('public')")
    for name in [".env", ".env.python", "api_pool.json"]:
        (source / name).write_text("private")
    (source / "backups").mkdir()
    (source / "backups/data.sql").write_text("private")
    payload.copy(source, target)
    assert (target / "public.py").is_file()
    assert not any(
        (target / name).exists()
        for name in [".env", ".env.python", "api_pool.json", "backups"]
    )


@pytest.mark.parametrize("fail_backup", [0, 1, 2])
def test_update_backup_failure_restores_old_container_without_replacement(
    tmp_path, fail_backup
):
    import os
    import shutil
    import subprocess
    import sys

    script = tmp_path / "start.sh"
    shutil.copy2(ROOT / "deployment/competition/start.sh", script)
    (tmp_path / ".env").write_text("XIAOJING_API_KEY=fixture-only\n")
    tools = tmp_path / "tools"
    tools.mkdir()
    log = tmp_path / "docker-calls.jsonl"
    fake = tools / "docker"
    fake.write_text(
        f"#!{sys.executable}\n"
        + """import gzip,json,os,sys
from pathlib import Path
a=sys.argv[1:]
with Path(os.environ['DOCKER_CALLS']).open('a') as out: out.write(json.dumps(a)+'\\n')
if a[:2]==['inspect','--format']: print('cuoti-delivery')
if a[:2]==['run','--rm']:
    if os.environ['FAIL_BACKUP']=='1': raise SystemExit(9)
    sys.stdout.buffer.write(b'corrupt' if os.environ['FAIL_BACKUP']=='2' else gzip.compress(b'volume-backup'))
"""
    )
    fake.chmod(0o700)
    result = subprocess.run(
        ["bash", str(script)],
        env={
            **os.environ,
            "PATH": str(tools) + os.pathsep + os.environ["PATH"],
            "DOCKER_CALLS": str(log),
            "FAIL_BACKUP": str(int(fail_backup)),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    stop = next(index for index, call in enumerate(calls) if call[:2] == ["stop", "-t"])
    backup = next(
        index for index, call in enumerate(calls) if call[:2] == ["run", "--rm"]
    )
    assert stop < backup
    if fail_backup:
        assert result.returncode == 1
        assert ["start", "cuoti-delivery-app"] in calls
        assert not any(call[0] == "rm" for call in calls)
        assert not any(
            call[:2] == ["run", "-d"] and "cuoti-delivery-app" in call for call in calls
        )
    else:
        assert result.returncode == 0
        remove = calls.index(["rm", "cuoti-delivery-app"])
        launch = next(
            index
            for index, call in enumerate(calls)
            if call[:2] == ["run", "-d"] and "cuoti-delivery-app" in call
        )
        assert backup < remove < launch
        saved = list((tmp_path / "backups").glob("*.tar.gz"))
        assert len(saved) == 1 and saved[0].stat().st_mode & 0o777 == 0o600
