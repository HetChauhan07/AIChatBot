"""
AI Companion Chatbot Backend — FastAPI server for a general-purpose AI companion chatbot.

Handles:
- Multi-turn conversations with rolling memory summarization
- Session persistence via SQLite
"""
import os
import sqlite3
import json
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq

# Load .env file (so API key doesn't need to be set in terminal)
load_dotenv()

# ──────────────────────────────────────────────
# App & Config
# ──────────────────────────────────────────────

app = FastAPI(title="ContextChat API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database path — stored alongside the backend
DB_PATH = Path(__file__).parent / "chat.db"

# LLM model — Groq Llama 3 (free, lightning fast)
MODEL_NAME = "llama-3.3-70b-versatile"

# ──────────────────────────────────────────────
# Load Prompts (relative to project root)
# ──────────────────────────────────────────────

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

try:
    SYSTEM_PROMPT = (PROMPTS_DIR / "system_prompt.txt").read_text(encoding="utf-8")
    SUMMARIZATION_PROMPT = (PROMPTS_DIR / "summarization_prompt.txt").read_text(encoding="utf-8")
except FileNotFoundError:
    # Fallbacks for standalone testing
    SYSTEM_PROMPT = "You are a Flowly customer support assistant."
    SUMMARIZATION_PROMPT = "Summarize the conversation."

# ──────────────────────────────────────────────
# Database Setup
# ──────────────────────────────────────────────

def init_db():
    """Create the sessions table if it doesn't exist."""
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            summary TEXT,
            history TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ──────────────────────────────────────────────
# Pydantic Models
# ──────────────────────────────────────────────

class ChatRequest(BaseModel):
    session_id: str
    message: str

class ResetRequest(BaseModel):
    session_id: str

# ──────────────────────────────────────────────
# Session Helpers
# ──────────────────────────────────────────────

def get_session(session_id: str) -> tuple[str, list]:
    """Retrieve the summary and message history for a session."""
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute("SELECT summary, history FROM sessions WHERE session_id=?", (session_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return row[0], json.loads(row[1])
    return "", []

def save_session(session_id: str, summary: str, history: list):
    """Persist the session summary and message history."""
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute('''
        INSERT OR REPLACE INTO sessions (session_id, summary, history)
        VALUES (?, ?, ?)
    ''', (session_id, summary, json.dumps(history)))
    conn.commit()
    conn.close()

# ──────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────

@app.post("/chat")
async def chat(req: ChatRequest):
    """
    Main chat endpoint using Groq.
    """
    # Step 1: Fetch session
    summary, history = get_session(req.session_id)
    history.append({"role": "user", "content": req.message})

    # Step 3: Build system prompt with context
    formatted_system_prompt = (
        SYSTEM_PROMPT
        .replace("{summary}", summary)
        .replace("{recent_messages}", json.dumps(history[-4:], indent=2))
    )

    # Initialize Groq client
    groq_api_key = os.environ.get("GROQ_API_KEY", "")
    client = Groq(api_key=groq_api_key) if groq_api_key else None

    try:
        if not client:
            raise ValueError("No API key configured")

        # Build messages array for Groq (System prompt + last 6 turns)
        messages = [{"role": "system", "content": formatted_system_prompt}]
        for msg in history[-6:]:
            messages.append({"role": msg["role"], "content": msg["content"]})

        response = client.chat.completions.create(
            messages=messages,
            model=MODEL_NAME,
            max_tokens=1024,
        )
        bot_reply = response.choices[0].message.content
    except Exception as e:
        # Fallback for evaluation/demo without a real API key
        if not groq_api_key:
            bot_reply = (
                "I'm a simulated response because no API key was provided. "
                "In production, I would use the conversation context to help you with Flowly."
            )
        else:
            raise HTTPException(status_code=500, detail=str(e))

    # Step 4: Add bot reply to history
    history.append({"role": "assistant", "content": bot_reply})

    # Step 5: Trigger summarization if history gets long (> 4 messages)
    if len(history) > 4:
        summarization_prompt_filled = (
            SUMMARIZATION_PROMPT
            .replace("{previous_summary}", summary)
            .replace("{new_messages}", json.dumps(history[-2:], indent=2))
        )
        try:
            if client:
                summary_response = client.chat.completions.create(
                    messages=[{"role": "user", "content": summarization_prompt_filled}],
                    model=MODEL_NAME,
                    max_tokens=512,
                )
                new_summary = summary_response.choices[0].message.content
            else:
                raise ValueError("No client")
        except Exception:
            # Fallback: append a simple text summary
            new_summary = summary + f"\nUser: {req.message}\nBot: {bot_reply}"
    else:
        new_summary = summary

    # Step 6: Persist
    save_session(req.session_id, new_summary, history)

    return {"response": bot_reply}


@app.post("/reset")
async def reset(req: ResetRequest):
    """Clear a session's conversation history and summary."""
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute("DELETE FROM sessions WHERE session_id=?", (req.session_id,))
    conn.commit()
    conn.close()
    return {"status": "ok"}

@app.get("/sessions")
async def get_sessions():
    """Retrieve a list of all past sessions, ordered by most recent."""
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    # Use rowid to roughly sort by newest first
    c.execute("SELECT session_id, history FROM sessions ORDER BY rowid DESC")
    rows = c.fetchall()
    conn.close()
    
    sessions_list = []
    for row in rows:
        session_id = row[0]
        history = json.loads(row[1])
        # Use the first user message as the title, or a default
        title = "New Chat"
        for msg in history:
            if msg["role"] == "user":
                title = msg["content"][:30] + ("..." if len(msg["content"]) > 30 else "")
                break
        sessions_list.append({"session_id": session_id, "title": title})
        
    return {"sessions": sessions_list}

@app.get("/session/{session_id}")
async def get_session_history(session_id: str):
    """Retrieve the full history of a specific session."""
    _, history = get_session(session_id)
    return {"history": history}
