"""Class invitations, persistent business messages and supplemental assignments."""
from alembic import op
import sqlalchemy as sa
revision='0010_teaching_messages'
down_revision='0009_lesson_draft_versions'
branch_labels=depends_on=None

def upgrade():
    bind=op.get_bind()
    def add(table,name,col):
        if name not in {c['name'] for c in sa.inspect(bind).get_columns(table)}:op.add_column(table,col)
    add('classrooms','subject',sa.Column('subject',sa.String(80),nullable=False,server_default=''))
    for name,size,default in [('kind',24,'note'),('due_date',40,''),('status',24,'active')]:add('supplemental_instructions',name,sa.Column(name,sa.String(size),nullable=False,server_default=default))
    from sczx_business.models import ClassInvite,JoinThrottle,BusinessMessage,SupplementRecipient
    for model in (ClassInvite,JoinThrottle,BusinessMessage,SupplementRecipient):model.__table__.create(bind,checkfirst=True)

def downgrade():
    for table in ('supplement_recipients','business_messages','class_join_throttles','class_invites'):op.drop_table(table)
    for name in ('status','due_date','kind'):op.drop_column('supplemental_instructions',name)
    op.drop_column('classrooms','subject')
