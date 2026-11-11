"""Append offline sync receipts; do not rewrite historical learning data."""
from alembic import op
revision='0016_offline_drafts'
down_revision='0015_classroom_community'
branch_labels=depends_on=None
def upgrade():
    from sczx_business.offline_models import OfflineOperation
    OfflineOperation.__table__.create(op.get_bind(),checkfirst=True)
def downgrade():
    raise RuntimeError('同步记录必须保留；请恢复独立备份，不自动删表。')
