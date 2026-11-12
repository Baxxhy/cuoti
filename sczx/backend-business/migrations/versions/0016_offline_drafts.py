"""Append offline sync receipts; do not rewrite historical learning data."""
from alembic import op
revision='0016_offline_drafts'
down_revision='0015_classroom_community'
branch_labels=depends_on=None
def upgrade():
    import sqlalchemy as sa
    if not sa.inspect(op.get_bind()).has_table('offline_operations'):
        op.create_table('offline_operations',
            sa.Column('owner_id',sa.String(40),sa.ForeignKey('accounts.id'),primary_key=True),
            sa.Column('operation_id',sa.String(64),primary_key=True),
            sa.Column('request_hash',sa.String(64),nullable=False),
            sa.Column('result',sa.JSON(),nullable=False),
            sa.Column('created_at',sa.DateTime(),server_default=sa.func.now(),nullable=False))
def downgrade():
    raise RuntimeError('同步记录必须保留；请恢复独立备份，不自动删表。')
