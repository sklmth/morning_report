import os
import re
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, jsonify, abort
from werkzeug.utils import secure_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
DB_PATH = os.path.join(BASE_DIR, 'data', 'novels.db')

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB


# ── DB ───────────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    with get_db() as conn:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS books (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                title        TEXT    NOT NULL,
                author       TEXT    DEFAULT '未知作者',
                filename     TEXT    NOT NULL,
                total_chaps  INTEGER DEFAULT 0,
                total_chars  INTEGER DEFAULT 0,
                created_at   TEXT    NOT NULL,
                cover_color  TEXT    DEFAULT '#4a90d9'
            );
            CREATE TABLE IF NOT EXISTS chapters (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id     INTEGER NOT NULL,
                chap_num    INTEGER NOT NULL,
                title       TEXT    NOT NULL,
                content     TEXT    NOT NULL,
                char_count  INTEGER DEFAULT 0,
                FOREIGN KEY (book_id) REFERENCES books(id)
            );
        ''')


# ── Chapter parser ────────────────────────────────────────────────────────────

_CHAP_RE = re.compile(
    r'^('
    r'第[零一二三四五六七八九十百千万\d〇○]+[章回节卷部篇]'
    r'|Chapter\s*\d+'
    r'|chapter\s*\d+'
    r'|序[章言]?|楔子|尾声|番外[篇章]?|后记|终章|完结感言'
    r'|\d{1,4}[\.、．]\s*\S'
    r')[\s\S]{0,60}$'
)


def parse_chapters(text: str) -> list[dict]:
    lines = text.splitlines()
    chapters, cur_title, cur_lines = [], '卷首', []
    chap_num = 0

    for line in lines:
        stripped = line.strip()
        if stripped and _CHAP_RE.match(stripped):
            body = '\n'.join(cur_lines).strip()
            if body or chap_num == 0:
                chapters.append({'num': chap_num, 'title': cur_title, 'content': body})
                chap_num += 1
            cur_title = stripped
            cur_lines = []
        else:
            cur_lines.append(line)

    body = '\n'.join(cur_lines).strip()
    if body:
        chapters.append({'num': chap_num, 'title': cur_title, 'content': body})

    if not chapters:
        chapters = [{'num': 0, 'title': '全文', 'content': text}]

    return chapters


_COLORS = [
    '#c0392b', '#e67e22', '#27ae60', '#2980b9', '#8e44ad',
    '#16a085', '#d35400', '#2471a3', '#1a5276', '#6c3483',
]


def cover_color(title: str) -> str:
    return _COLORS[abs(hash(title)) % len(_COLORS)]


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    with get_db() as conn:
        books = conn.execute('SELECT * FROM books ORDER BY created_at DESC').fetchall()
    return render_template('index.html', books=books)


@app.route('/upload', methods=['POST'])
def upload():
    f = request.files.get('file')
    if not f or not f.filename:
        return jsonify({'error': '请选择文件'}), 400
    if not f.filename.lower().endswith('.txt'):
        return jsonify({'error': '仅支持 .txt 格式'}), 400

    raw = f.read()
    text = None
    for enc in ('utf-8-sig', 'utf-8', 'gbk', 'gb18030', 'big5'):
        try:
            text = raw.decode(enc)
            break
        except Exception:
            continue
    if text is None:
        return jsonify({'error': '文件编码无法识别，请转为 UTF-8'}), 400

    title  = request.form.get('title',  '').strip() or os.path.splitext(f.filename)[0]
    author = request.form.get('author', '').strip() or '未知作者'

    fname = secure_filename(f.filename)
    base, ext = os.path.splitext(fname)
    fpath = os.path.join(UPLOAD_FOLDER, fname)
    i = 1
    while os.path.exists(fpath):
        fname = f'{base}_{i}{ext}'
        fpath = os.path.join(UPLOAD_FOLDER, fname)
        i += 1
    with open(fpath, 'w', encoding='utf-8') as out:
        out.write(text)

    chapters = parse_chapters(text)

    with get_db() as conn:
        cur = conn.execute(
            'INSERT INTO books (title,author,filename,total_chaps,total_chars,created_at,cover_color) VALUES (?,?,?,?,?,?,?)',
            (title, author, fname, len(chapters), len(text),
             datetime.now().strftime('%Y-%m-%d %H:%M'), cover_color(title))
        )
        book_id = cur.lastrowid
        conn.executemany(
            'INSERT INTO chapters (book_id,chap_num,title,content,char_count) VALUES (?,?,?,?,?)',
            [(book_id, c['num'], c['title'], c['content'], len(c['content'])) for c in chapters]
        )

    return jsonify({'success': True, 'book_id': book_id,
                    'title': title, 'chapters': len(chapters)})


@app.route('/book/<int:book_id>')
def toc(book_id):
    with get_db() as conn:
        book = conn.execute('SELECT * FROM books WHERE id=?', (book_id,)).fetchone()
        if not book:
            abort(404)
        chapters = conn.execute(
            'SELECT chap_num, title, char_count FROM chapters WHERE book_id=? ORDER BY chap_num',
            (book_id,)
        ).fetchall()
    return render_template('toc.html', book=book, chapters=chapters)


@app.route('/read/<int:book_id>/<int:chap_num>')
def read(book_id, chap_num):
    with get_db() as conn:
        book = conn.execute('SELECT * FROM books WHERE id=?', (book_id,)).fetchone()
        if not book:
            abort(404)
        chap = conn.execute(
            'SELECT * FROM chapters WHERE book_id=? AND chap_num=?', (book_id, chap_num)
        ).fetchone()
        if not chap:
            abort(404)
        prev_c = conn.execute(
            'SELECT chap_num,title FROM chapters WHERE book_id=? AND chap_num<? ORDER BY chap_num DESC LIMIT 1',
            (book_id, chap_num)
        ).fetchone()
        next_c = conn.execute(
            'SELECT chap_num,title FROM chapters WHERE book_id=? AND chap_num>? ORDER BY chap_num LIMIT 1',
            (book_id, chap_num)
        ).fetchone()
        all_chaps = conn.execute(
            'SELECT chap_num,title FROM chapters WHERE book_id=? ORDER BY chap_num',
            (book_id,)
        ).fetchall()
    return render_template('reader.html',
                           book=book, chap=chap,
                           prev_c=prev_c, next_c=next_c,
                           all_chaps=all_chaps)


@app.route('/delete/<int:book_id>', methods=['POST'])
def delete_book(book_id):
    with get_db() as conn:
        row = conn.execute('SELECT filename FROM books WHERE id=?', (book_id,)).fetchone()
        if not row:
            return jsonify({'error': '不存在'}), 404
        fpath = os.path.join(UPLOAD_FOLDER, row['filename'])
        if os.path.exists(fpath):
            os.remove(fpath)
        conn.execute('DELETE FROM chapters WHERE book_id=?', (book_id,))
        conn.execute('DELETE FROM books WHERE id=?', (book_id,))
    return jsonify({'success': True})


if __name__ == '__main__':
    init_db()
    host = os.environ.get('NOVEL_READER_HOST', '127.0.0.1')
    port = int(os.environ.get('NOVEL_READER_PORT', '16060'))
    app.run(debug=False, port=port, host=host)
