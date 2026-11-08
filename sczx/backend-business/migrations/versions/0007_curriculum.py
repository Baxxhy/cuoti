"""Course units, prerequisite knowledge, immutable lesson publications."""
from alembic import op
from sqlalchemy import inspect, Column, JSON, String, ForeignKey
from sczx_business.models import CourseUnit, KnowledgePoint, LessonContent, LessonVersion
revision = '0007_curriculum'
down_revision = '0006_materials_case_versions'
branch_labels = depends_on = None


def upgrade():
    bind = op.get_bind()
    for table in (CourseUnit.__table__, KnowledgePoint.__table__, LessonContent.__table__, LessonVersion.__table__):
        table.create(bind, checkfirst=True)
    changes = [('courses', Column('metadata_json', JSON, nullable=True)), ('lessons', Column('unit_id', String(40), nullable=True)), ('lesson_drafts', Column('lesson_snapshot', JSON, nullable=True))]
    for name, column in changes:
        if column.name not in {c['name'] for c in inspect(bind).get_columns(name)}: op.add_column(name, column)


def downgrade():
    raise RuntimeError('Retain published teaching content; restore from a deliberate backup instead.')
