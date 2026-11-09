import datetime
import uuid
from sqlalchemy import Column, String, Integer, Float, Text, DateTime
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class VideoRecord(Base):
    __tablename__ = "video_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    gdrive_file_id = Column(String(128), unique=True, index=True, nullable=False)
    file_name = Column(String(255), nullable=False)
    file_size = Column(Integer, default=0)
    file_hash = Column(String(64), index=True, nullable=True) # SHA-256
    mime_type = Column(String(64), default="video/mp4")
    duration_seconds = Column(Float, nullable=True)
    resolution = Column(String(32), nullable=True)
    local_path = Column(String(512), nullable=True)
    thumbnail_path = Column(String(512), nullable=True)
    
    # Status: PENDING, DOWNLOADING, ANALYZING, READY_TO_POST, POSTING, PUBLISHED, FAILED, SKIPPED
    status = Column(String(32), default="PENDING", index=True)
    
    # AI Results
    ai_analysis = Column(Text, nullable=True) # JSON containing transcript, scenes, summary, tone, audience
    caption_title = Column(String(255), nullable=True)
    caption_body = Column(Text, nullable=True)
    hashtags = Column(Text, nullable=True)
    
    # Meta / Facebook Reels
    facebook_page_id = Column(String(128), nullable=True)
    facebook_video_id = Column(String(128), nullable=True)
    facebook_post_id = Column(String(128), nullable=True)
    facebook_reel_url = Column(String(512), nullable=True)
    
    retry_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    published_at = Column(DateTime, nullable=True)


class SystemLog(Base):
    __tablename__ = "system_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    level = Column(String(16), default="INFO") # INFO, WARNING, ERROR, SUCCESS
    category = Column(String(32), default="SYSTEM") # DRIVE, AI, FACEBOOK, WORKER, SYSTEM
    message = Column(Text, nullable=False)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key = Column(String(64), primary_key=True)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
