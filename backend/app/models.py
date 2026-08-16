from datetime import datetime,timezone
from sqlalchemy import Boolean,DateTime,Float,ForeignKey,JSON,String,Text
from sqlalchemy.orm import Mapped,mapped_column
from app.db import Base
def now(): return datetime.now(timezone.utc)
class Project(Base):
    __tablename__="projects"
    id:Mapped[int]=mapped_column(primary_key=True); name:Mapped[str]=mapped_column(String(200)); domain:Mapped[str]=mapped_column(String(500)); repo:Mapped[str]=mapped_column(String(300),default=""); branch:Mapped[str]=mapped_column(String(100),default="main"); goal:Mapped[str]=mapped_column(String(100),default="organic_traffic"); language:Mapped[str]=mapped_column(String(20),default="en"); dry_run:Mapped[bool]=mapped_column(Boolean,default=True); active:Mapped[bool]=mapped_column(Boolean,default=True); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class Secret(Base):
    __tablename__="secrets"
    id:Mapped[int]=mapped_column(primary_key=True); project_id:Mapped[int]=mapped_column(ForeignKey("projects.id")); provider:Mapped[str]=mapped_column(String(80)); ciphertext:Mapped[str]=mapped_column(Text())
class Metric(Base):
    __tablename__="metrics"
    id:Mapped[int]=mapped_column(primary_key=True); project_id:Mapped[int]=mapped_column(ForeignKey("projects.id")); source:Mapped[str]=mapped_column(String(40)); date:Mapped[str]=mapped_column(String(20)); metric:Mapped[str]=mapped_column(String(80)); value:Mapped[float]=mapped_column(Float); dimensions:Mapped[dict]=mapped_column(JSON,default=dict)
class Opportunity(Base):
    __tablename__="opportunities"
    id:Mapped[int]=mapped_column(primary_key=True); project_id:Mapped[int]=mapped_column(ForeignKey("projects.id")); kind:Mapped[str]=mapped_column(String(80)); title:Mapped[str]=mapped_column(String(500)); evidence:Mapped[dict]=mapped_column(JSON,default=dict); score:Mapped[float]=mapped_column(Float,default=0); status:Mapped[str]=mapped_column(String(40),default="open")
class Decision(Base):
    __tablename__="decisions"
    id:Mapped[int]=mapped_column(primary_key=True); project_id:Mapped[int]=mapped_column(ForeignKey("projects.id")); agent:Mapped[str]=mapped_column(String(80)); decision:Mapped[str]=mapped_column(Text()); evidence:Mapped[dict]=mapped_column(JSON,default=dict)
class Run(Base):
    __tablename__="runs"
    id:Mapped[int]=mapped_column(primary_key=True); project_id:Mapped[int]=mapped_column(ForeignKey("projects.id")); status:Mapped[str]=mapped_column(String(40),default="running"); state:Mapped[dict]=mapped_column(JSON,default=dict); error:Mapped[str]=mapped_column(Text,default=""); started_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now); finished_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
class Experiment(Base):
    __tablename__="experiments"
    id:Mapped[int]=mapped_column(primary_key=True); project_id:Mapped[int]=mapped_column(ForeignKey("projects.id")); hypothesis:Mapped[str]=mapped_column(Text()); action:Mapped[str]=mapped_column(Text()); baseline:Mapped[dict]=mapped_column(JSON,default=dict); outcome:Mapped[dict]=mapped_column(JSON,default=dict); status:Mapped[str]=mapped_column(String(40),default="running")
class AuditLog(Base):
    __tablename__="audit_logs"
    id:Mapped[int]=mapped_column(primary_key=True); project_id:Mapped[int]=mapped_column(ForeignKey("projects.id")); actor:Mapped[str]=mapped_column(String(80)); action:Mapped[str]=mapped_column(String(120)); details:Mapped[dict]=mapped_column(JSON,default=dict)
class Deployment(Base):
    __tablename__="deployments"
    id:Mapped[int]=mapped_column(primary_key=True); project_id:Mapped[int]=mapped_column(ForeignKey("projects.id")); commit_sha:Mapped[str]=mapped_column(String(100),default=""); deployment_id:Mapped[str]=mapped_column(String(200),default=""); url:Mapped[str]=mapped_column(String(1000),default=""); status:Mapped[str]=mapped_column(String(40),default="created"); snapshot:Mapped[dict]=mapped_column(JSON,default=dict)
