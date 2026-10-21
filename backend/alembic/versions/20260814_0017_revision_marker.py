"""Retain the deployed revision marker after removing school collaboration.

The student-only schema does not create collaboration tables. Existing retired
records are left untouched; upgrading or downgrading this marker never deletes
student data or reinstates removed features.
"""

revision = "20260814_0017"
down_revision = "20260813_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
