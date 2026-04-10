import os
import asyncio
import aiohttp
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from database import Database

# ========== CONFIG ==========
BOT_TOKEN = os.getenv("BOT_TOKEN")
COBALT_API = "https://api.cobalt.tools/api/json"
ADMIN_IDS = [8217006573]  # 👈 YAHAN APNA TELEGRAM USER ID DALO
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", 10000))

# ========== WEB SERVER ==========
app = Flask(__name__)

@app.route('/')
def home():
    return {"status": "🤖 Bot Active", "service": "Cobalt Downloader"}

@app.route('/health')
def health():
    return {"status": "ok"}

def run_server():
    app.run(host="0.0.0.0", port=PORT)

# ========== BOT FUNCTIONS ==========
def detect_platform(url: str) -> str:
    platforms = {
        "youtube": ["youtube.com", "youtu.be"],
        "tiktok": ["tiktok.com"],
        "instagram": ["instagram.com"],
        "twitter": ["twitter.com", "x.com"],
        "facebook": ["facebook.com", "fb.watch"],
        "reddit": ["reddit.com"]
    }
    for name, domains in platforms.items():
        if any(d in url.lower() for d in domains):
            return name.title()
    return "Unknown"

async def download_video(url: str):
    try:
        async with aiohttp.ClientSession() as session:
            payload = {"url": url, "vQuality": "1080", "isAudioOnly": False}
            async with session.post(COBALT_API, json=payload, timeout=30) as resp:
                return await resp.json()
    except Exception as e:
        return {"status": "error", "text": str(e)}

# ========== USER COMMANDS ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db = Database()
    
    # Check banned
    if db.is_banned(user.id):
        await update.message.reply_text("⛔ You are banned!")
        return
    
    db.add_user(user.id, user.username, user.first_name)
    
    await update.message.reply_text(
        f"🎬 *Hey {user.first_name}!*\n\n"
        f"Send me any video link:\n"
        f"• YouTube • TikTok • Instagram\n"
        f"• Twitter • Facebook • Reddit\n\n"
        f"_High quality downloads_",
        parse_mode="Markdown"
    )

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db = Database()
    
    # User stats
    cur = db.conn.cursor()
    cur.execute("SELECT total_downloads FROM users WHERE user_id = %s", (user.id,))
    result = cur.fetchone()
    my_downloads = result[0] if result else 0
    cur.close()
    
    # Global stats
    global_stats = db.get_stats()
    
    await update.message.reply_text(
        f"📊 *Your Stats*\n"
        f"Downloads: `{my_downloads}`\n\n"
        f"🌍 *Global Stats*\n"
        f"Users: `{global_stats['users']}`\n"
        f"Total: `{global_stats['downloads']}`\n"
        f"Today: `{global_stats['today']}`",
        parse_mode="Markdown"
    )

# ========== ADMIN COMMANDS ==========
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    
    db = Database()
    stats = db.get_stats()
    
    await update.message.reply_text(
        f"🔐 *Admin Panel*\n\n"
        f"👥 Total Users: `{stats['users']}`\n"
        f"📥 Total Downloads: `{stats['downloads']}`\n"
        f"📅 Today: `{stats['today']}`\n\n"
        f"Commands:\n"
        f"/broadcast - Message all users\n"
        f"/ban - Ban a user",
        parse_mode="Markdown"
    )

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /broadcast Your message here")
        return
    
    message = " ".join(context.args)
    db = Database()
    users = db.get_all_users()
    
    sent = 0
    failed = 0
    
    for user_id in users:
        try:
            await context.bot.send_message(user_id, f"📢 *Broadcast:*\n\n{message}", parse_mode="Markdown")
            sent += 1
            await asyncio.sleep(0.1)  # Rate limit
        except:
            failed += 1
    
    await update.message.reply_text(f"✅ Sent: {sent}\n❌ Failed: {failed}")

async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /ban 123456789")
        return
    
    try:
        user_id = int(context.args[0])
        db = Database()
        db.ban_user(user_id)
        await update.message.reply_text(f"✅ Banned user {user_id}")
    except:
        await update.message.reply_text("❌ Invalid user ID")

# ========== MESSAGE HANDLER ==========
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    url = update.message.text.strip()
    
    # Check banned
    db = Database()
    if db.is_banned(user.id):
        return
    
    if not url.startswith("http"):
        return
    
    platform = detect_platform(url)
    if platform == "Unknown":
        await update.message.reply_text("❌ Unsupported platform!")
        return
    
    msg = await update.message.reply_text(f"⏳ Processing {platform}...")
    
    result = await download_video(url)
    
    status = "failed"
    if result.get("status") in ["redirect", "tunnel"]:
        status = "success"
        link = result.get("url")
        keyboard = [[InlineKeyboardButton("📥 Download", url=link)]]
        
        await msg.edit_text(
            "✅ *Ready!*\n\nClick to download:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    else:
        error = result.get("text", "Error")
        await msg.edit_text(f"❌ Failed: {error}")
    
    db.log_download(user.id, url, platform, status)

# ========== MAIN ==========
def main():
    # Start web server in thread
    server_thread = Thread(target=run_server)
    server_thread.daemon = True
    server_thread.start()
    print("🌐 Web server started")
    
    # Start bot
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("admin", admin_stats))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("ban", ban))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Webhook or Polling
    if WEBHOOK_URL:
        print(f"🚀 Starting webhook on port {PORT}")
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            webhook_url=WEBHOOK_URL
        )
    else:
        print("🤖 Starting polling...")
        application.run_polling()

if __name__ == "__main__":
    main()
