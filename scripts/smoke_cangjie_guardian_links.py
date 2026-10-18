"""Consent and revocation through public APIs in the disposable Cangjie database."""

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from smoke_cangjie_accounts import request


def guardian_links(endpoint, env, query):
    def actor(role):
        email = f"family-{uuid4().hex}@example.test"
        user = request(
            endpoint,
            "POST",
            "/api/v1/auth/register",
            {
                "email": email,
                "password": "FamilyTest-123456",
                "name": "查看权限验收",
            },
        )
        if role != "student":
            query(env, f"UPDATE users SET role='{role}' WHERE id='{user['id']}'")
        return {**user, "email": email}

    pupil, other, guardian, foreign, teacher = [
        actor(role)
        for role in ("student", "student", "guardian", "guardian", "teacher")
    ]
    token = pupil["access_token"]
    path = "/api/v1/students/guardian-links"
    report = f"/api/v1/guardians/students/{pupil['id']}/overview"
    assert request(endpoint, "GET", path, token=token) == []
    request(endpoint, "GET", report, token=guardian["access_token"], expected=403)
    for confirmed in (None, False, "true", 1):
        request(
            endpoint,
            "POST",
            path,
            {"email": guardian["email"], "confirmed": confirmed},
            token=token,
            expected=422,
        )
    for non_guardian in (other, teacher):
        request(
            endpoint,
            "POST",
            path,
            {"email": non_guardian["email"], "confirmed": True},
            token=token,
            expected=404,
        )
    for account in (guardian, teacher):
        request(
            endpoint,
            "POST",
            path,
            {"email": guardian["email"], "confirmed": True},
            token=account["access_token"],
            expected=403,
        )

    def grant(_):
        return request(
            endpoint,
            "POST",
            path,
            {"email": guardian["email"].upper(), "confirmed": True},
            token=token,
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        grants = list(pool.map(grant, range(4)))
    assert all(row["id"] == guardian["id"] for row in grants)
    assert all(set(row) == {"id", "name", "email"} for row in grants)
    assert len(request(endpoint, "GET", path, token=token)) == 1
    assert (
        query(
            env,
            f"SELECT COUNT(*) FROM guardian_student_links WHERE student_id='{pupil['id']}'",
        )
        == "1"
    )
    assert (
        request(endpoint, "GET", report, token=guardian["access_token"])["student"][
            "id"
        ]
        == pupil["id"]
    )
    request(endpoint, "GET", report, token=foreign["access_token"], expected=403)
    # Neither an unrelated student nor another guardian can remove this pair.
    request(
        endpoint, "DELETE", path + "/" + guardian["id"], token=other["access_token"]
    )
    request(
        endpoint,
        "DELETE",
        f"/api/v1/guardians/students/{pupil['id']}",
        token=foreign["access_token"],
    )
    assert len(request(endpoint, "GET", path, token=token)) == 1
    for _ in range(2):
        request(endpoint, "DELETE", path + "/" + guardian["id"], token=token)
    request(endpoint, "GET", report, token=guardian["access_token"], expected=403)
    assert (
        request(
            endpoint,
            "GET",
            "/api/v1/guardians/students",
            token=guardian["access_token"],
        )
        == []
    )
    grant(0)
    request(
        endpoint,
        "DELETE",
        f"/api/v1/guardians/students/{pupil['id']}",
        token=guardian["access_token"],
    )
    request(endpoint, "GET", report, token=guardian["access_token"], expected=403)
    assert request(endpoint, "GET", path, token=token) == []
    # The configured limit is enforced while a repeated existing grant remains safe.
    grant(0)
    for _ in range(4):
        item = actor("guardian")
        request(
            endpoint,
            "POST",
            path,
            {"email": item["email"], "confirmed": True},
            token=token,
        )
    overflow = actor("guardian")
    request(
        endpoint,
        "POST",
        path,
        {"email": overflow["email"], "confirmed": True},
        token=token,
        expected=409,
    )
    grant(0)
    assert len(request(endpoint, "GET", path, token=token)) == 5
    print(
        "Cangjie guardian consent passed: explicit student grant, concurrent deduplication, five-link limit, isolation and bilateral revocation"
    )
