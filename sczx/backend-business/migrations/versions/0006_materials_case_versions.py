"""原始材料、定位片段与不可变案例版本。"""
from alembic import op
import sqlalchemy as sa
from sczx_business.models import SourceMaterial, MaterialUnit, CaseDraftContent, CaseVersion
import json
import uuid

revision = '0006_materials_case_versions'
down_revision = '0005_model_job_deduplication'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    for model in (SourceMaterial, MaterialUnit, CaseDraftContent, CaseVersion):
        model.__table__.create(connection, checkfirst=True)
    if 'case_snapshot' not in {c['name'] for c in sa.inspect(connection).get_columns('lesson_drafts')}:
        op.add_column('lesson_drafts', sa.Column('case_snapshot', sa.JSON(), nullable=True))
    for case in connection.execute(sa.text('SELECT id,title,source,content,status FROM teaching_cases')).mappings():
        payload = {'title': case['title'], 'source': case['source'], 'content': case['content'], 'author': '', 'grade': '', 'subject': '数学', 'experience': {}, 'references': [], 'legacy': True}
        if case['status'] == 'published' and not connection.execute(sa.text('SELECT id FROM case_versions WHERE case_id=:id'), {'id': case['id']}).first():
            connection.execute(CaseVersion.__table__.insert().values(id='version-'+uuid.uuid4().hex, case_id=case['id'], number=1, data=payload))
        elif case['status'] == 'draft' and not connection.execute(sa.text('SELECT case_id FROM case_draft_contents WHERE case_id=:id'), {'id': case['id']}).first():
            connection.execute(CaseDraftContent.__table__.insert().values(case_id=case['id'], data=payload, reviewed=False))


def downgrade():
    op.drop_column('lesson_drafts', 'case_snapshot')
    for model in (CaseVersion, CaseDraftContent, MaterialUnit, SourceMaterial):
        model.__table__.drop(op.get_bind(), checkfirst=True)
