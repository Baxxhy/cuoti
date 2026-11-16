from typing import Any

from pydantic import BaseModel, model_validator

from .protocol import ApiError

GRADES = ["初一", "初二", "初三", "高一", "高二", "高三"]
SUBJECTS = [
    "语文",
    "数学",
    "英语",
    "物理",
    "化学",
    "生物",
    "历史",
    "地理",
    "道德与法治",
    "思想政治",
]


def text_field(body, key, limit, *, trim=True, default=None):
    if key not in body and default is None:
        raise ApiError(422, f"缺少 {key}")
    value = body.get(key, default)
    if not isinstance(value, str):
        raise ApiError(422, f"{key} 必须是文字")
    value = value.strip() if trim else value
    if not 1 <= len(value) <= limit:
        raise ApiError(422, f"{key} 长度不正确")
    return value


def email_field(body):
    value = text_field(body, "email", 190)
    value = value.translate(
        str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")
    )
    parts = value.split("@")
    if (
        len(parts) != 2
        or not all(parts)
        or "." not in parts[1]
        or parts[1].startswith(".")
        or parts[1].endswith(".")
    ):
        raise ApiError(422, "请输入正确的邮箱")
    if any(c.isspace() for c in value):
        raise ApiError(422, "请输入正确的邮箱")
    return value


def strict_fields(body, allowed):
    if set(body) - set(allowed):
        raise ApiError(422, "请求包含不支持的字段")


class Credentials(BaseModel):
    email: str
    password: str

    @model_validator(mode="before")
    @classmethod
    def validate_input(cls, body: Any):
        return {
            **body,
            "email": email_field(body),
            "password": text_field(body, "password", 256, trim=False),
        }


class Registration(Credentials):
    name: str = "智维同学"
    grade: str = "初二"

    @model_validator(mode="before")
    @classmethod
    def validate_registration(cls, body):
        return {
            **body,
            "name": text_field(body, "name", 100, default="智维同学"),
            "grade": text_field(body, "grade", 30, default="初二"),
        }


class PasswordChange(BaseModel):
    email: str
    current_password: str
    new_password: str

    @model_validator(mode="before")
    @classmethod
    def validate_input(cls, body):
        return {
            "email": email_field(body),
            **{
                key: text_field(body, key, 256, trim=False)
                for key in ["current_password", "new_password"]
            },
        }


class ProfilePatch(BaseModel):
    name: str | None = None
    email: str | None = None
    grade: str | None = None
    current_password: Any = None

    @model_validator(mode="before")
    @classmethod
    def validate_input(cls, body):
        strict_fields(body, cls.model_fields)
        result = dict(body)
        for key, limit in [("name", 100), ("grade", 30)]:
            if key in body:
                result[key] = text_field(body, key, limit)
        if "email" in body:
            result["email"] = email_field(body)
        # The old handler reads current_password only when email actually changes.
        return result


class PreferencePatch(BaseModel):
    grade: str | None = None
    subject: str
    minutes: int
    goal: str
    version: int

    @model_validator(mode="before")
    @classmethod
    def validate_input(cls, body):
        strict_fields(body, cls.model_fields)
        if type(body.get("version")) is not int:
            raise ApiError(409, "学习方向已变化，请重新读取后保存")
        result = dict(body)
        if "grade" in body:
            result["grade"] = text_field(body, "grade", 30)
            if result["grade"] not in GRADES:
                raise ApiError(422, "请选择初一至高三的年级")
        result["subject"] = text_field(body, "subject", 30)
        if result["subject"] not in SUBJECTS:
            raise ApiError(422, "请选择支持的学科")
        if type(body.get("minutes")) is not int or body["minutes"] not in [5, 10, 20]:
            raise ApiError(422, "请选择5、10或20分钟")
        result["goal"] = text_field(body, "goal", 30)
        if result["goal"] not in ["understand", "practice", "review"]:
            raise ApiError(422, "请选择学习目标")
        return result


class UserOutput(BaseModel):
    id: str
    email: str
    name: str
    role: str
    created_at: str
    updated_at: str
