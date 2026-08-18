import os
import re
import httpx
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = "8789484794:AAFhCa9C2I8GfzVpFkzQ2wp1__RPSXj6NsM"
DOWNLOAD_DIR = "./downloads"

PIPED_INSTANCES = [
    "https://pipedapi.kavin.rocks",
    "https://piped-api.privacy.com.de",
    "https://api.piped.projectsegfau.lt",
    "https://pipedapi.drgns.space",
    "https://pipedapi.darkness.services",
    "https://piped-api.codespace.cz",
    "https://pipedapi.in.projectsegfau.lt",
]

os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def extract_video_id(url: str) -> str | None:
    patterns = [
        r"youtu\.be/([a-zA-Z0-9_-]{11})",
        r"youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})",
        r"youtube\.com/shorts/([a-zA-Z0-9_-]{11})",
        r"youtube\.com/embed/([a-zA-Z0-9_-]{11})",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None


async def get_audio_stream(video_id: str) -> tuple[str, str] | None:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; Bot/1.0)",
        "Accept": "application/json",
    }
    async with httpx.AsyncClient(timeout=20, headers=headers, follow_redirects=True) as client:
        for instance in PIPED_INSTANCES:
            try:
                r = await client.get(f"{instance}/streams/{video_id}")
                if r.status_code != 200:
                    print(f"[SKIP] {instance} → {r.status_code}")
                    continue

                data = r.json()
                if "error" in data:
                    print(f"[SKIP] {instance} → error: {data['error']}")
                    continue

                title = data.get("title", "audio")
                audio_streams = data.get("audioStreams", [])
                if not audio_streams:
                    continue

                # Ưu tiên m4a (mp4a), fallback webm/opus
                best = None
                for s in audio_streams:
                    mime = s.get("mimeType", "")
                    if "mp4" in mime or "m4a" in mime:
                        if best is None or s.get("bitrate", 0) > best.get("bitrate", 0):
                            best = s
                if not best:
                    best = max(audio_streams, key=lambda x: x.get("bitrate", 0))

                print(f"[OK] {instance} → {title}")
                return best["url"], title

            except Exception as e:
                print(f"[ERR] {instance} → {e}")
                continue
    return None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎵 Gửi link YouTube, mình download thành audio!\n"
        "Hỗ trợ: youtube.com/watch, youtu.be, youtube.com/shorts"
    )


async def download_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    video_id = extract_video_id(url)

    if not video_id:
        await update.message.reply_text("❌ Link YouTube không hợp lệ.")
        return

    msg = await update.message.reply_text("⏳ Đang tìm stream...")

    result = await get_audio_stream(video_id)
    if not result:
        await msg.edit_text(
            "❌ Không lấy được stream từ tất cả servers.\n"
            "Thử lại sau vài phút hoặc dùng link khác."
        )
        return

    stream_url, title = result
    await msg.edit_text(f"⬇️ Đang tải: *{title}*", parse_mode="Markdown")

    ext = "m4a"
    if "webm" in stream_url or "opus" in stream_url:
        ext = "ogg"

    filepath = os.path.join(DOWNLOAD_DIR, f"{video_id}.{ext}")

    try:
        async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
            async with client.stream("GET", stream_url) as r:
                r.raise_for_status()
                with open(filepath, "wb") as f:
                    async for chunk in r.aiter_bytes(chunk_size=16384):
                        f.write(chunk)

        file_size = os.path.getsize(filepath)
        if file_size > 50 * 1024 * 1024:  # 50MB limit Telegram
            await msg.edit_text("❌ File quá lớn (>50MB), Telegram không cho upload.")
            return

        await msg.edit_text(f"✅ Xong: *{title}*", parse_mode="Markdown")

        with open(filepath, "rb") as audio_file:
            await update.message.reply_audio(
                audio=audio_file,
                title=title,
                performer="YouTube",
                filename=f"{title}.{ext}",
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
