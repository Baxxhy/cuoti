"""Step18 extends existing accounts, classes, lessons and tasks."""
from datetime import datetime
from sqlalchemy import String,Integer,DateTime,JSON,ForeignKey,UniqueConstraint,Text
from sqlalchemy.orm import Mapped,mapped_column
from .database import Base
class LiveClass(Base):
 __tablename__='live_classes'
 id:Mapped[str]=mapped_column(String(40),primary_key=True)
 owner_id:Mapped[str]=mapped_column(ForeignKey('accounts.id'),index=True)
 classroom_id:Mapped[str]=mapped_column(ForeignKey('classrooms.id'),index=True)
 lesson_id:Mapped[str]=mapped_column(ForeignKey('lessons.id'))
 snapshot:Mapped[dict]=mapped_column(JSON)
 status:Mapped[str]=mapped_column(String(20),default='active')
 revision:Mapped[int]=mapped_column(Integer,default=0)
 current_id:Mapped[str|None]=mapped_column(String(40),nullable=True)
 task_id:Mapped[str|None]=mapped_column(ForeignKey('learning_tasks.id'),nullable=True)
 created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
class LivePresence(Base):
 __tablename__='live_presences'
 session_id:Mapped[str]=mapped_column(ForeignKey('live_classes.id'),primary_key=True)
 student_id:Mapped[str]=mapped_column(ForeignKey('accounts.id'),primary_key=True)
 joined_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
class LiveActivity(Base):
 __tablename__='live_activities'
 id:Mapped[str]=mapped_column(String(40),primary_key=True)
 session_id:Mapped[str]=mapped_column(ForeignKey('live_classes.id'),index=True)
 position:Mapped[int]=mapped_column(Integer)
 question:Mapped[dict]=mapped_column(JSON)
 feedback:Mapped[str]=mapped_column(Text,default='')
class LiveAnswer(Base):
 __tablename__='live_answers'
 __table_args__=(UniqueConstraint('activity_id','student_id'),)
 id:Mapped[str]=mapped_column(String(40),primary_key=True)
 activity_id:Mapped[str]=mapped_column(ForeignKey('live_activities.id'))
 student_id:Mapped[str]=mapped_column(ForeignKey('accounts.id'))
 answer:Mapped[str]=mapped_column(Text,default='')
 reason:Mapped[str]=mapped_column(Text,default='')
 revision:Mapped[int]=mapped_column(Integer,default=0)
 submitted_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
 verification:Mapped[dict]=mapped_column(JSON,default=dict)
class TeachingGroupPlan(Base):
 __tablename__='teaching_group_plans'
 id:Mapped[str]=mapped_column(String(40),primary_key=True)
 owner_id:Mapped[str]=mapped_column(ForeignKey('accounts.id'))
 classroom_id:Mapped[str]=mapped_column(ForeignKey('classrooms.id'))
 knowledge_id:Mapped[str]=mapped_column(ForeignKey('knowledge_points.id'))
 groups:Mapped[list]=mapped_column(JSON)
 evidence:Mapped[dict]=mapped_column(JSON)
 published:Mapped[bool]=mapped_column(default=False)
 revision:Mapped[int]=mapped_column(Integer,default=0)
class CommunityShare(Base):
 __tablename__='community_shares'
 id:Mapped[str]=mapped_column(String(40),primary_key=True)
 owner_id:Mapped[str]=mapped_column(ForeignKey('accounts.id'),index=True)
 kind:Mapped[str]=mapped_column(String(20))
 source_id:Mapped[str]=mapped_column(String(40))
 snapshot:Mapped[dict]=mapped_column(JSON)
 active:Mapped[bool]=mapped_column(default=True)
 created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
class CommunityBookmark(Base):
 __tablename__='community_bookmarks'
 share_id:Mapped[str]=mapped_column(ForeignKey('community_shares.id'),primary_key=True)
 owner_id:Mapped[str]=mapped_column(ForeignKey('accounts.id'),primary_key=True)
class CommunityEvent(Base):
 __tablename__='community_events'
 id:Mapped[str]=mapped_column(String(40),primary_key=True)
 share_id:Mapped[str]=mapped_column(ForeignKey('community_shares.id'))
 owner_id:Mapped[str]=mapped_column(ForeignKey('accounts.id'))
 kind:Mapped[str]=mapped_column(String(20))
 data:Mapped[dict]=mapped_column(JSON)
 withdrawn:Mapped[bool]=mapped_column(default=False)
 created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
