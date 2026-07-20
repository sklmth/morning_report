"""会话历史 + 用户认证持久化：标准库 sqlite3，零额外依赖。

表结构：
    users(id, username, pass_hash, salt, created_at)
    sessions(token, user_id, created_at, expires_at)
    conversations(id, user_id, title, model, created_at, updated_at)
    messages(id, conv_id, role, content, sources_json, model, created_at)

说明：
    - 会话按 user_id 隔离，每个用户只能看到/操作自己的会话。
      文档知识库仍为全员共享（企业知识库定位）。
    - 密码用 hashlib.pbkdf2_hmac + 每用户随机 salt 哈希，不存明文。
    - 登录令牌（session token）用 secrets 生成，带过期时间，支持登出。
    - 所有写操作经 api 层的 _WRITE_LOCK 串行化；这里每次开新连接，
      配合 WAL 模式，读写并发安全。
"""
import hashlib
import json
import secrets
import sqlite3
import time
import uuid
from contextlib import contextmanager

import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id         TEXT PRIMARY KEY,
    username   TEXT NOT NULL UNIQUE,
    pass_hash  TEXT NOT NULL,
    salt       TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token      TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL,
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS conversations (
    id         TEXT PRIMARY KEY,
    user_id    TEXT,
    title      TEXT NOT NULL DEFAULT '新对话',
    model      TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id           TEXT PRIMARY KEY,
    conv_id      TEXT NOT NULL,
    role         TEXT NOT NULL,
    content      TEXT NOT NULL DEFAULT '',
    sources_json TEXT,
    model        TEXT,
    created_at   REAL NOT NULL,
    FOREIGN KEY (conv_id) REFERENCES conversations(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conv_id, created_at);
"""

# 索引单独建：idx_conv_user 依赖 conversations.user_id 列，必须在“补列迁移”
# 之后执行，否则旧库(无 user_id)会在建索引时报 no such column。
_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(user_id, updated_at);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
"""


def init_db() -> None:
    with _conn() as c:
        # 1) 建表（IF NOT EXISTS，不含依赖 user_id 的索引）
        c.executescript(_SCHEMA)
        # 2) 幂等迁移：旧库 conversations 无 user_id 列时补上（值为 NULL）
        cols = {r["name"] for r in c.execute("PRAGMA table_info(conversations)")}
        if "user_id" not in cols:
            c.execute("ALTER TABLE conversations ADD COLUMN user_id TEXT")
        # 3) 补列后再建依赖 user_id 的索引
        c.executescript(_INDEXES)


@contextmanager
def _conn():
    conn = sqlite3.connect(str(config.CHAT_DB))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _now() -> float:
    return time.time()


def _new_id() -> str:
    return uuid.uuid4().hex


# ---- 用户 / 密码 ----------------------------------------------------------

def _hash_pw(password: str, salt: str) -> str:
    """PBKDF2-HMAC-SHA256 哈希，260000 轮。"""
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                             bytes.fromhex(salt), 260_000)
    return dk.hex()


def create_user(username: str, password: str) -> dict | None:
    """创建用户。用户名已存在时返回 None。"""
    uid = _new_id()
    salt = secrets.token_hex(16)
    ph = _hash_pw(password, salt)
    now = _now()
    try:
        with _conn() as c:
            c.execute(
                "INSERT INTO users(id,username,pass_hash,salt,created_at)"
                " VALUES(?,?,?,?,?)",
                (uid, username, ph, salt, now),
            )
    except sqlite3.IntegrityError:
        return None  # username UNIQUE 冲突
    return {"id": uid, "username": username, "created_at": now}


def verify_user(username: str, password: str) -> dict | None:
    """校验用户名/密码，成功返回用户，失败返回 None。"""
    with _conn() as c:
        row = c.execute(
            "SELECT id,username,pass_hash,salt FROM users WHERE username=?",
            (username,),
        ).fetchone()
    if not row:
        return None
    expected = row["pass_hash"]
    got = _hash_pw(password, row["salt"])
    if not secrets.compare_digest(expected, got):
        return None
    return {"id": row["id"], "username": row["username"]}


# ---- 登录会话（token） ----------------------------------------------------

def create_session(user_id: str) -> str:
    """签发登录令牌，返回 token。"""
    token = secrets.token_urlsafe(32)
    now = _now()
    expires = now + config.SESSION_TTL_DAYS * 86400
    with _conn() as c:
        c.execute(
            "INSERT INTO sessions(token,user_id,created_at,expires_at)"
            " VALUES(?,?,?,?)",
            (token, user_id, now, expires),
        )
    return token


def user_for_token(token: str) -> dict | None:
    """按 token 取用户；过期或无效返回 None。"""
    if not token:
        return None
    with _conn() as c:
        row = c.execute(
            "SELECT s.user_id, s.expires_at, u.username"
            " FROM sessions s JOIN users u ON u.id=s.user_id"
            " WHERE s.token=?",
            (token,),
        ).fetchone()
        if not row:
            return None
        if row["expires_at"] < _now():
            c.execute("DELETE FROM sessions WHERE token=?", (token,))
            return None
    return {"id": row["user_id"], "username": row["username"]}


def delete_session(token: str) -> None:
    with _conn() as c:
        c.execute("DELETE FROM sessions WHERE token=?", (token,))


# ---- 会话 ----------------------------------------------------------------

def create_conversation(user_id: str, title: str = "新对话",
                        model: str | None = None) -> dict:
    cid = _new_id()
    now = _now()
    with _conn() as c:
        c.execute(
            "INSERT INTO conversations(id,user_id,title,model,created_at,updated_at)"
            " VALUES(?,?,?,?,?,?)",
            (cid, user_id, title, model, now, now),
        )
    return {"id": cid, "title": title, "model": model,
            "created_at": now, "updated_at": now, "message_count": 0}


def list_conversations(user_id: str) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT c.id, c.title, c.model, c.created_at, c.updated_at,"
            " (SELECT COUNT(*) FROM messages m WHERE m.conv_id=c.id) AS message_count"
            " FROM conversations c WHERE c.user_id=? ORDER BY c.updated_at DESC",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_conversation(cid: str, user_id: str) -> dict | None:
    """取会话及消息；仅当会话属于该用户时返回，否则 None（归属校验）。"""
    with _conn() as c:
        row = c.execute(
            "SELECT id,title,model,created_at,updated_at FROM conversations"
            " WHERE id=? AND user_id=?",
            (cid, user_id),
        ).fetchone()
        if not row:
            return None
        msgs = c.execute(
            "SELECT id,role,content,sources_json,model,created_at"
            " FROM messages WHERE conv_id=? ORDER BY created_at, id",
            (cid,),
        ).fetchall()
    conv = dict(row)
    conv["messages"] = [
        {
            "id": m["id"], "role": m["role"], "content": m["content"],
            "sources": json.loads(m["sources_json"]) if m["sources_json"] else [],
            "model": m["model"], "created_at": m["created_at"],
        }
        for m in msgs
    ]
    return conv


def rename_conversation(cid: str, user_id: str, title: str) -> bool:
    with _conn() as c:
        cur = c.execute(
            "UPDATE conversations SET title=?, updated_at=? WHERE id=? AND user_id=?",
            (title, _now(), cid, user_id),
        )
        return cur.rowcount > 0


def delete_conversation(cid: str, user_id: str) -> bool:
    with _conn() as c:
        # 归属校验：仅当会话属于该用户时才删
        owned = c.execute(
            "SELECT 1 FROM conversations WHERE id=? AND user_id=?", (cid, user_id)
        ).fetchone()
        if not owned:
            return False
        c.execute("DELETE FROM messages WHERE conv_id=?", (cid,))
        cur = c.execute("DELETE FROM conversations WHERE id=? AND user_id=?",
                        (cid, user_id))
        return cur.rowcount > 0


def touch_conversation(cid: str, model: str | None = None) -> None:
    with _conn() as c:
        if model:
            c.execute("UPDATE conversations SET updated_at=?, model=? WHERE id=?",
                      (_now(), model, cid))
        else:
            c.execute("UPDATE conversations SET updated_at=? WHERE id=?",
                      (_now(), cid))


def owns(cid: str, user_id: str) -> bool:
    """该会话是否属于该用户。"""
    with _conn() as c:
        return c.execute(
            "SELECT 1 FROM conversations WHERE id=? AND user_id=?", (cid, user_id)
        ).fetchone() is not None


# ---- 消息 ----------------------------------------------------------------

def add_message(conv_id: str, role: str, content: str,
                sources: list | None = None, model: str | None = None) -> str:
    mid = _new_id()
    with _conn() as c:
        c.execute(
            "INSERT INTO messages(id,conv_id,role,content,sources_json,model,created_at)"
            " VALUES(?,?,?,?,?,?,?)",
            (mid, conv_id, role, content,
             json.dumps(sources, ensure_ascii=False) if sources else None,
             model, _now()),
        )
    return mid


def recent_messages(conv_id: str, turns: int) -> list[dict]:
    """取最近 turns 轮（user+assistant 各算一条）对话，按时间正序返回。

    用于给大模型提供多轮上下文。turns 轮 ≈ 2*turns 条消息。
    """
    limit = max(1, turns) * 2
    with _conn() as c:
        rows = c.execute(
            "SELECT role, content FROM messages WHERE conv_id=?"
            " ORDER BY created_at DESC, id DESC LIMIT ?",
            (conv_id, limit),
        ).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
