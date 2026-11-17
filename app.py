import base64
import re
from pathlib import Path

from fastapi import FastAPI, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from check_live import LiveCheckError, check_live, open_live

app = FastAPI()
LOCAL_ORIGIN = "http://127.0.0.1:8000"
MAX_IMAGE_BYTES = 512 * 1024

# Synthetic labels exercise Unicode transport without inventing ground truth.
BOOKS = [
    {"id": f"B{number:03}", "title": title}
    for number, title in enumerate(
        [f"测试书 {i}" for i in range(1, 15)]
        + [f"Test Book {i}" for i in range(1, 14)],
        start=1,
    )
]


@app.get("/")
def home():
    return FileResponse(Path(__file__).with_name("index.html"))


@app.websocket("/ws")
async def inventory(socket: WebSocket):
    await socket.accept()
    try:
        while True:
            command = await socket.receive_text()
            if command == "test_live":
                if socket.headers.get("origin") != LOCAL_ORIGIN:
                    await socket.send_json(
                        {"type": "live_result", "message": "Open http://127.0.0.1:8000 to test Live."}
                    )
                    continue
                try:
                    reply = await check_live(request_reply=True)
                    message = f"Gemini Live transcript: {reply}"
                except LiveCheckError as error:
                    message = str(error)
                except Exception as error:
                    message = f"Gemini Live test failed ({type(error).__name__}). Check the server terminal setup."
                await socket.send_json({"type": "live_result", "message": message})
                continue
            if command != "scan":
                await socket.send_json({"type": "error", "message": "Unknown command"})
                continue
            await socket.send_json(
                {"type": "inventory", "mode": "mock", "books": BOOKS}
            )
    except WebSocketDisconnect:
        return


@app.post("/test-image")
async def test_image(request: Request, inventory: bool = False):
    if request.headers.get("origin") != LOCAL_ORIGIN:
        return {"message": "Open http://127.0.0.1:8000 to test an image."}
    if request.headers.get("content-type") != "image/jpeg":
        return {"message": "Choose a valid image."}
    image = bytearray()
    async for chunk in request.stream():
        if len(image) + len(chunk) > MAX_IMAGE_BYTES:
            return {"message": "Image exceeds 512 KiB."}
        image.extend(chunk)
    if not image.startswith(b"\xff\xd8") or not image.endswith(b"\xff\xd9"):
        return {"message": "Choose a valid JPEG image."}
    try:
        reply = await check_live(request_reply=True, image=bytes(image), inventory=inventory)
    except LiveCheckError as error:
        return {"message": str(error)}
    except Exception as error:
        return {"message": f"Gemini Live image test failed ({type(error).__name__})."}
    return {"message": f"Gemini Live transcript: {reply}"}


@app.get("/measure")
def measurement_page():
    return FileResponse(Path(__file__).with_name("measure.html"))


@app.get("/measure/convert")
def convert_measurement(
    reference_px: float = Query(gt=0, allow_inf_nan=False),
    reference_cm: float = Query(gt=0, allow_inf_nan=False),
    spine_px: float = Query(gt=0, allow_inf_nan=False),
):
    return {"spine_cm": spine_px * (reference_cm / reference_px)}


def extract_sweep_titles(transcript: str) -> list[str]:
    marker = r'\bbook title\b\s*(?:is\b\s*)?[:：,，.。–—-]?\s*'
    titles = re.findall(
        marker + r'(.*?)(?=' + marker + r'|\bunreadable spine\b|$)',
        transcript,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not titles:
        titles = re.findall(
            r'\b(?:the title is|one visible book is)\s+["“]([^"”\n]+)["”]',
            transcript,
            flags=re.IGNORECASE,
        )
    return [
        title for raw in titles[:6]
        if (title := raw.strip(' \t\r\n"“”「」.。;；'))
        and title.casefold() not in {"unreadable", "unknown", "[unreadable]"}
    ]


async def send_voice_turn(session, payload: bytes):
    from google.genai import types

    await session.send_realtime_input(activity_start=types.ActivityStart())
    # 100 ms of 16 kHz mono PCM16 per message.
    for offset in range(0, len(payload), 3200):
        await session.send_realtime_input(
            audio=types.Blob(
                data=payload[offset:offset + 3200],
                mime_type="audio/pcm;rate=16000",
            )
        )
    await session.send_realtime_input(activity_end=types.ActivityEnd())


@app.websocket("/sweep")
async def sweep(socket: WebSocket):
    import asyncio

    if socket.headers.get("origin") != LOCAL_ORIGIN:
        await socket.close(code=1008)
        return
    await socket.accept()

    async def feedback(session, payload, voice):
        from google.genai import types

        if voice:
            await send_voice_turn(session, payload)
        else:
            await session.send_client_content(
                turns=types.Content(role="user", parts=[
                    types.Part.from_bytes(data=payload, mime_type="image/jpeg"),
                    types.Part.from_text(text=(
                        "Use only the latest frame. Report up to six clearly readable spine titles. "
                        'For each use this exact spoken format: Book title: [title]. '
                        'Keep original language and volume markers. Say "Unreadable spine" once '
                        "if any visible spine is unclear. Do not guess titles. If the frame "
                        "needs adjustment, give one short tip before listing titles."
                    )),
                ]),
                turn_complete=True,
            )
        heard, transcript = [], []
        audio = bytearray()
        while True:
            async for event in session.receive():
                if event.data:
                    audio.extend(event.data)
                content = event.server_content
                if content and content.input_transcription:
                    heard.append(content.input_transcription.text or "")
                if content and content.output_transcription:
                    transcript.append(content.output_transcription.text or "")
            # Live may report an idle boundary before the voice reply arrives.
            # The caller's turn timeout bounds the wait for actual output.
            if not voice or audio or "".join(transcript).strip():
                break
        return (
            "".join(heard).strip(),
            "".join(transcript).strip(),
            base64.b64encode(audio).decode("ascii"),
        )

    try:
        async with asyncio.timeout(60), open_live(True, transcribe_input=True, manual_activity=True) as session:
            await socket.send_json({"type": "ready", "supports_voice": True})
            frame_number = 0
            voice_used = False
            while frame_number < 3:
                payload = await socket.receive_bytes()
                voice = payload.startswith(b"PCM:")
                if voice:
                    payload = payload[4:]
                    valid = frame_number == 1 and not voice_used and 0 < len(payload) <= 128_000 and len(payload) % 2 == 0
                    voice_used = True
                else:
                    valid = len(payload) <= MAX_IMAGE_BYTES and payload.startswith(b"\xff\xd8") and payload.endswith(b"\xff\xd9")
                    frame_number += 1
                if not valid:
                    await socket.send_json({"type": "error", "message": "Invalid sweep frame."})
                    return
                reply = asyncio.create_task(
                    asyncio.wait_for(feedback(session, payload, voice), timeout=20)
                )
                incoming = asyncio.create_task(socket.receive())
                try:
                    done, _ = await asyncio.wait({incoming, reply}, return_when=asyncio.FIRST_COMPLETED)
                    if incoming in done:
                        return
                    try:
                        heard, transcript, audio_pcm = reply.result()
                    except TimeoutError:
                        kind = "voice question" if voice else "camera frame"
                        await socket.send_json({
                            "type": "error",
                            "message": f"Gemini did not finish the {kind} within 20 seconds.",
                        })
                        return
                    titles = [] if voice else extract_sweep_titles(transcript)
                    await socket.send_json({
                        "type": "voice_feedback" if voice else "feedback",
                        "frame": frame_number, "heard": heard,
                        "has_transcript": bool(transcript),
                        "audio_pcm": audio_pcm,
                        "titles": titles,
                        "needs_review": not voice and (
                            not titles
                            or "unreadable spine" in transcript.casefold()
                        ),
                        "message": transcript or "No transcript for this frame.",
                    })
                finally:
                    for task in (reply, incoming):
                        task.cancel()
                    await asyncio.gather(reply, incoming, return_exceptions=True)
        await socket.send_json({"type": "done"})
    except WebSocketDisconnect:
        pass
    except Exception as error:
        await socket.send_json({"type": "error", "message": f"Sweep failed ({type(error).__name__})."})
    finally:
        if socket.client_state.name != "DISCONNECTED":
            await socket.close()


@app.post("/test-voice")
async def test_voice(request: Request):
    import asyncio

    if request.headers.get("origin") != LOCAL_ORIGIN:
        return {"error": "Open the local page to test voice."}
    if request.headers.get("content-type") != "audio/pcm":
        return {"error": "Expected microphone PCM audio."}
    pcm = bytearray()
    async for chunk in request.stream():
        if len(pcm) + len(chunk) > 128_000:
            return {"error": "Voice test is limited to four seconds."}
        pcm.extend(chunk)
    if not pcm or len(pcm) % 2:
        return {"error": "No valid microphone audio received."}

    heard, reply = [], []
    audio = bytearray()
    try:
        async with asyncio.timeout(30), open_live(True, transcribe_input=True, manual_activity=True) as session:
            await send_voice_turn(session, bytes(pcm))
            while not (heard and (reply or audio)):
                async for event in session.receive():
                    if event.data:
                        audio.extend(event.data)
                    content = event.server_content
                    if content and content.input_transcription and content.input_transcription.text:
                        heard.append(content.input_transcription.text)
                    if content and content.output_transcription and content.output_transcription.text:
                        reply.append(content.output_transcription.text)
    except TimeoutError:
        if not heard:
            return {"error": "Gemini did not transcribe the microphone clip within 30 seconds."}
    except LiveCheckError as error:
        return {"error": str(error)}
    except Exception as error:
        return {"error": f"Voice test failed ({type(error).__name__})."}

    return {
        "heard": "".join(heard).strip(),
        "reply": "".join(reply).strip(),
        "audio_pcm": base64.b64encode(audio).decode("ascii"),
    }
