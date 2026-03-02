# TanjAI (แทนใจ) — Google Workspace Voice AI

A real-time voice AI sales assistant for Tangerine Company, powered by OpenAI's Realtime API.

---

## Project Structure

```
tanjai/
├── main.py              # FastAPI backend + WebSocket bridge
├── static/
│   └── index.html       # Frontend UI (voice + chat)
├── requirements.txt
├── .env.example
└── .env                 # Your secrets (git-ignored)
```

---

## Setup

### 1. Clone & install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and add your OpenAI API key:

```
OPENAI_API_KEY=sk-your-key-here
```

### 3. Run

```bash
python main.py
```

Open your browser at **http://localhost:8000**

---

## How It Works

```
Browser ──(WebSocket)──▶ FastAPI ──(WebSocket)──▶ OpenAI Realtime API
   ▲                                                        │
   └────────────────── Audio + Text ◀──────────────────────┘
```

1. **Browser** captures mic audio via `getUserMedia` and sends PCM16 chunks to FastAPI over WebSocket.
2. **FastAPI** acts as a bridge — forwarding audio to OpenAI Realtime API and streaming responses back.
3. **OpenAI** handles VAD (Voice Activity Detection), transcription (Whisper), and LLM response generation.
4. **Audio responses** are streamed back as PCM16 and played in real-time via the Web Audio API.

---

## Agent Configuration

- **Name:** TanjAI (แทนใจ)
- **Model:** `gpt-4o-realtime-preview-2024-12-17`
- **Voice:** `alloy`
- **Role:** Google Workspace Sales, Tangerine Company
- **Languages:** Thai + English (auto-detects from user input)

To change the agent personality, edit the `SYSTEM_PROMPT` constant in `main.py`.

---

## Features

- 🎙️ **Full-duplex voice** — speak and listen simultaneously
- 📝 **Live transcription** — see what you and TanjAI say in real time
- 💬 **Text fallback** — type messages if voice isn't available
- 📜 **Conversation history** — side panel shows full session log
- 🔄 **Auto-reconnect** — WebSocket reconnects on disconnect
- 🎨 **Bilingual UI** — Thai/English interface

---

## Notes

- Requires microphone permission in the browser
- The OpenAI Realtime API uses VAD (server-side) to detect when you stop speaking
- PCM16 audio at 24kHz is used for both input and output
