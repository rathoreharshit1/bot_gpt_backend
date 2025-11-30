A clean, maintainable RAG chatbot with Groq API.

## Structure 

```
bot-gpt/
├── .env                # Config
├── requirements.txt    # Dependencies
├── database.py        # All database logic
├── llm_service.py     # All LLM & RAG logic
├── api.py             # Complete FastAPI backend
└── app.py             # Streamlit frontend
```

## Setup

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Configure `.env`:**
```
GROQ_API_KEY=your_key_here
DATABASE_URL=sqlite+aiosqlite:///./bot_gpt.db
```

3. **Run backend:**
```bash
uvicorn api:app --reload
```

4. **Run frontend (new terminal):**
```bash
streamlit run app.py
```

## Features

- ✅ Open chat mode (standard AI chat)
- ✅ RAG mode (chat with documents)
- ✅ PDF/TXT upload and processing
- ✅ Conversation history
- ✅ User management
- ✅ Token tracking


## Usage

1. Create/login as a user (sidebar)
2. Start Open Chat or RAG Chat
3. For RAG: Upload a document and attach it
4. Chat with your documents!

## Tech Stack

- FastAPI (backend)
- Streamlit (frontend)
- SQLite (database)
- Groq API (LLM)
- Sentence Transformers (embeddings)
"""