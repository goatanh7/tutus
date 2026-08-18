import os
import httpx
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = "8789484794:AAFhCa9C2I8GfzVpFkzQ2wp1__RPSXj6NsM"
DOWNLOAD_DIR = "./downloads"

# Danh sách Piped instances — fallback nếu 1 cái chết
PIPED_INSTANCES = [
    "https://pipedapi.kavin.rocks",
    "https://piped-api.privacy.com.de",
    "https://api.piped.projectsegfau.lt",
]

os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def extract_video_id(url: str) -> str | None:
    import re
    patterns = [
        r"youtu\.be/([a-zA-Z0-9_-]{11})",
        r"youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})",
        r"youtube\.com/shorts/([a-zA-Z0-9_-]{11})",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None


async def get_audio_stream(video_id: str) -> tuple[str, str] | None:
    """Coba từng Piped instance, trả về (stream_url, title)"""
    async with httpx.AsyncClient(timeout=15) as client:
        for instance in PIPED_INSTANCES:
            try:
                r = await client.get(f"{instance}/streams/{video_id}")
                if r.status_code != 200:
                    continue
                data = r.json()
                title = data.get("title", "audio")

                # Lấy audio stream tốt nhất
                audio_streams = data.get("audioStreams", [])
                if not audio_streams:
                    continue

                # Ưu tiên m4a, fallback webm
                best = None
                for s in audio_streams:
                    if s.get("mimeType", "").startswith("audio/mp4"):
                        best = s
                        break
                if not best:
                    best = audio_streams[0]

                return best["url"], title

            except Exception:
                continue
    return None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎵 Gửi link YouTube, mình download thành MP3!")


async def download_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    video_id = extract_video_id(url)

    if not video_id:
        await update.message.reply_text("❌ Link YouTube không hợp lệ.")
        return

    msg = await update.message.reply_text("⏳ Đang xử lý...")

    result = await get_audio_stream(video_id)
    if not result:
        await msg.edit_text("❌ Không lấy được stream. Thử lại sau!")
        return

    stream_url, title = result
    await msg.edit_text(f"⬇️ Đang tải: *{title}*", parse_mode="Markdown")

    filepath = os.path.join(DOWNLOAD_DIR, f"{video_id}.m4a")

    try:
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            async with client.stream("GET", stream_url) as r:
                r.raise_for_status()
                with open(filepath, "wb") as f:
                    async for chunk in r.aiter_bytes(chunk_size=8192):
                        f.write(chunk)

        await msg.edit_text(f"✅ Xong: *{title}*", parse_mode="Markdown")

        with open(filepath, "rb") as audio_file:
            await update.message.reply_audio(
                audio=audio_file,
                title=title,
                performer="YouTube"
            )

    except Exception as e:
        await msg.edit_text(f"❌ Lỗi tải file: `{e}`", parse_mode="Markdown")

    finally:
        if os.path.exists(filepath):
            os.remove(filepath)


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_audio))
    print("Bot running...")
    app.run_polling()


if __name__ == "__main__":
    main()
