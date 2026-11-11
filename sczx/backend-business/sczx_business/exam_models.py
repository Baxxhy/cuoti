"""Question/paper versions are append-only; original submissions are never regraded in place."""
from datetime import datetime
from sqlalchemy import String,Integer,JSON,DateTime,ForeignKey,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from .database import Base
class BankQuestion(Base):
 __tablename__='bank_questions'
 id:Mapped[str]=mapped_column(String(40),primary_key=True)
 owner_id:Mapped[str]=mapped_column(ForeignKey('accounts.id'),index=True)
 draft:Mapped[dict]=mapped_column(JSON)
 revision:Mapped[int]=mapped_column(Integer,default=1)
 reviewed:Mapped[bool]=mapped_column(default=False)
class QuestionVersion(Base):
 __tablename__='question_versions'
 __table_args__=(UniqueConstraint('question_id','number'),)
 id:Mapped[str]=mapped_column(String(40),primary_key=True)
 question_id:Mapped[str]=mapped_column(ForeignKey('bank_questions.id'),index=True)
 number:Mapped[int]=mapped_column(Integer)
 data:Mapped[dict]=mapped_column(JSON)
 created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
class ExamPaper(Base):
 __tablename__='exam_papers'
 id:Mapped[str]=mapped_column(String(40),primary_key=True)
 owner_id:Mapped[str]=mapped_column(ForeignKey('accounts.id'),index=True)
 draft:Mapped[dict]=mapped_column(JSON)
 revision:Mapped[int]=mapped_column(Integer,default=1)
 reviewed:Mapped[bool]=mapped_column(default=False)
class PaperVersion(Base):
 __tablename__='paper_versions'
 __table_args__=(UniqueConstraint('paper_id','number'),)
 id:Mapped[str]=mapped_column(String(40),primary_key=True)
 paper_id:Mapped[str]=mapped_column(ForeignKey('exam_papers.id'))
 number:Mapped[int]=mapped_column(Integer)
 data:Mapped[dict]=mapped_column(JSON)
 created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
class ClassExam(Base):
 __tablename__='class_exams'
 id:Mapped[str]=mapped_column(String(40),primary_key=True)
 owner_id:Mapped[str]=mapped_column(ForeignKey('accounts.id'),index=True)
 classroom_id:Mapped[str]=mapped_column(ForeignKey('classrooms.id'))
 version_id:Mapped[str]=mapped_column(ForeignKey('paper_versions.id'))
 starts_at:Mapped[datetime]=mapped_column(DateTime)
 ends_at:Mapped[datetime]=mapped_column(DateTime)
 minutes:Mapped[int]=mapped_column(Integer)
 request_key:Mapped[str]=mapped_column(String(100),unique=True)
 results_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
 review_task_id:Mapped[str|None]=mapped_column(ForeignKey('learning_tasks.id'),nullable=True)
class ExamSubmission(Base):
 __tablename__='exam_submissions'
 __table_args__=(UniqueConstraint('exam_id','student_id'),)
 id:Mapped[str]=mapped_column(String(40),primary_key=True)
 exam_id:Mapped[str]=mapped_column(ForeignKey('class_exams.id'),index=True)
 student_id:Mapped[str]=mapped_column(ForeignKey('accounts.id'),index=True)
 answers:Mapped[dict]=mapped_column(JSON,default=dict)
 revision:Mapped[int]=mapped_column(Integer,default=0)
 started_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
 submitted_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
 automatic:Mapped[dict]=mapped_column(JSON,default=dict)
 grades:Mapped[dict]=mapped_column(JSON,default=dict)
class ExamGradeAudit(Base):
 __tablename__='exam_grade_audits'
 id:Mapped[str]=mapped_column(String(40),primary_key=True)
 submission_id:Mapped[str]=mapped_column(ForeignKey('exam_submissions.id'),index=True)
 actor_id:Mapped[str]=mapped_column(ForeignKey('accounts.id'))
 data:Mapped[dict]=mapped_column(JSON)
 created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
class EquationProgress(Base):
 __tablename__='equation_progress'
 __table_args__=(UniqueConstraint('record_id','question'),)
 id:Mapped[str]=mapped_column(String(40),primary_key=True)
 record_id:Mapped[str]=mapped_column(ForeignKey('student_records.id'))
 question:Mapped[int]=mapped_column(Integer)
 actions:Mapped[list]=mapped_column(JSON,default=list)
 explanation:Mapped[str]=mapped_column(String(6000),default='')
 revision:Mapped[int]=mapped_column(Integer,default=0)
