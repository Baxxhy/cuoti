"""Independent wrong questions and immutable dynamic repair snapshots."""
from alembic import op
import sqlalchemy as sa
revision='0011_wrong_remediation'
down_revision='0010_teaching_messages'
branch_labels=depends_on=None

def upgrade():
    bind=op.get_bind()
    columns={c['name'] for c in sa.inspect(bind).get_columns('wrong_questions')}
    if 'owner_id' not in columns:
        op.add_column('wrong_questions',sa.Column('owner_id',sa.String(40),sa.ForeignKey('accounts.id'),nullable=True))
        op.create_index('ix_wrong_questions_owner_id','wrong_questions',['owner_id'])
    if 'details' not in columns:op.add_column('wrong_questions',sa.Column('details',sa.JSON(),nullable=True))
    op.alter_column('wrong_questions','record_id',existing_type=sa.String(40),nullable=True)
    op.execute('UPDATE wrong_questions w JOIN student_records r ON w.record_id=r.id SET w.owner_id=r.student_id WHERE w.owner_id IS NULL')
    if 'details' not in {c['name'] for c in sa.inspect(bind).get_columns('repair_attempts')}:
        op.add_column('repair_attempts',sa.Column('details',sa.JSON(),nullable=True))

def downgrade():
    raise RuntimeError('本迁移含独立个人错题，不提供丢弃数据的自动回退；恢复前先导出并核对。')
