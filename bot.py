import os
import re
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.constants import ParseMode

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8345172518:AAHahPKnJZwKZ-SIp97vBtNyMyyRXZ-Gw7M`")
RAPID_API_KEY = os.environ.get("RAPID_API_KEY", "YOUR_RAPIDAPI_KEY_HERE")

# ─────────────────────────────────────────
#  MAIN KEYBOARD
# ─────────────────────────────────────────
def get_main_keyboard():
    keyboard = [
        [KeyboardButton("🎬 YouTube Details"), KeyboardButton("⬇️ YT Downloader")],
        [KeyboardButton("📸 Instagram Downloader"), KeyboardButton("🎵 TikTok Downloader")],
        [KeyboardButton("🖼️ Remove Background"), KeyboardButton("ℹ️ Help")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

# ─────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────
def is_youtube_url(text):
    pattern = r'(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)[\w\-]+'
    return re.search(pattern, text)

def is_instagram_url(text):
    return re.search(r'(https?://)?(www\.)?instagram\.com/', text)

def is_tiktok_url(text):
    return re.search(r'(https?://)?(www\.|vm\.)?tiktok\.com/', text)

def extract_youtube_id(url):
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([\w\-]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def mono(text):
    """Wrap text in monospace for easy copy"""
    return f"`{text}`"

# ─────────────────────────────────────────
#  YOUTUBE DETAILS
# ─────────────────────────────────────────
async def fetch_youtube_details(video_id: str):
    url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return {
                "title": data.get("title", "N/A"),
                "author": data.get("author_name", "N/A"),
                "thumbnail": data.get("thumbnail_url", f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"),
            }
    except Exception as e:
        logger.error(f"YT details error: {e}")
    return None

async def handle_youtube_details(update: Update, url: str):
    msg = await update.message.reply_text("⏳ Fetching YouTube details...")
    video_id = extract_youtube_id(url)
    if not video_id:
        await msg.edit_text("❌ Invalid YouTube URL.")
        return

    data = await fetch_youtube_details(video_id)
    thumbnail_url = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"

    if data:
        caption = (
            f"🎬 *YouTube Video Details*\n\n"
            f"📌 *Title:*\n{mono(data['title'])}\n\n"
            f"👤 *Channel:*\n{mono(data['author'])}\n\n"
            f"🔗 *Video ID:*\n{mono(video_id)}\n\n"
            f"🖼️ *Thumbnail URL:*\n{mono(thumbnail_url)}\n\n"
            f"🔗 *Video URL:*\n{mono(url)}"
        )
        try:
            await update.message.reply_photo(
                photo=thumbnail_url,
                caption=caption,
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception:
            await update.message.reply_text(caption, parse_mode=ParseMode.MARKDOWN)
        await msg.delete()
    else:
        await msg.edit_text("❌ Could not fetch details. Check the URL.")

# ─────────────────────────────────────────
#  YOUTUBE DOWNLOADER  (via RapidAPI)
# ─────────────────────────────────────────
async def handle_youtube_download(update: Update, url: str):
    msg = await update.message.reply_text("⏳ Fetching download links...")
    video_id = extract_youtube_id(url)
    if not video_id:
        await msg.edit_text("❌ Invalid YouTube URL.")
        return

    # Using y2mate / yt-download API on RapidAPI
    api_url = "https://youtube-mp36.p.rapidapi.com/dl"
    headers = {
        "X-RapidAPI-Key": RAPID_API_KEY,
        "X-RapidAPI-Host": "youtube-mp36.p.rapidapi.com"
    }
    try:
        r = requests.get(api_url, headers=headers, params={"id": video_id}, timeout=15)
        data = r.json()
        if data.get("status") == "ok":
            link = data.get("link", "N/A")
            title = data.get("title", "N/A")
            text = (
                f"🎵 *YouTube MP3 Download*\n\n"
                f"📌 *Title:*\n{mono(title)}\n\n"
                f"⬇️ *Download Link:*\n{mono(link)}"
            )
            await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
            await msg.delete()
            return
    except Exception as e:
        logger.error(f"YT download error: {e}")

    # Fallback: provide direct links
    text = (
        f"⬇️ *YouTube Download Links*\n\n"
        f"🔗 *Video ID:* {mono(video_id)}\n\n"
        f"Use these sites to download:\n"
        f"• {mono('https://ssyoutube.com/watch?v=' + video_id)}\n"
        f"• {mono('https://y2mate.com')}\n"
        f"• {mono('https://savefrom.net')}"
    )
    await msg.edit_text(text, parse_mode=ParseMode.MARKDOWN)

# ─────────────────────────────────────────
#  INSTAGRAM DOWNLOADER
# ─────────────────────────────────────────
async def handle_instagram_download(update: Update, url: str):
    msg = await update.message.reply_text("⏳ Fetching Instagram media...")

    api_url = "https://instagram-downloader-download-instagram-videos-stories.p.rapidapi.com/index"
    headers = {
        "X-RapidAPI-Key": RAPID_API_KEY,
        "X-RapidAPI-Host": "instagram-downloader-download-instagram-videos-stories.p.rapidapi.com"
    }
    try:
        r = requests.get(api_url, headers=headers, params={"url": url}, timeout=15)
        data = r.json()
        media_url = data.get("media", data.get("url", None))
        if media_url:
            text = (
                f"📸 *Instagram Download*\n\n"
                f"⬇️ *Media URL:*\n{mono(media_url)}\n\n"
                f"_Click the link to download_"
            )
            await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
            await msg.delete()
            return
    except Exception as e:
        logger.error(f"Instagram error: {e}")

    text = (
        f"📸 *Instagram Downloader*\n\n"
        f"Use this site:\n"
        f"• {mono('https://snapinsta.app')}\n"
        f"• {mono('https://instasave.io')}\n\n"
        f"🔗 *Your URL:*\n{mono(url)}"
    )
    await msg.edit_text(text, parse_mode=ParseMode.MARKDOWN)

# ─────────────────────────────────────────
#  TIKTOK DOWNLOADER
# ─────────────────────────────────────────
async def handle_tiktok_download(update: Update, url: str):
    msg = await update.message.reply_text("⏳ Fetching TikTok video...")

    api_url = "https://tiktok-downloader-download-tiktok-videos-without-watermark.p.rapidapi.com/index"
    headers = {
        "X-RapidAPI-Key": RAPID_API_KEY,
        "X-RapidAPI-Host": "tiktok-downloader-download-tiktok-videos-without-watermark.p.rapidapi.com"
    }
    try:
        r = requests.get(api_url, headers=headers, params={"url": url}, timeout=15)
        data = r.json()
        video_url = None
        if isinstance(data, dict):
            video_url = data.get("video", data.get("url", None))
        if video_url:
            text = (
                f"🎵 *TikTok Download (No Watermark)*\n\n"
                f"⬇️ *Video URL:*\n{mono(video_url)}"
            )
            await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
            await msg.delete()
            return
    except Exception as e:
        logger.error(f"TikTok error: {e}")

    text = (
        f"🎵 *TikTok Downloader*\n\n"
        f"Use these sites:\n"
        f"• {mono('https://snaptik.app')}\n"
        f"• {mono('https://ssstik.io')}\n\n"
        f"🔗 *Your URL:*\n{mono(url)}"
    )
    await msg.edit_text(text, parse_mode=ParseMode.MARKDOWN)

# ─────────────────────────────────────────
#  REMOVE BACKGROUND
# ─────────────────────────────────────────
async def handle_remove_bg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        msg = await update.message.reply_text("⏳ Removing background...")
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        file_bytes = await file.download_as_bytearray()

        remove_bg_key = os.environ.get("REMOVE_BG_API_KEY", "")
        if not remove_bg_key:
            await msg.edit_text(
                "🖼️ *Remove Background*\n\n"
                "Set `REMOVE_BG_API_KEY` env var to enable.\n"
                "Get free key at:\n"
                f"{mono('https://www.remove.bg/api')}",
                parse_mode=ParseMode.MARKDOWN
            )
            return

        try:
            r = requests.post(
                "https://api.remove.bg/v1.0/removebg",
                files={"image_file": ("image.jpg", bytes(file_bytes), "image/jpeg")},
                data={"size": "auto"},
                headers={"X-Api-Key": remove_bg_key},
                timeout=30
            )
            if r.status_code == 200:
                await update.message.reply_document(
                    document=r.content,
                    filename="removed_bg.png",
                    caption="✅ Background removed!"
                )
                await msg.delete()
            else:
                await msg.edit_text(f"❌ Error: {r.status_code} - {r.text[:200]}")
        except Exception as e:
            await msg.edit_text(f"❌ Error: {str(e)[:200]}")
    else:
        await update.message.reply_text(
            "🖼️ *Remove Background*\n\nPlease send a photo/image to remove its background.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_main_keyboard()
        )

# ─────────────────────────────────────────
#  COMMAND HANDLERS
# ─────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (
        f"👋 *Welcome {user.first_name}!*\n\n"
        f"🤖 I am your *All-in-One Media Bot*\n\n"
        f"*What I can do:*\n"
        f"🎬 Extract YouTube video details\n"
        f"⬇️ Download YouTube videos/audio\n"
        f"📸 Download Instagram videos/reels\n"
        f"🎵 Download TikTok without watermark\n"
        f"🖼️ Remove image background\n\n"
        f"*Just paste a link or use buttons below!*"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=get_main_keyboard())

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"📖 *How to use this bot:*\n\n"
        f"1️⃣ *YouTube Details* → Paste YT link → get title, thumbnail, description\n"
        f"2️⃣ *YT Downloader* → Paste YT link → get download link\n"
        f"3️⃣ *Instagram* → Paste IG reel/post link\n"
        f"4️⃣ *TikTok* → Paste TikTok link\n"
        f"5️⃣ *Remove BG* → Send any photo\n\n"
        f"💡 *Tip:* All details shown in monospace — tap to copy!\n\n"
        f"🔧 *Commands:*\n"
        f"/start - Restart bot\n"
        f"/help - This message\n"
        f"/ytdetails <url> - YouTube details\n"
        f"/ytdownload <url> - YT download\n"
        f"/igdownload <url> - Instagram\n"
        f"/ttdownload <url> - TikTok\n"
        f"/removebg - Remove background (send photo)"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=get_main_keyboard())

# ─────────────────────────────────────────
#  STATE TRACKING for button modes
# ─────────────────────────────────────────
user_mode = {}  # user_id -> mode

async def handle_keyboard_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    if text == "🎬 YouTube Details":
        user_mode[user_id] = "yt_details"
        await update.message.reply_text(
            "🎬 *YouTube Details Extractor*\n\nPaste a YouTube link:",
            parse_mode=ParseMode.MARKDOWN
        )
    elif text == "⬇️ YT Downloader":
        user_mode[user_id] = "yt_download"
        await update.message.reply_text(
            "⬇️ *YouTube Downloader*\n\nPaste a YouTube link:",
            parse_mode=ParseMode.MARKDOWN
        )
    elif text == "📸 Instagram Downloader":
        user_mode[user_id] = "ig_download"
        await update.message.reply_text(
            "📸 *Instagram Downloader*\n\nPaste an Instagram post/reel/story link:",
            parse_mode=ParseMode.MARKDOWN
        )
    elif text == "🎵 TikTok Downloader":
        user_mode[user_id] = "tt_download"
        await update.message.reply_text(
            "🎵 *TikTok Downloader*\n\nPaste a TikTok video link:",
            parse_mode=ParseMode.MARKDOWN
        )
    elif text == "🖼️ Remove Background":
        user_mode[user_id] = "remove_bg"
        await update.message.reply_text(
            "🖼️ *Remove Background*\n\nSend a photo/image:",
            parse_mode=ParseMode.MARKDOWN
        )
    elif text == "ℹ️ Help":
        await help_command(update, context)
    else:
        # Handle URLs sent in any mode or auto-detect
        await handle_url_message(update, context)

async def handle_url_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = update.effective_user.id
    mode = user_mode.get(user_id, "auto")

    # Auto-detect
    if is_youtube_url(text):
        if mode == "yt_download":
            await handle_youtube_download(update, text)
        else:
            await handle_youtube_details(update, text)
    elif is_instagram_url(text):
        await handle_instagram_download(update, text)
    elif is_tiktok_url(text):
        await handle_tiktok_download(update, text)
    else:
        if mode == "yt_details":
            await update.message.reply_text("❌ That doesn't look like a YouTube link. Try again.")
        elif mode == "yt_download":
            await update.message.reply_text("❌ That doesn't look like a YouTube link. Try again.")
        elif mode == "ig_download":
            await handle_instagram_download(update, text)
        elif mode == "tt_download":
            await handle_tiktok_download(update, text)
        else:
            await update.message.reply_text(
                "❓ Please paste a valid YouTube / Instagram / TikTok link, or use the buttons below.",
                reply_markup=get_main_keyboard()
            )

async def handle_photo_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    mode = user_mode.get(user_id, "auto")
    if mode == "remove_bg" or update.message.photo:
        await handle_remove_bg(update, context)

# ─────────────────────────────────────────
#  DIRECT COMMANDS
# ─────────────────────────────────────────
async def cmd_ytdetails(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        await handle_youtube_details(update, " ".join(context.args))
    else:
        user_mode[update.effective_user.id] = "yt_details"
        await update.message.reply_text("🎬 Send YouTube URL:")

async def cmd_ytdownload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        await handle_youtube_download(update, " ".join(context.args))
    else:
        user_mode[update.effective_user.id] = "yt_download"
        await update.message.reply_text("⬇️ Send YouTube URL:")

async def cmd_igdownload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        await handle_instagram_download(update, " ".join(context.args))
    else:
        user_mode[update.effective_user.id] = "ig_download"
        await update.message.reply_text("📸 Send Instagram URL:")

async def cmd_ttdownload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        await handle_tiktok_download(update, " ".join(context.args))
    else:
        user_mode[update.effective_user.id] = "tt_download"
        await update.message.reply_text("🎵 Send TikTok URL:")

async def cmd_removebg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_mode[update.effective_user.id] = "remove_bg"
    await update.message.reply_text("🖼️ Send a photo to remove background:")

# ─────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("ytdetails", cmd_ytdetails))
    app.add_handler(CommandHandler("ytdownload", cmd_ytdownload))
    app.add_handler(CommandHandler("igdownload", cmd_igdownload))
    app.add_handler(CommandHandler("ttdownload", cmd_ttdownload))
    app.add_handler(CommandHandler("removebg", cmd_removebg))

    app.add_handler(MessageHandler(filters.PHOTO, handle_photo_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_keyboard_buttons))

    logger.info("Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
