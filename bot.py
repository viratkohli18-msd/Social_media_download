import os
import logging
import asyncio
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    CallbackQueryHandler, filters, ContextTypes
)

from modules.cobalt_api import CobaltAPI
from modules.database import Database
from modules.helpers import detect_platform, is_valid_url
from modules.admin_panel import admin_stats, broadcast

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Config
BOT_TOKEN = os.getenv("BOT_TOKEN")
COBALT_API_URL = os.getenv("COBALT_API_URL", "https://api.cobalt.tools/api/json")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Initialize
cobalt = CobaltAPI(COBALT_API_URL)

# ============== COMMAND HANDLERS ==============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command"""
    user = update.effective_user
    db = Database()
    db.add_user(user.id, user.username, user.first_name)
    
    keyboard = [
        [InlineKeyboardButton("📥 Start Download", callback_data="help")],
        [InlineKeyboardButton("📊 My Stats", callback_data="stats")],
        [InlineKeyboardButton("❓ Help", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"🎬 *Hey {user.first_name}!*\n\n"
        f"Main *Cobalt Downloader Bot* hoon! 🚀\n\n"
        f"Mujhe koi bhi video link bhejo:\n"
        f"• YouTube • TikTok • Instagram\n"
        f"• Twitter • Facebook • Reddit\n"
        f"• SoundCloud • Twitch • Vimeo\n\n"
        f"_High quality, no watermark, fast!_",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command"""
    help_text = (
        "📖 *How to use:*\n\n"
        "1️⃣ Video link copy karo (YouTube, TikTok, etc.)\n"
        "2️⃣ Yahan paste karo\n"
        "3️⃣ Main auto-detect karke process karunga\n"
        "4️⃣ Download link mil jayega!\n\n"
        "*Example links:*\n"
        "`https://youtube.com/watch?v=...`\n"
        "`https://tiktok.com/@user/video/...`\n"
        "`https://instagram.com/reel/...`\n\n"
        "*Commands:*\n"
        "/start - Bot shuru karo\n"
        "/stats - Aapki download stats\n"
        "/help - Yeh message\n"
        "/quality - Quality settings\n\n"
        "💡 *Tip:* Group mein bhi use kar sakte ho! Mujhe admin banao aur link auto-detect hoga."
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User stats"""
    user = update.effective_user
    db = Database()
    stats = db.get_stats(user.id)
    
    await update.message.reply_text(
        f"📊 *Your Statistics*\n\n"
        f"👤 Name: {user.first_name}\n"
        f"📥 Total Downloads: `{stats['total_downloads']}`\n"
        f"📅 Joined: {stats['joined_at'][:10] if stats['joined_at'] else 'Today'}\n\n"
        f"Keep downloading! 🚀",
        parse_mode="Markdown"
    )

async def quality_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Quality selection"""
    keyboard = [
        [
            InlineKeyboardButton("144p", callback_data="quality_144"),
            InlineKeyboardButton("360p", callback_data="quality_360"),
        ],
        [
            InlineKeyboardButton("720p HD", callback_data="quality_720"),
            InlineKeyboardButton("1080p FHD", callback_data="quality_1080"),
        ],
        [InlineKeyboardButton("🔊 Audio Only (MP3)", callback_data="quality_audio")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "⚙️ *Select Quality:*\n\n"
        "Default: 1080p\n\n"
        "Note: Audio Only sirf videos ke liye available hai.",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

# ============== MESSAGE HANDLER ==============

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all text messages"""
    message_text = update.message.text.strip()
    user = update.effective_user
    
    # Check if it's a URL
    if not is_valid_url(message_text):
        return  # Ignore non-URLs
    
    # Check if supported platform
    platform = detect_platform(message_text)
    if platform == "unknown":
        await update.message.reply_text(
            "❌ *Unsupported platform!*\n\n"
            "Supported: YouTube, TikTok, Instagram, Twitter, Facebook, Reddit, SoundCloud, Twitch, Vimeo",
            parse_mode="Markdown"
        )
        return
    
    # Show processing message
    processing_msg = await update.message.reply_text(
        f"⏳ Processing *{platform.upper()}* link...\n"
        f"Please wait 10-30 seconds!",
        parse_mode="Markdown"
    )
    
    # Get user preference (default 1080p)
    quality = context.user_data.get("quality", "1080")
    audio_only = context.user_data.get("audio_only", False)
    
    try:
        # Call Cobalt API
        result = await cobalt.download(message_text, quality=quality, audio_only=audio_only)
        
        # Delete processing message
        await processing_msg.delete()
        
        # Log to database
        db = Database()
        status = "success" if result["success"] else "failed"
        db.log_download(user.id, message_text, platform, status, result.get("error"))
        
        if not result["success"]:
            await update.message.reply_text(
                f"❌ *Download Failed*\n\n"
                f"Reason: {result['error']}\n\n"
                f"_Try again later or different link_",
                parse_mode="Markdown"
            )
            return
        
        # Success - Send download options
        keyboard = [
            [InlineKeyboardButton("📥 Download Now", url=result["url"])],
            [InlineKeyboardButton("🔄 Download Audio", callback_data=f"audio_{message_text}")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        file_type = "🎵 Audio" if result["type"] == "audio" else "🎬 Video"
        
        await update.message.reply_text(
            f"✅ *Ready!*\n\n"
            f"📁 {file_type}: `{result['filename']}`\n"
            f"🔗 [Download Link]({result['url']})\n\n"
            f"_Link expires in ~1 hour_",
            parse_mode="Markdown",
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )
        
    except Exception as e:
        logger.error(f"Error: {e}")
        await processing_msg.edit_text("❌ Error occurred! Please try again.")

# ============== CALLBACK HANDLERS ==============

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline buttons"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "help":
        await help_command(update, context)
    elif data == "stats":
        await stats_command(update, context)
    elif data.startswith("quality_"):
        quality = data.split("_")[1]
        if quality == "audio":
            context.user_data["audio_only"] = True
            context.user_data["quality"] = "best"
            await query.edit_message_text("✅ Audio Only mode enabled!")
        else:
            context.user_data["audio_only"] = False
            context.user_data["quality"] = quality
            await query.edit_message_text(f"✅ Quality set to {quality}p!")
    elif data.startswith("audio_"):
        url = data.replace("audio_", "")
        await query.edit_message_text("⏳ Converting to audio... Please wait!")
        
        result = await cobalt.download(url, audio_only=True)
        if result["success"]:
            await query.message.reply_text(
                f"🎵 *Audio Ready!*\n\n[Download MP3]({result['url']})",
                parse_mode="Markdown"
            )
        else:
            await query.edit_message_text("❌ Audio conversion failed!")

# ============== ERROR HANDLER ==============

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors"""
    logger.error(f"Update {update} caused error {context.error}")

# ============== MAIN ==============

def main():
    """Start the bot"""
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("quality", quality_settings))
    application.add_handler(CommandHandler("admin", admin_stats))
    application.add_handler(CommandHandler("broadcast", broadcast))
    
    # Message handlers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Callback handlers
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Error handler
    application.add_error_handler(error_handler)
    
    # Webhook setup (Render ke liye)
    if WEBHOOK_URL:
        port = int(os.environ.get("PORT", 10000))
        application.run_webhook(
            listen="0.0.0.0",
            port=port,
            webhook_url=WEBHOOK_URL
        )
    else:
        # Local development ke liye polling
        application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
