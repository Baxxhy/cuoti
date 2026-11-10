"""Append-only learning evidence corrections and review preferences."""
from alembic import op
revision='0012_learning_memory'
down_revision='0011_wrong_remediation'
branch_labels=depends_on=None

def upgrade():
    from sczx_business.models import LearningMemoryChange
    LearningMemoryChange.__table__.create(op.get_bind(),checkfirst=True)

def downgrade():
    raise RuntimeError('保留学习纠正审计记录，不自动删除；回退前先导出。')
