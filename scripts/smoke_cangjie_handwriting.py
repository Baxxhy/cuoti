"""Teaching handwriting upload and owner/context validation through real HTTP."""

import io
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4

from PIL import Image, ImageDraw
from smoke_cangjie_accounts import request


def handwriting(endpoint, env, token, other, flow, state, kind="tutor"):
    image = Image.new("RGB", (100, 80), "white")
    ImageDraw.Draw(image).rectangle((20, 10, 40, 30), fill="red")
    output = io.BytesIO()
    image.save(output, "PNG")
    recognized = {
        "final_answer": "x=5",
        "steps": ["3x=15", "x=5"],
        "transcription": "3x=15，x=5",
        "confidence": 0.9,
        "uncertain": False,
    }
    state["handwriting_result"] = recognized
    state["handwriting"] = True
    state["image_size"] = (100, 80)

    def upload(account=token, activity_id=None, expected=200):
        boundary = "handwriting-" + uuid4().hex
        fields = {
            "context_type": kind,
            "context_id": flow["id"],
            "activity_id": activity_id or flow["activity"]["id"],
            **flow.get("upload_fields", {}),
        }
        body = b"".join(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode()
            for key, value in fields.items()
        )
        body += (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="work.png"\r\nContent-Type: image/png\r\n\r\n'.encode()
            + output.getvalue()
            + f"\r\n--{boundary}--\r\n".encode()
        )
        try:
            response = urlopen(
                Request(
                    endpoint + "/api/v1/answers/handwriting",
                    data=body,
                    headers={
                        "Authorization": "Bearer " + account,
                        "Content-Type": "multipart/form-data; boundary=" + boundary,
                    },
                ),
                timeout=20,
            )
        except HTTPError as error:
            response = error
        with response:
            payload = json.load(response)
            assert response.status == expected, (response.status, payload)
        return payload.get("data")

    try:
        upload(account=other, expected=404)
        if kind == "tutor":
            upload(activity_id="stale", expected=409)
        result = upload()
        assert result["recognition"] == recognized
        path = urlsplit(result["image_url"]).path
        assert (Path(env["CANGJIE_MEDIA_ROOT"]) / path.lstrip("/")).is_file()
        with urlopen(endpoint + result["image_url"]) as response:
            assert response.status == 200
        answer_path = {
            "tutor": "/api/v1/tutor/sessions/" + flow["id"] + "/activity/answer",
            "review": "/api/v1/reviews/" + flow["id"] + "/attempt",
            "assignment": "/api/v1/students/assignments/" + flow["id"] + "/attempts",
            "practice": "/api/v1/practice/attempt",
        }[kind]
        for fields in [
            {"handwriting_recognition": recognized},
            {
                "handwriting_image_url": result["image_url"],
                "handwriting_recognition": {"confidence": 2},
            },
            {
                "handwriting_image_url": result["image_url"].replace(
                    "/" + kind + "/", "/invalid/"
                ),
                "handwriting_recognition": recognized,
            },
        ]:
            request(
                endpoint,
                "POST",
                answer_path,
                {
                    "activity_id": flow["activity"]["id"],
                    "answer": "x=5",
                    **flow.get("answer_fields", {}),
                    **fields,
                },
                token=token,
                expected=422,
            )
        return {
            "handwriting_image_url": result["image_url"],
            "handwriting_recognition": recognized,
            "working": "3x=15，x=5",
        }
    finally:
        state["handwriting"] = False
