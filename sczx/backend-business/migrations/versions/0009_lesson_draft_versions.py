"""Teacher draft revisions, immutable history and optional planning details."""
from alembic import op
import sqlalchemy as sa
revision='0009_lesson_draft_versions'
down_revision='0008_knowledge_aliases'
branch_labels=depends_on=None

def upgrade():
    bind=op.get_bind(); cols={c['name'] for c in sa.inspect(bind).get_columns('lesson_drafts')}
    if 'revision' not in cols:op.add_column('lesson_drafts',sa.Column('revision',sa.Integer,nullable=False,server_default='0'))
    if 'planning_details' not in cols:op.add_column('lesson_drafts',sa.Column('planning_details',sa.JSON,nullable=True))
    if not sa.inspect(bind).has_table('lesson_draft_versions'):
        op.create_table('lesson_draft_versions',sa.Column('id',sa.String(40),primary_key=True),sa.Column('draft_id',sa.String(40),sa.ForeignKey('lesson_drafts.id'),nullable=False,index=True),sa.Column('number',sa.Integer,nullable=False),sa.Column('data',sa.JSON,nullable=False),sa.Column('reason',sa.String(100),nullable=False),sa.Column('created_at',sa.DateTime,server_default=sa.func.now(),nullable=False),sa.UniqueConstraint('draft_id','number',name='uq_draft_version_number'))

def downgrade():
    op.drop_table('lesson_draft_versions')
    op.drop_column('lesson_drafts','planning_details')
    op.drop_column('lesson_drafts','revision')
