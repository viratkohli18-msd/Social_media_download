from flask import Flask, jsonify
import os

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({
        "status": "🤖 Bot is running",
        "service": "Cobalt Downloader Bot",
        "timestamp": "active"
    })

@app.route('/health')
def health():
    return jsonify({"status": "ok"})

@app.route('/stats')
def stats():
    from database import Database
    db = Database()
    stats = db.get_stats()
    return jsonify(stats)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
