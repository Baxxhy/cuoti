"""Add exams without rewriting any original teaching/learning row."""
from alembic import op
revision='0014_examinations'
down_revision='0013_teaching_insights'
branch_labels=depends_on=None
def upgrade():
 from sczx_business.exam_models import BankQuestion,QuestionVersion,ExamPaper,PaperVersion,ClassExam,ExamSubmission,ExamGradeAudit,EquationProgress
 for model in [BankQuestion,QuestionVersion,ExamPaper,PaperVersion,ClassExam,ExamSubmission,ExamGradeAudit,EquationProgress]:model.__table__.create(op.get_bind(),checkfirst=True)
def downgrade():raise RuntimeError('考试原始答卷与审计不可自动删除；请先备份并恢复到独立旧库。')
