import os
import asyncio
import aiohttp
import threading
import time
from flask import Flask, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ========== CONFIG ==========
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", 10000))
ADMIN_IDS = [8217006573]  # 👈 YAHAN APNA TELEGRAM USER ID DALO

# ========== WEB SERVER (Keep Render Awake) ==========
app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({"status": "🤖 Bot Running", "service": "Cobalt Downloader"})

@app.route('/health')
def health():
    return jsonify({"status": "ok"})

def run_server():
    app.run(host="0.0.0.0", port=PORT)

def keep_alive():
    """Har 5 min mein khud ko ping karo"""
    while True:
        time.sleep(300)
        try:
            import requests
            requests.get(f"http://localhost:{PORT}/health")
        except:
            pass

# ========== HELPERS ==========
def detect_platform(url: str) -> str:
    platforms = {
        "youtube": ["youtube.com", "youtu.be"],
        "tiktok": ["tiktok.com"],
        "instagram": ["instagram.com"],
        "twitter": ["twitter.com", "x.com"],
        "facebook": ["facebook.com"],
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
            async with session.post("https://api.cobalt.tools/api/json", json=payload, timeout=30) as resp:
                return await resp.json()
    except Exception as e:
        return {"status": "error", "text": str(e)}

# ========== COMMANDS ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"🎬 *Hey {user.first_name}!*\n\n"
        f"Mujhe video link bhejo:\n"
        f"• YouTube • TikTok • Instagram\n"
        f"• Twitter • Facebook • Reddit\n\n"
        f"Example: `https://youtube.com/watch?v=...`",
        parse_mode="Markdown"
    )

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📊 Stats feature coming soon!")

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Admin only!")
        return
    await update.message.reply_text("🔐 Admin Panel\n\n/broadcast - Message all users")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    if not context.args:
        await update.message.reply_text("Usage: /broadcast message")
        return
    await update.message.reply_text(f"📢 Broadcast: {' '.join(context.args)}")

# ========== MESSAGE HANDLER ==========
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    
    if not url.startswith("http"):
        return
    
    platform = detect_platform(url)
    if platform == "Unknown":
        await update.message.reply_text("❌ Unsupported link!")
        return
    
    msg = await update.message.reply_text(f"⏳ Processing {platform}...")
    
    result = await download_video(url)
    
    if result.get("status") in ["redirect", "tunnel"]:
        link = result.get("url")
        keyboard = [[InlineKeyboardButton("📥 Download Now", url=link)]]
        await msg.edit_text(
            "✅ *Ready!*\n\nClick to download:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    else:
        error = result.get("text", "Error")
        await msg.edit_text(f"❌ Failed: {error}")

# ========== MAIN ==========
def main():
    # Web server start
    threading.Thread(target=run_server, daemon=True).start()
    threading.Thread(target=keep_alive, daemon=True).start()
    print("🌐 Server started on port", PORT)
    
    # Bot setup
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Commands
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("admin", admin))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 Bot is running...")
    
    # POLLING MODE (Simple & Working)
    application.run_polling()

if __name__ == "__main__":
    main()
