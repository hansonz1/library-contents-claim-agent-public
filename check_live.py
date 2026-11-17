"""Check a Gemini Live connection and optionally request one synthetic reply."""

import argparse
import asyncio
import os
from contextlib import asynccontextmanager


class LiveCheckError(ValueError):
    """A diagnostic message safe to display without exposing credentials."""


@asynccontextmanager
async def open_live(transcribe: bool, *, transcribe_input: bool = False, manual_activity: bool = False):
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise LiveCheckError("GEMINI_API_KEY is missing. Set it in the terminal that starts FastAPI.")

    from google import genai
    from google.genai import types

    options = types.HttpOptions(
        base_url="https://generativelanguage.googleapis.com",
        api_version="v1beta",
    )
    async with genai.Client(
        api_key=key, vertexai=False, http_options=options
    ).aio as client:
        config = {"response_modalities": ["AUDIO"]}
        if transcribe:
            config["output_audio_transcription"] = {}
        if transcribe_input:
            config["input_audio_transcription"] = {}
        if manual_activity:
            config["realtime_input_config"] = {
                "automatic_activity_detection": {"disabled": True}
            }
        async with client.live.connect(model="gemini-3.8-live", config=config) as session:
            yield session


async def check_live(request_reply: bool = False, image: bytes | None = None, inventory: bool = False) -> str | None:
    from google.genai import types

    async with asyncio.timeout(30 if request_reply else 15), open_live(request_reply) as session:
        if request_reply:
            prompt = "Reply with exactly: Ready to scan."
            if image is None:
                await session.send_realtime_input(text=prompt)
            else:
                if inventory:
                    prompt = (
                        "List each visible physical book once, from left to right. "
                        "Return a numbered list with one spine title per line. "
                        "Keep the original language and any visible volume marker. "
                        "Use [unreadable] for a visible book whose title you cannot read. "
                        "Do not guess titles or include books outside the photo."
                    )
                else:
                    prompt = (
                        "Read one clearly visible title from a book spine. "
                        "If none is readable, describe one visible detail without "
                        "guessing a title. Then give one concrete instruction for "
                        "moving the phone camera or adjusting the lighting so the "
                        "spine lettering is easier to read in the next photo."
                    )
                await session.send_client_content(
                    turns=types.Content(
                        role="user",
                        parts=[
                            types.Part.from_bytes(data=image, mime_type="image/jpeg"),
                            types.Part.from_text(text=prompt),
                        ],
                    ),
                    turn_complete=True,
                )
            transcript = []
            async for message in session.receive():
                content = message.server_content
                if content and content.output_transcription:
                    transcript.append(content.output_transcription.text or "")
            reply = "".join(transcript).strip()
            if not reply:
                raise LiveCheckError("Gemini Live completed the turn without a transcript.")
            return reply

async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reply", action="store_true", help="Request one test reply.")
    args = parser.parse_args()
    from websockets.exceptions import InvalidStatus

    try:
        reply = await check_live(args.reply)
    except LiveCheckError as error:
        raise SystemExit(str(error)) from None
    except InvalidStatus as error:
        raise SystemExit(
            f"Gemini Live handshake rejected (HTTP {error.response.status_code})."
        ) from None
    except Exception as error:
        raise SystemExit(f"Gemini Live check failed ({type(error).__name__}).") from None
    print(f"Gemini Live transcript: {reply}" if args.reply else "Gemini Live handshake OK")


if __name__ == "__main__":
    asyncio.run(main())
