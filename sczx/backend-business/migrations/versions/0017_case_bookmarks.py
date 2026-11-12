"""Persist the existing private case favorite; no historical rows are rewritten."""
from alembic import op
revision='0017_case_bookmarks'
down_revision='0016_offline_drafts'
branch_labels=depends_on=None
def upgrade():
    from sczx_business.models import CaseBookmark
    CaseBookmark.__table__.create(op.get_bind(),checkfirst=True)
def downgrade():
    raise RuntimeError('收藏记录保留；需要回退时恢复独立备份，不自动删表。')
