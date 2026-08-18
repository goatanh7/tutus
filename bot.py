import os
import re
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp

BOT_TOKEN = "8789484794:AAFhCa9C2I8GfzVpFkzQ2wp1__RPSXj6NsM"
DOWNLOAD_DIR = "./downloads"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def extract_video_id(url: str) -> str | None:
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


def download_audio_sync(url: str, output_dir: str) -> tuple[str, str] | None:
    """Download audio tanpa FFmpeg — chọn format audio native."""
    ydl_opts = {
        # Ưu tiên m4a (không cần convert), fallback webm
        "format": "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio",
        "outtmpl": os.path.join(output_dir, "%(id)s.%(ext)s"),
        # KHÔNG có postprocessors — không cần FFmpeg
        "quiet": False,
        "no_warnings": False,
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web"],
                "player_skip": ["configs"],
            }
        },
        "http_headers": {
            "User-Agent": "com.google.android.youtube/19.09.37 (Linux; U; Android 11) gzip",
        },
        "geo_bypass": True,
        "nocheckcertificate": True,
        "retries": 5,
        "fragment_retries": 5,
        "socket_timeout": 30,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        video_id = info.get("id")
        title = info.get("title", "audio")
        ext = info.get("ext", "webm")
        filename = os.path.join(output_dir, f"{video_id}.{ext}")
        return filename, title


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎵 Gửi link YouTube, mình download thành audio!\n"
        "Hỗ trợ: youtube.com, youtu.be, youtube.com/shorts"
    )


async def download_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()

    if not extract_video_id(url):
        await update.message.reply_text("❌ Link YouTube không hợp lệ.")
        return

    msg = await update.message.reply_text("⏳ Đang tải...")

    filepath = None
    try:
        loop = asyncio.get_event_loop()
        filepath, title = await loop.run_in_executor(
            None, download_audio_sync, url, DOWNLOAD_DIR
        )

        if not os.path.exists(filepath):
            await msg.edit_text("❌ Tải xong nhưng không tìm thấy file.")
            return

        file_size = os.path.getsize(filepath)
        if file_size > 50 * 1024 * 1024:
            await msg.edit_text("❌ File quá lớn (>50MB).")
            return

        await msg.edit_text(f"✅ Xong: *{title}*", parse_mode="Markdown")

        with open(filepath, "rb") as f:
            await update.message.reply_audio(
                audio=f,
                title=title,
                performer="YouTube",
            )

    except Exception as e:
        print(f"[ERR] {e}")
        await msg.edit_text(f"❌ Lỗi: `{e}`", parse_mode="Markdown")

    finally:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_audio))
    print("Bot running...")
    app.run_polling()


if __name__ == "__main__":
    main()
