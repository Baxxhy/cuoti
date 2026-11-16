import json
import time
from pathlib import Path

import pytest
from cuoti_backend.security import (
    create_token,
    hash_password,
    read_token,
    verify_password,
)

VECTOR = json.loads((Path(__file__).parent / "fixtures/auth_vectors.json").read_text())


def test_original_password_and_token_vectors():
    assert hash_password(VECTOR["password"], bytes(range(16))) == VECTOR["encoded"]
    assert verify_password(VECTOR["password"], VECTOR["encoded"])
    assert (
        read_token(VECTOR["token"], VECTOR["secret"], VECTOR["encoded"])
        == VECTOR["user_id"]
    )
    assert (
        create_token(VECTOR["user_id"], VECTOR["secret"], VECTOR["encoded"], 4102444800)
        == VECTOR["token"]
    )


@pytest.mark.parametrize(
    "value", ["", "bad", "pbkdf2_sha256$???$bad", "pbkdf2_sha256$AA==$bad"]
)
def test_invalid_password_hash(value):
    assert not verify_password("password", value)


def test_token_tampering_expiry_and_changed_password():
    v = VECTOR
    assert read_token(v["token"] + "a", v["secret"]) is None
    assert read_token(v["token"], "wrong-secret") is None
    assert read_token(v["token"], v["secret"], hash_password("changed")) is None
    assert (
        read_token(
            create_token(v["user_id"], v["secret"], v["encoded"], int(time.time()) - 1),
            v["secret"],
        )
        is None
    )
    for token in ["", "a.b.c", "a." + "b" * 9000, "中文.中文"]:
        assert read_token(token, v["secret"]) is None
