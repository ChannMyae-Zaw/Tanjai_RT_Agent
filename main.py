import asyncio
import json
import os
import websockets
import base64
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uvicorn
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="TanjAI - Voice AI Assistant")

app.mount("/static", StaticFiles(directory="static"), name="static")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
REALTIME_URL = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-12-17"

SYSTEM_PROMPT = """You are TanjAI (แทนใจ), a professional and friendly Google Workspace sales representative from Tangerine Company.

Your role:
- Sell and promote Google Workspace products (Gmail, Drive, Docs, Sheets, Meet, Calendar, etc.)
- Help businesses understand the value of Google Workspace for their organization
- Answer questions about pricing, plans (Business Starter, Business Standard, Business Plus, Enterprise)
- Handle objections gracefully and professionally
- Schedule demos and follow-ups when appropriate

Your personality:
- Warm, professional, and enthusiastic about Google Workspace
- Speak naturally in a conversational tone
- You can speak both Thai and English — match the language the customer uses
- Always be helpful, never pushy

Company: Tangerine Company — an authorized Google Workspace reseller in Thailand.

Key selling points:
- Google Workspace integrates all productivity tools seamlessly
- Enterprise-grade security and 99.9% uptime SLA
- Easy migration from other platforms (Microsoft 365, etc.)
- Competitive pricing with Tangerine's local support
- Thai-language support available

Always greet warmly and ask how you can help the customer today."""


@app.get("/", response_class=HTMLResponse)
async def root():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.websocket("/ws")
async def websocket_endpoint(client_ws: WebSocket):
    await client_ws.accept()
    print("Client connected")

    if not OPENAI_API_KEY:
        await client_ws.send_json({"type": "error", "message": "OPENAI_API_KEY not set"})
        await client_ws.close()
        return

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "OpenAI-Beta": "realtime=v1",
    }

    try:
        async with websockets.connect(REALTIME_URL, additional_headers=headers) as openai_ws:
            print("Connected to OpenAI Realtime API")

            # Initialize session
            session_config = {
                "type": "session.update",
                "session": {
                    "modalities": ["text", "audio"],
                    "instructions": SYSTEM_PROMPT,
                    "voice": "alloy",
                    "input_audio_format": "pcm16",
                    "output_audio_format": "pcm16",
                    "input_audio_transcription": {
                        "model": "whisper-1"
                    },
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": 0.5,
                        "prefix_padding_ms": 300,
                        "silence_duration_ms": 800
                    },
                    "temperature": 0.8,
                    "max_response_output_tokens": 4096
                }
            }
            await openai_ws.send(json.dumps(session_config))

            async def receive_from_client():
                """Receive messages from browser client and forward to OpenAI"""
                try:
                    while True:
                        data = await client_ws.receive_text()
                        message = json.loads(data)
                        msg_type = message.get("type")

                        if msg_type == "audio_chunk":
                            openai_msg = {
                                "type": "input_audio_buffer.append",
                                "audio": message["audio"]
                            }
                            await openai_ws.send(json.dumps(openai_msg))

                        elif msg_type == "audio_commit":
                            await openai_ws.send(json.dumps({"type": "input_audio_buffer.commit"}))

                        elif msg_type == "text_message":
                            await openai_ws.send(json.dumps({
                                "type": "conversation.item.create",
                                "item": {
                                    "type": "message",
                                    "role": "user",
                                    "content": [{"type": "input_text", "text": message["text"]}]
                                }
                            }))
                            await openai_ws.send(json.dumps({"type": "response.create"}))

                        elif msg_type == "clear_audio":
                            await openai_ws.send(json.dumps({"type": "input_audio_buffer.clear"}))

                except WebSocketDisconnect:
                    print("Client disconnected")
                except Exception as e:
                    print(f"Error receiving from client: {e}")

            async def receive_from_openai():
                """Receive messages from OpenAI and forward to browser client"""
                try:
                    async for raw_message in openai_ws:
                        message = json.loads(raw_message)
                        msg_type = message.get("type")

                        if msg_type == "session.created":
                            await client_ws.send_json({"type": "session.created"})

                        elif msg_type == "session.updated":
                            await client_ws.send_json({"type": "session.updated"})

                        elif msg_type == "response.audio.delta":
                            await client_ws.send_json({
                                "type": "audio_delta",
                                "delta": message.get("delta", "")
                            })

                        elif msg_type == "response.audio_transcript.delta":
                            await client_ws.send_json({
                                "type": "transcript_delta",
                                "delta": message.get("delta", ""),
                                "role": "assistant"
                            })

                        elif msg_type == "response.audio_transcript.done":
                            await client_ws.send_json({
                                "type": "transcript_done",
                                "transcript": message.get("transcript", ""),
                                "role": "assistant"
                            })

                        elif msg_type == "conversation.item.input_audio_transcription.completed":
                            await client_ws.send_json({
                                "type": "user_transcript_done",
                                "transcript": message.get("transcript", ""),
                                "role": "user"
                            })

                        elif msg_type == "input_audio_buffer.speech_started":
                            await client_ws.send_json({"type": "speech_started"})
                            # Cancel AI response so user can barge in
                            try:
                                await openai_ws.send(json.dumps({"type": "response.cancel"}))
                            except:
                                pass
                            # Cancel current AI response so user can interrupt
                            await openai_ws.send(json.dumps({"type": "response.cancel"}))

                        elif msg_type == "response.cancelled":
                            await client_ws.send_json({"type": "response_cancelled"})

                        elif msg_type == "input_audio_buffer.speech_stopped":
                            await client_ws.send_json({"type": "speech_stopped"})

                        elif msg_type == "response.created":
                            await client_ws.send_json({"type": "response_started"})

                        elif msg_type == "response.done":
                            await client_ws.send_json({"type": "response_done"})

                        elif msg_type == "error":
                            error_msg = message.get("error", {}).get("message", "Unknown error")
                            # Ignore harmless cancellation errors
                            if "no active response" in error_msg.lower() or "cancellation" in error_msg.lower():
                                pass
                            else:
                                await client_ws.send_json({
                                    "type": "error",
                                    "message": error_msg
                                })

                except Exception as e:
                    print(f"Error receiving from OpenAI: {e}")
                    try:
                        await client_ws.send_json({"type": "error", "message": str(e)})
                    except:
                        pass

            await asyncio.gather(
                receive_from_client(),
                receive_from_openai(),
                return_exceptions=True
            )

    except Exception as e:
        print(f"WebSocket error: {e}")
        try:
            await client_ws.send_json({"type": "error", "message": str(e)})
        except:
            pass


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)