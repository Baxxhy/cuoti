"""将教学会话迁移到显式四阶段状态机。"""

from alembic import op

revision = "20260811_0012"
down_revision = "20260811_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE tutor_sessions
        SET stage = 'understanding'
        WHERE stage IN (
            'guided_question', 'prerequisite', 'local_hint',
            'strategy_switch', 'replan', 'answer_shown'
        )
        """
    )
    op.execute(
        """
        UPDATE tutor_sessions
        SET state = JSON_SET(
            COALESCE(state, JSON_OBJECT()),
            '$.understanding_passed',
            COALESCE(JSON_EXTRACT(state, '$.understanding_passed'), false)
        )
        """
    )


def downgrade() -> None:
    op.execute("UPDATE tutor_sessions SET stage = 'guided_question' WHERE stage = 'understanding'")
