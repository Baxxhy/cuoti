"""Extend existing issues/supplements; preserve all original rows and replies."""
from alembic import op
import sqlalchemy as sa
revision='0013_teaching_insights'
down_revision='0012_learning_memory'
branch_labels=depends_on=None

def upgrade():
    inspector=sa.inspect(op.get_bind())
    if 'details' not in {c['name'] for c in inspector.get_columns('supplemental_instructions')}:op.add_column('supplemental_instructions',sa.Column('details',sa.JSON(),nullable=True))
    existing={c['name'] for c in inspector.get_columns('support_issues')}
    for col in [sa.Column('task_id',sa.String(40),sa.ForeignKey('learning_tasks.id'),nullable=True),sa.Column('category',sa.String(24),server_default='learning',nullable=False),sa.Column('status',sa.String(24),server_default='pending',nullable=False),sa.Column('revision',sa.Integer(),server_default='1',nullable=False),sa.Column('request_key',sa.String(100),nullable=True),sa.Column('created_at',sa.DateTime(),nullable=True)]:
        if col.name not in existing:op.add_column('support_issues',col)
    if not any(c['column_names']==['request_key'] for c in inspector.get_unique_constraints('support_issues')):op.create_unique_constraint('uq_issue_request_key','support_issues',['request_key'])
    # Original resolved/reply/text remain byte-for-byte unchanged.
    op.execute("UPDATE support_issues SET status='replied' WHERE resolved=1")
    from sczx_business.models import SupportIssueEvent
    SupportIssueEvent.__table__.create(op.get_bind(),checkfirst=True)

def downgrade():raise RuntimeError('需先导出问题历史及教学安排，不自动删除。')
