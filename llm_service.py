import os
import math
import httpx
from typing import List
from sentence_transformers import SentenceTransformer

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.1-8b-instant"

# Load embedding model once
embed_model = SentenceTransformer('all-MiniLM-L6-v2')


class LLMService:
    """Handles all LLM operations"""
    
    @staticmethod
    async def chat(messages: List[dict], max_tokens: int = 300) -> dict:
        """Send chat request to Groq"""
        payload = {
            "model": MODEL,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.7
        }
        
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(GROQ_URL, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        
        return {
            "content": data["choices"][0]["message"]["content"],
            "tokens": data.get("usage", {}).get("total_tokens", 0)
        }
    
    @staticmethod
    def embed(text: str) -> List[float]:
        """Generate embeddings using local model"""
        if len(text) > 8000:
            text = text[:8000]
        return embed_model.encode(text, convert_to_tensor=False).tolist()


class RAGService:
    """Handles document chunking and retrieval"""
    
    @staticmethod
    def chunk_text(text: str, size: int = 500) -> List[str]:
        """Split text into chunks"""
        words = text.split()
        chunks = []
        current = []
        
        for word in words:
            current.append(word)
            if len(current) >= size:
                chunks.append(" ".join(current))
                current = []
        
        if current:
            chunks.append(" ".join(current))
        
        return chunks
    
    @staticmethod
    def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """Calculate similarity between vectors"""
        dot = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))
        return dot / (norm1 * norm2) if norm1 and norm2 else 0.0
    
    @staticmethod
    async def retrieve_chunks(db, document_ids: List[str], query: str, top_k: int = 3) -> List[str]:
        """Retrieve relevant chunks for RAG"""
        from sqlalchemy import select
        from database import DocumentChunk
        
        if not document_ids:
            return []
        
        # Embed query
        query_embedding = LLMService.embed(query)
        
        # Get all chunks
        stmt = select(DocumentChunk).where(DocumentChunk.document_id.in_(document_ids))
        result = await db.execute(stmt)
        chunks = result.scalars().all()
        
        if not chunks:
            return []
        
        # Score and sort
        scored = []
        for chunk in chunks:
            similarity = RAGService.cosine_similarity(query_embedding, chunk.embedding)
            scored.append((similarity, chunk.content))
        
        scored.sort(reverse=True, key=lambda x: x[0])
        
        return [content for _, content in scored[:top_k]]
