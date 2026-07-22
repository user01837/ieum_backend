from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func, Boolean
from sqlalchemy.orm import relationship
from app.db.database import Base

class Knowledge(Base):
    __tablename__ = "knowledge"

    knowledge_id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("task.task_id"), nullable=True)
    department_code = Column(String(10), ForeignKey("DEPARTMENT.department_code"), nullable=True)
    title = Column(String(200), nullable=False)
    category_code = Column(String(10), nullable=True)
    summary = Column(Text, nullable=True)
    warning_note = Column(Text, nullable=True)
    scope_code = Column(String(10), nullable=True)
    created_by = Column(String(50), ForeignKey("user.user_id"), nullable=True)
    updated_by = Column(String(50), ForeignKey("user.user_id"), nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    logs = relationship("KnowledgeLog", back_populates="knowledge", cascade="all, delete-orphan")
    attachments = relationship("KnowledgeAttachment", back_populates="knowledge", cascade="all, delete-orphan")

class KnowledgeAttachment(Base):
    __tablename__ = "knowledge_attachment"

    attachment_id = Column(Integer, primary_key=True, autoincrement=True)
    knowledge_id = Column(Integer, ForeignKey("knowledge.knowledge_id"), nullable=False)
    file_url = Column(String(500), nullable=False)
    file_name = Column(String(255), nullable=True)
    uploaded_by = Column(String(50), ForeignKey("user.user_id"), nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)
    uploaded_at = Column(DateTime, default=func.now(), nullable=False)

    knowledge = relationship("Knowledge", back_populates="attachments")

class KnowledgeLog(Base):
    __tablename__ = "knowledge_log"

    log_id = Column(Integer, primary_key=True, autoincrement=True)
    knowledge_id = Column(Integer, ForeignKey("knowledge.knowledge_id"), nullable=False)
    user_id = Column(String(50), ForeignKey("user.user_id"), nullable=True)
    content = Column(Text, nullable=True)
    updated_by = Column(String(50), ForeignKey("user.user_id"), nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    knowledge = relationship("Knowledge", back_populates="logs")

class KnowledgeLogTag(Base):
    __tablename__ = "knowledge_log_tag"

    log_tag_id = Column(Integer, primary_key=True, autoincrement=True)
    log_id = Column(Integer, ForeignKey("knowledge_log.log_id"), nullable=False)
    tag_id = Column(Integer, ForeignKey("knowledge_tag.tag_id"), nullable=False)

class KnowledgeTag(Base):
    __tablename__ = "knowledge_tag"

    tag_id = Column(Integer, primary_key=True, autoincrement=True)
    department_code = Column(String(10), ForeignKey("DEPARTMENT.department_code"), nullable=True)
    name = Column(String(50), nullable=False)
    created_by = Column(String(50), ForeignKey("user.user_id"), nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)