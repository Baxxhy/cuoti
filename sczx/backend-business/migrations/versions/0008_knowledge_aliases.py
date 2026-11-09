"""Knowledge aliases; immutable teaching versions remain untouched."""
from alembic import op
from sqlalchemy import inspect, Column, JSON
revision='0008_knowledge_aliases'
down_revision='0007_curriculum'
branch_labels=depends_on=None


def upgrade():
    if 'aliases' not in {c['name'] for c in inspect(op.get_bind()).get_columns('knowledge_points')}:
        op.add_column('knowledge_points',Column('aliases',JSON,nullable=True))


def downgrade():
    if 'aliases' in {c['name'] for c in inspect(op.get_bind()).get_columns('knowledge_points')}:
        op.drop_column('knowledge_points','aliases')
