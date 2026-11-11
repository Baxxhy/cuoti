"""Preserve existing lesson/exam records; add classroom/group/community state."""
from alembic import op
revision='0015_classroom_community'
down_revision='0014_examinations'
branch_labels=depends_on=None
def upgrade():
 from sczx_business.classroom_models import LiveClass,LivePresence,LiveActivity,LiveAnswer,TeachingGroupPlan,CommunityShare,CommunityBookmark,CommunityEvent
 for model in [LiveClass,LivePresence,LiveActivity,LiveAnswer,TeachingGroupPlan,CommunityShare,CommunityBookmark,CommunityEvent]:model.__table__.create(op.get_bind(),checkfirst=True)
def downgrade():raise RuntimeError('课堂原始回答及教研历史必须保留；恢复到独立备份库，不自动删表。')
