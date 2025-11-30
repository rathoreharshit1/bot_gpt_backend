from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import List, Optional
from PyPDF2 import PdfReader
from io import BytesIO

# Import from other files
from database import (
    get_db, init_db, User, Conversation, Message, 
    Document, DocumentChunk, ConversationDocument, new_id
)
from llm_service import LLMService, RAGService

# Initialize FastAPI
app = FastAPI(title="BOT GPT API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    await init_db()

# SCHEMAS
class UserCreate(BaseModel):
    name: str
    email: str

class ConversationCreate(BaseModel):
    user_id: str
    first_message: str
    mode: str = "open"

class MessageCreate(BaseModel):
    content: str


# USER ROUTES
@app.post("/users")
async def create_user(data: UserCreate, db: AsyncSession = Depends(get_db)):
    # Check if exists
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(400, "Email already exists")
    
    user = User(id=new_id(), name=data.name, email=data.email)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    return {"id": user.id, "name": user.name, "email": user.email}

@app.get("/users")
async def list_users(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User))
    users = result.scalars().all()
    
    return {
        "users": [
            {"id": u.id, "name": u.name, "email": u.email}
            for u in users
        ]
    }


# CONVERSATION ROUTES
@app.post("/conversations")
async def create_conversation(data: ConversationCreate, db: AsyncSession = Depends(get_db)):
    # Create conversation
    title = data.first_message[:50] + ("..." if len(data.first_message) > 50 else "")
    conv = Conversation(
        id=new_id(),
        user_id=data.user_id,
        mode=data.mode,
        title=title
    )
    db.add(conv)
    await db.flush()
    
    # Add user message
    user_msg = Message(
        id=new_id(),
        conversation_id=conv.id,
        role="user",
        content=data.first_message
    )
    db.add(user_msg)
    
    # Get AI response
    llm_messages = [{"role": "user", "content": data.first_message}]
    response = await LLMService.chat(llm_messages)
    
    # Save AI message
    ai_msg = Message(
        id=new_id(),
        conversation_id=conv.id,
        role="assistant",
        content=response["content"],
        tokens=response["tokens"]
    )
    db.add(ai_msg)
    
    conv.total_tokens = response["tokens"]
    await db.commit()
    
    return {
        "conversation_id": conv.id,
        "assistant_response": response["content"],
        "tokens": response["tokens"]
    }

@app.post("/conversations/{conv_id}/messages")
async def add_message(conv_id: str, data: MessageCreate, db: AsyncSession = Depends(get_db)):
    # Get conversation
    result = await db.execute(select(Conversation).where(Conversation.id == conv_id))
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(404, "Conversation not found")
    
    # Save user message
    user_msg = Message(
        id=new_id(),
        conversation_id=conv_id,
        role="user",
        content=data.content
    )
    db.add(user_msg)
    await db.flush()
    
    # Prepare LLM messages
    llm_messages = []
    
    # RAG mode: add document context
    if conv.mode == "rag":
        # Get linked documents
        result = await db.execute(
            select(ConversationDocument).where(ConversationDocument.conversation_id == conv_id)
        )
        doc_links = result.scalars().all()
        doc_ids = [link.document_id for link in doc_links]
        
        if doc_ids:
            chunks = await RAGService.retrieve_chunks(db, doc_ids, data.content)
            if chunks:
                context = "\n\n".join([f"CHUNK {i+1}:\n{c}" for i, c in enumerate(chunks)])
                llm_messages.append({
                    "role": "system",
                    "content": f"Answer based on this context:\n\n{context}"
                })
    
    # Add user message
    llm_messages.append({"role": "user", "content": data.content})
    
    # Get AI response
    response = await LLMService.chat(llm_messages)
    
    # Save AI message
    ai_msg = Message(
        id=new_id(),
        conversation_id=conv_id,
        role="assistant",
        content=response["content"],
        tokens=response["tokens"]
    )
    db.add(ai_msg)
    
    conv.total_tokens += response["tokens"]
    await db.commit()
    
    return {
        "assistant_response": response["content"],
        "tokens": response["tokens"]
    }

@app.get("/conversations")
async def list_conversations(user_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc())
    )
    convs = result.scalars().all()
    
    return {
        "conversations": [
            {
                "id": c.id,
                "mode": c.mode,
                "title": c.title,
                "created_at": str(c.created_at),
                "total_tokens": c.total_tokens
            }
            for c in convs
        ]
    }

@app.get("/conversations/{conv_id}")
async def get_conversation(conv_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Conversation).where(Conversation.id == conv_id))
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(404, "Not found")
    
    return {
        "id": conv.id,
        "mode": conv.mode,
        "title": conv.title,
        "messages": [
            {"role": m.role, "content": m.content, "created_at": str(m.created_at)}
            for m in conv.messages
        ]
    }

@app.delete("/conversations/{conv_id}")
async def delete_conversation(conv_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Conversation).where(Conversation.id == conv_id))
    conv = result.scalar_one_or_none()
    if conv:
        await db.delete(conv)
        await db.commit()
    return {"status": "deleted"}


# DOCUMENT ROUTES
@app.post("/documents/upload")
async def upload_document(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    # Extract text
    content = await file.read()
    
    if file.filename.endswith(".pdf"):
        pdf = PdfReader(BytesIO(content))
        text = "\n".join([page.extract_text() or "" for page in pdf.pages])
    else:
        text = content.decode("utf-8", errors="ignore")
    
    if not text.strip():
        raise HTTPException(400, "No text found")
    
    # Create document
    doc = Document(
        id=new_id(),
        user_id="test-user",  # TODO: use real auth
        filename=file.filename
    )
    db.add(doc)
    await db.flush()
    
    # Chunk and embed
    chunks = RAGService.chunk_text(text)
    
    for i, chunk_text in enumerate(chunks):
        embedding = LLMService.embed(chunk_text)
        
        chunk = DocumentChunk(
            id=new_id(),
            document_id=doc.id,
            content=chunk_text,
            embedding=embedding
        )
        db.add(chunk)
    
    await db.commit()
    
    return {
        "document_id": doc.id,
        "filename": file.filename,
        "chunks": len(chunks)
    }

@app.get("/documents")
async def list_documents(user_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Document).where(Document.user_id == user_id))
    docs = result.scalars().all()
    
    return [
        {
            "id": d.id,
            "filename": d.filename,
            "chunks": len(d.chunks),
            "created_at": str(d.created_at)
        }
        for d in docs
    ]

@app.delete("/documents/{doc_id}")
async def delete_document(doc_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if doc:
        await db.delete(doc)
        await db.commit()
    return {"status": "deleted"}

@app.post("/conversations/{conv_id}/attach_document")
async def attach_document(conv_id: str, document_id: str, db: AsyncSession = Depends(get_db)):
    # Check if already linked
    result = await db.execute(
        select(ConversationDocument).where(
            ConversationDocument.conversation_id == conv_id,
            ConversationDocument.document_id == document_id
        )
    )
    if result.scalar_one_or_none():
        return {"message": "Already attached"}
    
    # Create link
    link = ConversationDocument(
        id=new_id(),
        conversation_id=conv_id,
        document_id=document_id
    )
    db.add(link)
    await db.commit()
    
    return {"message": "Attached successfully"}


@app.get("/")
def root():
    return {"message": "BOT GPT API - Simplified Version"}
