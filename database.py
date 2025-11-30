import os
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, JSON, Integer, create_engine
from sqlalchemy.orm import relationship, declarative_base, sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

# Load environment
from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./bot_gpt.db")

# Setup
Base = declarative_base()
engine = create_async_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Dependency
async def get_db():
    async with SessionLocal() as session:
        yield session

# Helper
def new_id():
    return str(uuid.uuid4())

# MODELS
class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, default=new_id)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="user", cascade="all, delete-orphan")


class Conversation(Base):
    __tablename__ = "conversations"
    
    id = Column(String, primary_key=True, default=new_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    mode = Column(String, default="open")
    title = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    total_tokens = Column(Integer, default=0)
    
    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    documents = relationship("Document", secondary="conversation_documents", back_populates="conversations")


class Message(Base):
    __tablename__ = "messages"
    
    id = Column(String, primary_key=True, default=new_id)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False)
    role = Column(String) 
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    tokens = Column(Integer, default=0)
    
    conversation = relationship("Conversation", back_populates="messages")


class Document(Base):
    __tablename__ = "documents"
    
    id = Column(String, primary_key=True, default=new_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    filename = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="documents")
    conversations = relationship("Conversation", secondary="conversation_documents", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    
    id = Column(String, primary_key=True, default=new_id)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(JSON)  # List of floats
    
    document = relationship("Document", back_populates="chunks")


class ConversationDocument(Base):
    __tablename__ = "conversation_documents"
    
    id = Column(String, primary_key=True, default=new_id)
    conversation_id = Column(String, ForeignKey("conversations.id"))
    document_id = Column(String, ForeignKey("documents.id"))


# Initialize database
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
