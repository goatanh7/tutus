import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp

BOT_TOKEN = "8789484794:AAFhCa9C2I8GfzVpFkzQ2wp1__RPSXj6NsM"
DOWNLOAD_DIR = "./downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎵 Gửi link YouTube, mình download thành MP3!")

async def download_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()

    if "youtube.com" not in url and "youtu.be" not in url:
        await update.message.reply_text("❌ Link YouTube không hợp lệ.")
        return

    msg = await update.message.reply_text("⏳ Đang tải...")

    ydl_opts = {
    "format": "bestaudio",
    "outtmpl": f"{DOWNLOAD_DIR}/%(title)s.%(ext)s",
    "postprocessors": [{
        "key": "FFmpegExtractAudio",
        "preferredcodec": "mp3",
        "preferredquality": "192",
    }],
    "quiet": True,
    "no_warnings": True,
    "extractor_args": {
        "youtube": {
            "player_client": ["android", "web"],
        }
    },
    "http_headers": {
        "User-Agent": "com.google.android.youtube/19.09.37 (Linux; U; Android 11) gzip",
    },
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "audio")
            filename = ydl.prepare_filename(info).rsplit(".", 1)[0] + ".mp3"

        await msg.edit_text(f"✅ Xong: *{title}*", parse_mode="Markdown")

        with open(filename, "rb") as audio_file:
            await update.message.reply_audio(
                audio=audio_file,
                title=title,
                performer="YouTube"
            )

        os.remove(filename)

    except Exception as e:
        await msg.edit_text(f"❌ Lỗi: `{e}`", parse_mode="Markdown")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_audio))
    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
