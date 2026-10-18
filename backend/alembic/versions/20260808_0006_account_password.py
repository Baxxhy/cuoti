"""账号密码与固定角色登录。"""

import base64
import hashlib
import os

import sqlalchemy as sa
from alembic import op

revision = "20260808_0006"
down_revision = "20260808_0005"
branch_labels = None
depends_on = None


def _hash_default_password() -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", b"123456", salt, 210_000)
    return (
        f"pbkdf2_sha256${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"
    )


def upgrade() -> None:
    columns = {item["name"]: item for item in sa.inspect(op.get_bind()).get_columns("users")}
    if "password_hash" not in columns:
        op.add_column("users", sa.Column("password_hash", sa.String(255), nullable=True))
    op.execute(
        sa.text("UPDATE users SET password_hash=:value WHERE password_hash IS NULL").bindparams(
            value=_hash_default_password()
        )
    )
    columns = {item["name"]: item for item in sa.inspect(op.get_bind()).get_columns("users")}
    if columns["password_hash"]["nullable"]:
        op.alter_column("users", "password_hash", existing_type=sa.String(255), nullable=False)


def downgrade() -> None:
    op.drop_column("users", "password_hash")
