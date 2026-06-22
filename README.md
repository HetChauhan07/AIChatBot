# AI Companion Chatbot

A modern, full-stack AI chatbot application featuring a responsive React frontend and a lightning-fast FastAPI backend powered by Groq's Llama-3 API.

## Features
- **ChatGPT-Style Interface:** Beautiful UI with a left sidebar for chat history, responsive mobile layout, and markdown support for rich text.
- **Blazing Fast AI:** Integrated with Groq's API for near-instantaneous LLM responses.
- **Persistent Sessions:** All chat histories are saved locally using SQLite. The backend automatically summarizes long conversations to conserve context limits.
- **Seamless State Management:** Instantly switch between past conversations without losing context.

## Tech Stack
- **Frontend:** React, Vite, CSS, React-Markdown
- **Backend:** Python, FastAPI, SQLite, Uvicorn
- **AI Provider:** Groq (Llama-3.3-70b-versatile)

## Getting Started

### 1. Backend Setup
```bash
cd backend
pip install -r requirements.txt
```
Create a `.env` file in the `backend` folder and add your Groq API key:
```env
GROQ_API_KEY=gsk_your_key_here
```
Run the server:
```bash
uvicorn main:app --reload --port 8000
```

### 2. Frontend Setup
In a new terminal window:
```bash
cd frontend
npm install
npm run dev
```

Open your browser to `http://localhost:5173` to start chatting!
