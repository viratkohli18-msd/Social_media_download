import os
import psycopg2
from datetime import datetime

class Database:
    def __init__(self):
        self.conn = psycopg2.connect(os.getenv("DATABASE_URL"), sslmode='require')
        self._create_tables()
    
    def _create_tables(self):
        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_banned BOOLEAN DEFAULT FALSE,
                total_downloads INTEGER DEFAULT 0
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS downloads (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                url TEXT,
                platform TEXT,
                status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()
        cur.close()
    
    def add_user(self, user_id, username, first_name):
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO users (user_id, username, first_name)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET
                username = EXCLUDED.username,
                first_name = EXCLUDED.first_name
        """, (user_id, username, first_name))
        self.conn.commit()
        cur.close()
    
    def log_download(self, user_id, url, platform, status):
        cur = self.conn.cursor()
        cur.execute("INSERT INTO downloads (user_id, url, platform, status) VALUES (%s, %s, %s, %s)",
                   (user_id, url, platform, status))
        if status == "success":
            cur.execute("UPDATE users SET total_downloads = total_downloads + 1 WHERE user_id = %s", (user_id,))
        self.conn.commit()
        cur.close()
    
    def get_stats(self):
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*), SUM(total_downloads) FROM users")
        users, downloads = cur.fetchone()
        cur.execute("SELECT COUNT(*) FROM downloads WHERE created_at > NOW() - INTERVAL '24 hours'")
        today = cur.fetchone()[0]
        cur.close()
        return {"users": users or 0, "downloads": downloads or 0, "today": today or 0}
    
    def get_all_users(self):
        cur = self.conn.cursor()
        cur.execute("SELECT user_id FROM users WHERE is_banned = FALSE")
        users = [row[0] for row in cur.fetchall()]
        cur.close()
        return users
    
    def ban_user(self, user_id):
        cur = self.conn.cursor()
        cur.execute("UPDATE users SET is_banned = TRUE WHERE user_id = %s", (user_id,))
        self.conn.commit()
        cur.close()
    
    def is_banned(self, user_id):
        cur = self.conn.cursor()
        cur.execute("SELECT is_banned FROM users WHERE user_id = %s", (user_id,))
        result = cur.fetchone()
        cur.close()
        return result[0] if result else False
