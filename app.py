from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
import sqlite3
import os
import io

app = Flask(__name__)
app.config['SECRET_KEY'] = '123456789'
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'doc', 'docx', 'xls', 'xlsx'}

login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, username, password, role):
        self.id = id
        self.username = username
        self.password = password
        self.role = role

@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect('EDO.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user_data = cursor.fetchone()
    conn.close()
    return User(*user_data) if user_data else None

def init_db():
    conn = sqlite3.connect('EDO.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'user'
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            file_data BLOB NOT NULL,
            file_name TEXT NOT NULL,
            status TEXT DEFAULT 'Черновик',
            user_id INTEGER,
            file_date DATE DEFAULT CURRENT_DATE,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    cursor.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES (?, ?, ?)", 
                  ('admin', 'admin', 'admin'))
    conn.commit()
    conn.close()

init_db()

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = sqlite3.connect('EDO.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
        user_data = cursor.fetchone()
        conn.close()
        if user_data:
            login_user(User(*user_data))
            return redirect(url_for('home'))
        flash('Неверные данные')
    return render_template('login.html')

@app.route('/')
@login_required
def home():
    sort_by = request.args.get('sort_by', 'file_date')
    order = request.args.get('order', 'desc')
    valid_sort_columns = ['title', 'file_date', 'status']
    if sort_by not in valid_sort_columns:
        sort_by = 'file_date'
    
    valid_orders = ['asc', 'desc']
    if order not in valid_orders:
        order = 'desc'
    
    conn = sqlite3.connect('EDO.db')
    cursor = conn.cursor()
    query = f"""
        SELECT d.id, d.title, d.file_name, d.status, d.file_date, u.username 
        FROM documents d 
        JOIN users u ON d.user_id = u.id
        ORDER BY {sort_by} {order}
    """
    
    cursor.execute(query)
    documents = cursor.fetchall()
    conn.close()
    
    return render_template('home.html', 
                         documents=documents,
                         sort_by=sort_by,
                         order=order)

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        file = request.files['file']
        if file and file.filename:
            file_data = file.read()
            conn = sqlite3.connect('EDO.db')
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO documents (title, file_data, file_name, user_id) 
                VALUES (?, ?, ?, ?)
            """, (request.form['title'], file_data, file.filename, current_user.id))
            conn.commit()
            conn.close()
            flash('Документ загружен')
            return redirect(url_for('home'))
    return render_template('upload.html')

@app.route('/change_status/<int:doc_id>/<status>')
@login_required
def change_status(doc_id, status):
    if current_user.role != 'admin':
        flash('Недостаточно прав', 'Отказано')
        return redirect(url_for('home'))   
    conn = sqlite3.connect('EDO.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE documents SET status = ? WHERE id = ?", (status, doc_id))
    conn.commit()
    conn.close()
    
    flash('Статус документа обновлен', 'Успешно')
    return redirect(url_for('home'))

@app.route('/delete/<int:doc_id>')
@login_required
def delete(doc_id):
    conn = sqlite3.connect('EDO.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    conn.commit()
    conn.close()
    flash('Документ удален')
    return redirect(url_for('home'))

@app.route('/download/<int:doc_id>')
@login_required
def download(doc_id):
    conn = sqlite3.connect('EDO.db')
    cursor = conn.cursor()
    cursor.execute("SELECT file_data, file_name FROM documents WHERE id = ?", (doc_id,))
    doc = cursor.fetchone()
    conn.close()
    if doc:
        return send_file(
            io.BytesIO(doc[0]),
            as_attachment=True,
            download_name=doc[1]
        )
    flash('Документ не найден')
    return redirect(url_for('home'))

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
