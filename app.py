# -*- coding: utf-8 -*-
"""
Firmowy Kiosk - Aplikacja Flask do wyświetlania dashboardów
Autor: Replit Agent
Data: 2025-10-27
"""

import os
import json
import sqlite3
import secrets
import csv
from datetime import datetime, date, timedelta
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from werkzeug.utils import secure_filename
import pandas as pd
from waitress import serve

# Konfiguracja aplikacji Flask
app = Flask(__name__)

# Stały klucz sesji dla zachowania ciągłości po restarcie serwera
app.secret_key = "stora-enso-kiosk-permanent-secret-key-2025"
app.config['SESSION_COOKIE_NAME'] = 'kiosk_session'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
app.config['UPLOAD_FOLDER'] = 'static/images'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Max 16MB upload

# Dozwolone rozszerzenia plików
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'svg', 'webp'}

# ==================== BAZA DANYCH ====================

def init_db():
    """Inicjalizacja bazy danych SQLite"""
    conn = sqlite3.connect('kiosk.db')
    c = conn.cursor()
    
    # Tabela z ustawieniami ogólnymi
    c.execute('''CREATE TABLE IF NOT EXISTS settings
                 (key TEXT PRIMARY KEY, value TEXT)''')
    
    # Tabela z inspiracjami
    c.execute('''CREATE TABLE IF NOT EXISTS inspirations
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  title TEXT,
                  description TEXT,
                  image_url TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Tabela ze zdjęciami (dla pokazu slajdów)
    c.execute('''CREATE TABLE IF NOT EXISTS slides
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  filename TEXT,
                  caption TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Tabela z widocznością stron
    c.execute('''CREATE TABLE IF NOT EXISTS page_visibility
                 (page_id TEXT PRIMARY KEY,
                  title TEXT,
                  is_visible INTEGER DEFAULT 1)''')
    
    # Wstaw domyślne ustawienia jeśli nie istnieją
    c.execute("SELECT COUNT(*) FROM settings")
    if c.fetchone()[0] == 0:
        default_settings = [
            ('header_title', 'Dashboard Inspiracji i Wyników'),
            ('footer_note', 'Stora Enso - Innowacje dla Przyszłości'),
            ('about_text', 'Nasz zespół stale poszukuje nowych rozwiązań i inspiracji.')
        ]
        c.executemany("INSERT INTO settings (key, value) VALUES (?, ?)", default_settings)

    # Wstaw domyślne strony jeśli nie istnieją
    c.execute("SELECT COUNT(*) FROM page_visibility")
    if c.fetchone()[0] == 0:
        default_pages = [
            ('dashboard', 'Dashboard', 1),
            ('wykresy', 'Wykresy', 1),
            ('inspiracje', 'Inspiracje', 1),
            ('zdjecia', 'Zdjęcia', 1),
            ('quiz', 'Quiz', 1),
            ('o-nas', 'O nas', 1),
            ('powerbi', 'Power BI', 1)
        ]
        c.executemany("INSERT INTO page_visibility (page_id, title, is_visible) VALUES (?, ?, ?)", default_pages)
        
        # Dodaj przykładowe inspiracje
        example_inspirations = [
            ('Zielona Energia', 'Inwestujemy w odnawialne źródła energii, aby zmniejszyć nasz ślad węglowy.', '/static/images/placeholder1.jpg'),
            ('Cyfrowa Transformacja', 'Automatyzacja procesów i wykorzystanie AI w produkcji.', '/static/images/placeholder2.jpg'),
            ('Ekologiczne Opakowania', 'Rozwój biodegradowalnych materiałów opakowaniowych.', '/static/images/placeholder3.jpg')
        ]
        c.executemany("INSERT INTO inspirations (title, description, image_url) VALUES (?, ?, ?)", 
                     example_inspirations)
    
    conn.commit()
    conn.close()

def get_setting(key):
    """Pobierz ustawienie z bazy danych"""
    conn = sqlite3.connect('kiosk.db')
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key=?", (key,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

def update_setting(key, value):
    """Aktualizuj ustawienie w bazie danych"""
    conn = sqlite3.connect('kiosk.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def get_inspirations():
    """Pobierz wszystkie inspiracje"""
    conn = sqlite3.connect('kiosk.db')
    c = conn.cursor()
    c.execute("SELECT id, title, description, image_url FROM inspirations ORDER BY created_at DESC")
    inspirations = [{'id': row[0], 'title': row[1], 'description': row[2], 'image_url': row[3]} 
                   for row in c.fetchall()]
    conn.close()
    return inspirations

# ==================== POMOCNICZE FUNKCJE ====================

def allowed_file(filename):
    """Sprawdź czy plik ma dozwolone rozszerzenie"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def load_config():
    """Wczytaj konfigurację z pliku config.json"""
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        # Zwróć domyślną konfigurację jeśli plik nie istnieje
        return {'admin_pin': '7456', 'rotation_interval': 30, 'refresh_interval': 300}

def get_chart_data():
    """Wczytaj dane z pliku Export.xlsx - dla kompatybilności (nie używane)"""
    return []

def get_chart_data_for_machine(kod='1310', start_day=1):
    """Wczytaj dane dla konkretnej maszyny z Export.xlsx - osobno dla każdej brygady (A, B, C) dzienne i narastające"""
    try:
        # Wczytaj dane z Export.xlsx
        df_long = load_long()
        
        if df_long.empty:
            return {'series': []}
        
        # Filtruj dane dla wybranej maszyny
        df_maszyna = df_long[df_long['Kod'] == str(kod)].copy()
        
        if df_maszyna.empty:
            return {'series': []}
        
        # Pobierz 7 dni od start_day
        end_day = start_day + 6
        
        series_data = []
        kolory_slupki = {'A': '#0ea5e9', 'B': '#FF6B35', 'C': '#6b7280'}
        kolory_linie = {'A': '#0284c7', 'B': '#f97316', 'C': '#4b5563'}
        
        # Słupki dla wartości dziennych (brygady A, B, C)
        for brygada in ['A', 'B', 'C']:
            mask = (df_maszyna['Typ'] == 'Dzienne') & (df_maszyna['Brygada'] == brygada) & \
                   (df_maszyna['Dzien'] >= start_day) & (df_maszyna['Dzien'] <= end_day)
            filtered = df_maszyna[mask].copy().sort_values('Dzien')
            
            if not filtered.empty:
                series_data.append({
                    'type': 'bar',
                    'name': brygada,
                    'x': filtered['Dzien'].tolist(),
                    'y': [round(v, 0) for v in filtered['Wartosc'].tolist()],
                    'color': kolory_slupki.get(brygada, '#999999')
                })
        
        # Linie dla wartości narastających (brygady A, B, C)
        for brygada in ['A', 'B', 'C']:
            mask = (df_maszyna['Typ'] == 'Narastające') & (df_maszyna['Brygada'] == brygada) & \
                   (df_maszyna['Dzien'] >= start_day) & (df_maszyna['Dzien'] <= end_day)
            filtered = df_maszyna[mask].copy().sort_values('Dzien')
            
            if not filtered.empty:
                series_data.append({
                    'type': 'line',
                    'name': f'Narastająco {brygada}',
                    'x': filtered['Dzien'].tolist(),
                    'y': [round(v, 0) for v in filtered['Wartosc'].tolist()],
                    'color': kolory_linie.get(brygada, '#666666')
                })
        
        return {'series': series_data}
        
    except Exception as e:
        print(f"Błąd wczytywania danych dla maszyny {kod}: {e}")
        return {'series': []}

def get_slide_images():
    """Pobierz listę zdjęć do pokazu slajdów"""
    images_path = os.path.join(app.config['UPLOAD_FOLDER'])
    if not os.path.exists(images_path):
        return []
    
    images = []
    for filename in os.listdir(images_path):
        if allowed_file(filename):
            images.append({
                'url': f'/static/images/{filename}',
                'name': filename
            })
    return images

def get_current_quiz_question():
    """
    Wczytaj aktualne pytanie quizowe z pliku CSV
    Zwraca pytanie, które jest aktywne w obecnej dacie (start_date <= dzisiaj <= end_date)
    Jeśli nie ma dopasowania, zwraca pierwsze pytanie z pliku
    """
    csv_path = 'data/quiz_questions.csv'
    
    # Sprawdź czy plik istnieje
    if not os.path.exists(csv_path):
        return None
    
    try:
        today = date.today()
        questions = []
        
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=';')
            for row in reader:
                questions.append(row)
        
        if not questions:
            return None
        
        # Znajdź pytanie aktywne w obecnej dacie
        active_question = None
        for q in questions:
            try:
                start_date = datetime.strptime(q['start_date'], '%Y-%m-%d').date()
                end_date = datetime.strptime(q['end_date'], '%Y-%m-%d').date()
                
                if start_date <= today <= end_date:
                    active_question = q
                    break
            except (ValueError, KeyError):
                continue
        
        # Jeśli nie znaleziono aktywnego, użyj pierwszego
        if not active_question:
            active_question = questions[0]
        
        # Przetwórz odpowiedzi
        answers = []
        for i in range(1, 5):
            answer_key = f'answer{i}'
            if answer_key in active_question and active_question[answer_key].strip():
                answers.append(active_question[answer_key].strip())
        
        # Konwertuj correct_index z 1-indeksowany na 0-indeksowany
        try:
            correct_index = int(active_question.get('correct_index', 1)) - 1
        except (ValueError, TypeError):
            correct_index = 0
        
        return {
            'category': active_question.get('category', ''),
            'question': active_question.get('question', ''),
            'answers': answers,
            'correct_index': correct_index,
            'explanation': active_question.get('explanation', '')
        }
        
    except Exception as e:
        print(f"Błąd wczytywania pytań quizowych: {e}")
        return None

def load_long():
    """
    Wczytaj dane z pliku Export.xlsx i przekształć do formy długiej (long format)
    Format: Typ, Kod, Nazwa, Brygada, Dzien (1-31), Wartosc
    POPRAWKA: Dni miesiąca są w wierszu 1 od kolumny D (indeks 3).
    """
    try:
        # Wczytaj dane z Export.xlsx - używamy header=0, bo dni są w pierwszym wierszu
        try:
            df = pd.read_excel('Export.xlsx', sheet_name='Export', engine='openpyxl')
        except ValueError:
            try:
                df = pd.read_excel('Export.xlsx', sheet_name='Eksport', engine='openpyxl')
            except ValueError:
                try:
                    df = pd.read_excel('Export.xlsx', sheet_name='Arkusz1', engine='openpyxl')
                except ValueError:
                    df = pd.read_excel('Export.xlsx', sheet_name=0, engine='openpyxl')
        
        # Oczekiwana struktura: 
        # Kolumna A (0): Typ
        # Kolumna B (1): Kod
        # Kolumna C (2): Brygada (lub Nazwa, sprawdzimy)
        # Kolumny D-AH (3-33): Dni 1-31
        
        # Mapowanie kolumn bazowych
        base_cols = df.columns[:3].tolist()
        df.columns = ['Typ', 'Kod', 'Brygada'] + [str(c) for c in df.columns[3:]]
        df['Nazwa'] = '' # Dodajemy pustą nazwę dla spójności
        
        id_vars = ['Typ', 'Kod', 'Nazwa', 'Brygada']
        
        # Wybierz tylko kolumny, które są numerami dni 1-31
        value_vars = []
        for col in df.columns[3:]:
            try:
                # Czyścimy nazwę kolumny (może być "1.0" lub "1")
                c_clean = str(col).split('.')[0]
                c_int = int(c_clean)
                if 1 <= c_int <= 31:
                    value_vars.append(col)
            except:
                continue
        
        df_long = pd.melt(
            df,
            id_vars=id_vars,
            value_vars=value_vars,
            var_name='Dzien',
            value_name='Wartosc'
        )
        
        # Konwertujemy Dzień na czysty int
        df_long['Dzien'] = df_long['Dzien'].apply(lambda x: int(str(x).split('.')[0]))
        df_long = df_long.dropna(subset=['Wartosc'])
        
        # Konwertuj typy
        df_long['Typ'] = df_long['Typ'].astype(str)
        df_long['Kod'] = df_long['Kod'].astype(str)
        df_long['Nazwa'] = df_long['Nazwa'].astype(str)
        df_long['Brygada'] = df_long['Brygada'].astype(str)
        df_long['Wartosc'] = pd.to_numeric(df_long['Wartosc'], errors='coerce').fillna(0)
        
        print(f"✅ Dane z Export.xlsx wczytane poprawnie (Dni od kolumny D): {len(df_long)} wierszy.")
        return df_long
    
    except FileNotFoundError:
        print(f"❌ BŁĄD: Nie znaleziono pliku Export.xlsx")
        return pd.DataFrame(columns=['Typ', 'Kod', 'Nazwa', 'Brygada', 'Dzien', 'Wartosc'])
    except Exception as e:
        print(f"Błąd wczytywania danych z Export.xlsx: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame(columns=['Typ', 'Kod', 'Nazwa', 'Brygada', 'Dzien', 'Wartosc'])

# ==================== TRASY (ROUTES) ====================

@app.route('/')
def index():
    """Strona główna - Dashboard"""
    conn = sqlite3.connect('kiosk.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Pobierz ustawienia
    settings_rows = c.execute('SELECT key, value FROM settings').fetchall()
    settings_dict = {row['key']: row['value'] for row in settings_rows}
    
    # Pobierz inspiracje
    inspirations_rows = c.execute('SELECT id, title, description, image_url FROM inspirations ORDER BY created_at DESC').fetchall()
    inspirations = [dict(row) for row in inspirations_rows]
    
    # Pobierz widoczność stron
    try:
        visibility_rows = c.execute('SELECT page_id, is_visible FROM page_visibility').fetchall()
        visibility = {row['page_id']: bool(row['is_visible']) for row in visibility_rows}
    except:
        visibility = {}
    
    conn.close()
    
    return render_template('index.html',
                         header_title=settings_dict.get('header_title', 'Dashboard Inspiracji i Wyników'),
                         footer_note=settings_dict.get('footer_note', 'Stora Enso'),
                         about_text=settings_dict.get('about_text', ''),
                         inspirations=inspirations,
                         visibility=visibility)

@app.context_processor
def inject_page_visibility():
    """Wstrzykuje stan widoczności stron do wszystkich szablonów"""
    try:
        conn = sqlite3.connect('kiosk.db')
        c = conn.cursor()
        c.execute('SELECT page_id, is_visible FROM page_visibility')
        visibility = {row[0]: bool(row[1]) for row in c.fetchall()}
        conn.close()
        return dict(pages_visible=visibility)
    except:
        return dict(pages_visible={})

@app.route('/api/visibility', methods=['POST'])
def update_visibility():
    """Aktualizuj widoczność stron"""
    if not session.get('authenticated'):
        return jsonify({'error': 'Brak autoryzacji'}), 401
    
    data = request.json or {}
    page_id = data.get('page_id')
    is_visible = 1 if data.get('is_visible') else 0
    
    if not page_id:
        return jsonify({'error': 'Brak ID strony'}), 400
        
    conn = sqlite3.connect('kiosk.db')
    c = conn.cursor()
    c.execute("UPDATE page_visibility SET is_visible=? WHERE page_id=?", (is_visible, page_id))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    """Panel administracyjny"""
    config = load_config()
    
    if request.method == 'POST':
        # Sprawdź PIN
        pin = request.form.get('pin')
        if pin == config['admin_pin']:
            session.permanent = True
            session['authenticated'] = True
            return redirect(url_for('admin'))
        else:
            return render_template('admin.html', error='Nieprawidłowy PIN!')
    
    # Sprawdź czy użytkownik jest zalogowany
    if not session.get('authenticated'):
        return render_template('admin.html', authenticated=False)
    
    # Użytkownik zalogowany - pokaż panel
    try:
        # AUTOMATYCZNA NAPRAWA BAZY (Dla serwerów bez nowej tabeli)
        init_db()
        
        conn = sqlite3.connect('kiosk.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # Pobierz ustawienia
        settings_rows = c.execute('SELECT key, value FROM settings').fetchall()
        settings_dict = {row['key']: row['value'] for row in settings_rows}
        
        # Pobierz inspiracje
        inspirations_rows = c.execute('SELECT id, title, description, image_url FROM inspirations ORDER BY created_at DESC').fetchall()
        inspirations = [dict(row) for row in inspirations_rows]
        
        # Pobierz widoczność stron
        pages_rows = c.execute('SELECT page_id, title, is_visible FROM page_visibility').fetchall()
        pages = [dict(row) for row in pages_rows]
        
        conn.close()
        
        return render_template('admin.html',
                             authenticated=True,
                             header_title=settings_dict.get('header_title', ''),
                             footer_note=settings_dict.get('footer_note', ''),
                             about_text=settings_dict.get('about_text', ''),
                             inspirations=inspirations,
                             pages=pages)
    except Exception as e:
        print(f"BŁĄD W ADMIN: {str(e)}")
        import traceback
        traceback.print_exc()
        return f"Wystąpił błąd podczas ładowania panelu admina: {str(e)}", 500

@app.route('/admin/logout')
def admin_logout():
    """Wylogowanie z panelu admina"""
    session.pop('authenticated', None)
    return redirect(url_for('admin'))

@app.route('/quiz')
def quiz():
    """Strona Quiz / Pytanie dnia"""
    # Sprawdź widoczność
    conn = sqlite3.connect('kiosk.db')
    c = conn.cursor()
    c.execute('SELECT is_visible FROM page_visibility WHERE page_id=?', ('quiz',))
    row = c.fetchone()
    conn.close()
    
    if row and not row[0]:
        return "Brak uprawnień do tej sekcji", 403
        
    quiz_data = get_current_quiz_question()
    header_title = get_setting('header_title')
    footer_note = get_setting('footer_note')
    
    return render_template('quiz.html',
                         quiz=quiz_data,
                         header_title=header_title,
                         footer_note=footer_note)

# ==================== API ENDPOINTS ====================

@app.route('/api/settings', methods=['POST'])
def update_settings():
    """Aktualizuj ustawienia aplikacji"""
    if not session.get('authenticated'):
        return jsonify({'error': 'Brak autoryzacji'}), 401
    
    data = request.json
    if data and 'header_title' in data:
        update_setting('header_title', data['header_title'])
    if data and 'footer_note' in data:
        update_setting('footer_note', data['footer_note'])
    if data and 'about_text' in data:
        update_setting('about_text', data['about_text'])
    
    return jsonify({'success': True})

@app.route('/api/inspiration', methods=['POST'])
def add_inspiration():
    """Dodaj nową inspirację"""
    if not session.get('authenticated'):
        return jsonify({'error': 'Brak autoryzacji'}), 401
    
    data = request.json or {}
    conn = sqlite3.connect('kiosk.db')
    c = conn.cursor()
    c.execute("INSERT INTO inspirations (title, description, image_url) VALUES (?, ?, ?)",
             (data.get('title', ''), data.get('description', ''), data.get('image_url', '')))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/api/inspiration/<int:inspiration_id>', methods=['DELETE'])
def delete_inspiration(inspiration_id):
    """Usuń inspirację"""
    if not session.get('authenticated'):
        return jsonify({'error': 'Brak autoryzacji'}), 401
    
    conn = sqlite3.connect('kiosk.db')
    c = conn.cursor()
    c.execute("DELETE FROM inspirations WHERE id=?", (inspiration_id,))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Upload pliku zdjęcia"""
    if not session.get('authenticated'):
        return jsonify({'error': 'Brak autoryzacji'}), 401
    
    if 'file' not in request.files:
        return jsonify({'error': 'Brak pliku'}), 400
    
    file = request.files['file']
    if file.filename == '' or file.filename is None:
        return jsonify({'error': 'Nie wybrano pliku'}), 400
    
    if file and file.filename and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # Dodaj timestamp do nazwy aby uniknąć konfliktów
        name, ext = os.path.splitext(filename)
        filename = f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
        
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        return jsonify({
            'success': True,
            'url': f'/static/images/{filename}',
            'filename': filename
        })
    
    return jsonify({'error': 'Niedozwolony typ pliku'}), 400

@app.route('/api/upload-jumbo', methods=['POST'])
def upload_jumbo_file():
    """Upload pliku Excel (Jumbo.xlsx)"""
    if not session.get('authenticated'):
        return jsonify({'error': 'Brak autoryzacji'}), 401
    
    if 'excel_file' not in request.files:
        return jsonify({'error': 'Brak pliku w żądaniu'}), 400
    
    file = request.files['excel_file']
    if file.filename == '':
        return jsonify({'error': 'Nie wybrano pliku'}), 400
    
    if file and (file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
        try:
            filepath = 'Jumbo.xlsx'
            file.save(filepath)
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    return jsonify({'error': 'Niedozwolony typ pliku (tylko .xlsx)'}), 400

@app.route('/api/upload-excel', methods=['POST'])
def upload_excel():
    """Upload pliku Excel (Export.xlsx)"""
    if not session.get('authenticated'):
        return jsonify({'error': 'Brak autoryzacji'}), 401
    
    if 'excel_file' not in request.files:
        return jsonify({'error': 'Brak pliku w żądaniu'}), 400
    
    file = request.files['excel_file']
    if file.filename == '':
        return jsonify({'error': 'Nie wybrano pliku'}), 400
    
    # Sprawdź czy to plik Excel
    if file and (file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
        try:
            # Zapisz jako Export.xlsx (zastąp istniejący)
            filepath = 'Export.xlsx'
            file.save(filepath)
            
            # Wymuś przeładowanie danych, aby sprawdzić czy plik jest czytelny
            df_check = load_long()
            if df_check.empty:
                 return jsonify({'error': 'Plik został zapisany, ale wydaje się pusty lub ma nieprawidłową strukturę.'}), 200
            
            return jsonify({
                'success': True,
                'message': f'Plik Export.xlsx został zaktualizowany ({len(df_check)} wierszy)',
                'filename': 'Export.xlsx'
            })
        except Exception as e:
            return jsonify({'error': f'Błąd podczas zapisywania pliku: {str(e)}'}), 500
    
    return jsonify({'error': 'Niedozwolony typ pliku - wymagany plik .xlsx lub .xls'}), 400

@app.route('/api/quiz/questions', methods=['GET'])
def get_quiz_questions():
    """Pobierz wszystkie pytania quizowe"""
    if not session.get('authenticated'):
        return jsonify({'error': 'Brak autoryzacji'}), 401
    
    csv_path = 'data/quiz_questions.csv'
    
    if not os.path.exists(csv_path):
        return jsonify([])
    
    try:
        questions = []
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=';')
            for idx, row in enumerate(reader, start=1):
                row['id'] = idx
                questions.append(row)
        return jsonify(questions)
    except Exception as e:
        print(f"Błąd wczytywania pytań: {e}")
        return jsonify([])

@app.route('/api/quiz/question', methods=['POST'])
def add_quiz_question():
    """Dodaj nowe pytanie quizowe"""
    if not session.get('authenticated'):
        return jsonify({'error': 'Brak autoryzacji'}), 401
    
    data = request.json or {}
    csv_path = 'data/quiz_questions.csv'
    
    try:
        # Pobierz wszystkie istniejące pytania
        questions = []
        if os.path.exists(csv_path):
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f, delimiter=';')
                for row in reader:
                    questions.append(row)
        
        # Znajdź najwyższe ID
        max_id = 0
        for q in questions:
            try:
                max_id = max(max_id, int(q.get('id', 0)))
            except:
                pass
        
        new_id = max_id + 1
        
        # Dodaj nowe pytanie
        new_question = {
            'id': str(new_id),
            'category': data.get('category', ''),
            'question': data.get('question', ''),
            'answer1': data.get('answer1', ''),
            'answer2': data.get('answer2', ''),
            'answer3': data.get('answer3', ''),
            'answer4': data.get('answer4', ''),
            'correct_index': str(data.get('correct_index', 1)),
            'explanation': data.get('explanation', ''),
            'start_date': data.get('start_date', ''),
            'end_date': data.get('end_date', '')
        }
        
        questions.append(new_question)
        
        # Zapisz wszystkie pytania
        with open(csv_path, 'w', encoding='utf-8', newline='') as f:
            fieldnames = ['id', 'category', 'question', 'answer1', 'answer2', 'answer3', 'answer4', 
                         'correct_index', 'explanation', 'start_date', 'end_date']
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
            writer.writeheader()
            writer.writerows(questions)
        
        return jsonify({'success': True, 'id': new_id})
        
    except Exception as e:
        print(f"Błąd dodawania pytania: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/quiz/question/<int:question_id>', methods=['DELETE'])
def delete_quiz_question(question_id):
    """Usuń pytanie quizowe"""
    if not session.get('authenticated'):
        return jsonify({'error': 'Brak autoryzacji'}), 401
    
    csv_path = 'data/quiz_questions.csv'
    
    if not os.path.exists(csv_path):
        return jsonify({'error': 'Plik nie istnieje'}), 404
    
    try:
        # Wczytaj wszystkie pytania
        questions = []
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=';')
            for row in reader:
                questions.append(row)
        
        # Usuń pytanie o danym ID (ID to pozycja w liście, 1-indeksowany)
        if 1 <= question_id <= len(questions):
            questions.pop(question_id - 1)
        else:
            return jsonify({'error': 'Pytanie nie znalezione'}), 404
        
        # Zapisz pozostałe pytania z nowymi ID
        with open(csv_path, 'w', encoding='utf-8', newline='') as f:
            fieldnames = ['id', 'category', 'question', 'answer1', 'answer2', 'answer3', 'answer4', 
                         'correct_index', 'explanation', 'start_date', 'end_date']
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
            writer.writeheader()
            
            for idx, q in enumerate(questions, start=1):
                q['id'] = str(idx)
                writer.writerow(q)
        
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"Błąd usuwania pytania: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/chart-data')
def chart_data():
    """Zwróć dane do wykresów dla konkretnej maszyny"""
    kod = request.args.get('kod', '1310')
    start_day = int(request.args.get('start_day', 1))
    data = get_chart_data_for_machine(kod=kod, start_day=start_day)
    return jsonify(data)

@app.route('/api/machines')
def get_machines():
    """Zwróć listę dostępnych maszyn z Export.xlsx"""
    try:
        df_long = load_long()
        if df_long.empty:
            return jsonify([])
        
        # Pobierz unikalne maszyny (kod + nazwa)
        maszyny_df = df_long[['Kod', 'Nazwa']].drop_duplicates().sort_values('Kod')
        maszyny = []
        for _, row in maszyny_df.iterrows():
            kod = row['Kod']
            nazwa = row['Nazwa']
            if nazwa and str(nazwa).strip():
                maszyny.append({'kod': kod, 'label': f"{kod} {nazwa}"})
            else:
                maszyny.append({'kod': kod, 'label': kod})
        
        return jsonify(maszyny)
    except Exception as e:
        print(f"Błąd pobierania listy maszyn: {e}")
        return jsonify([])

@app.route('/api/slides')
def slides():
    """Zwróć listę zdjęć do pokazu slajdów"""
    images = get_slide_images()
    return jsonify(images)

@app.route('/api/inspirations')
def api_inspirations():
    """Zwróć listę inspiracji"""
    inspirations = get_inspirations()
    return jsonify(inspirations)

@app.route('/api/content')
def get_content():
    """Zwróć całą treść dla strony głównej (dla auto-refresh)"""
    conn = sqlite3.connect('kiosk.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Ustawienia
    settings_rows = c.execute('SELECT key, value FROM settings').fetchall()
    settings_dict = {row['key']: row['value'] for row in settings_rows}
    
    # Inspiracje
    inspirations = c.execute('SELECT id, title, description, image_url FROM inspirations ORDER BY created_at DESC').fetchall()
    inspirations_list = [dict(row) for row in inspirations]
    
    # Widoczność
    visibility_rows = c.execute('SELECT page_id, is_visible FROM page_visibility').fetchall()
    visibility_dict = {row['page_id']: bool(row['is_visible']) for row in visibility_rows}
    
    conn.close()
    
    return jsonify({
        'settings': settings_dict,
        'inspirations': inspirations_list,
        'visibility': visibility_dict,
        'chart_data': get_chart_data(),
        'slides': get_slide_images()
    })

# ==================== WYKRESY PLOTLY ====================

@app.route('/wykres')
def wykres():
    """Strona z interaktywnym wykresem Plotly - wykres kombinowany (słupki + linie)"""
    import plotly.graph_objects as go
    from plotly.offline import plot
    
    df_long = load_long()
    
    # Pobierz unikalne wartości dla dropdown maszyn
    if not df_long.empty:
        # Utwórz listę maszyn (kod + nazwa)
        maszyny_df = df_long[['Kod', 'Nazwa']].drop_duplicates().sort_values('Kod')
        maszyny = []
        for _, row in maszyny_df.iterrows():
            kod = row['Kod']
            nazwa = row['Nazwa']
            if nazwa and nazwa.strip():
                maszyny.append({'kod': kod, 'label': f"{kod} {nazwa}"})
            else:
                maszyny.append({'kod': kod, 'label': kod})
        
        # Domyślna maszyna
        default_kod = maszyny[0]['kod'] if maszyny else ''
        default_nazwa = maszyny[0]['label'] if maszyny else ''
        
        # Wygeneruj początkowy wykres kombinowany
        fig = go.Figure()
        
        # Kolory dla brygad (słupki)
        kolory_slupki = {'A': '#0ea5e9', 'B': '#FF6B35', 'C': '#6b7280'}  # niebieski, pomarańczowy, szary
        kolory_linie = {'A': '#0284c7', 'B': '#f97316', 'C': '#4b5563'}  # ciemniejsze odcienie
        
        # Dodaj słupki dla wartości dziennych (brygady A, B, C) - oś Y lewa
        for brygada in ['A', 'B', 'C']:
            mask = (df_long['Typ'] == 'Dzienne') & (df_long['Kod'] == default_kod) & (df_long['Brygada'] == brygada)
            filtered = df_long[mask].copy().sort_values('Dzien')
            
            if not filtered.empty:
                fig.add_trace(go.Bar(
                    x=filtered['Dzien'].tolist(),
                    y=filtered['Wartosc'].tolist(),
                    name=brygada,
                    marker_color=kolory_slupki.get(brygada, '#999999'),
                    text=filtered['Wartosc'].tolist(),
                    textposition='outside',
                    texttemplate='%{text:.0f}',
                    yaxis='y'
                ))
        
        # Dodaj linie dla wartości narastających (brygady A, B, C) - oś Y prawa
        for brygada in ['A', 'B', 'C']:
            mask = (df_long['Typ'] == 'Narastające') & (df_long['Kod'] == default_kod) & (df_long['Brygada'] == brygada)
            filtered = df_long[mask].copy().sort_values('Dzien')
            
            if not filtered.empty:
                fig.add_trace(go.Scatter(
                    x=filtered['Dzien'].tolist(),
                    y=filtered['Wartosc'].tolist(),
                    mode='lines+markers',
                    name=f'Narastająco {brygada}',
                    line=dict(color=kolory_linie.get(brygada, '#666666'), width=2),
                    marker=dict(color=kolory_linie.get(brygada, '#666666'), size=6),
                    yaxis='y2'
                ))
        
        # Dodaj linie Cel 0 i Cel 100 (opcjonalnie)
        # Na razie pominięte - można dodać później jeśli potrzebne
        
        # Oblicz maksymalną wartość ze wszystkich danych dla synchronizacji osi Y
        mask_all = df_long['Kod'] == default_kod
        if mask_all.any():
            max_value = df_long[mask_all]['Wartosc'].max()
            max_value = int(max_value * 1.1)  # Dodaj 10% marginesu
        else:
            max_value = 10000  # Wartość domyślna
        
        fig.update_layout(
            title=default_nazwa,
            xaxis_title='',
            hovermode='x unified',
            plot_bgcolor='white',
            paper_bgcolor='white',
            barmode='group',
            showlegend=True,
            legend=dict(
                orientation='h',
                yanchor='bottom',
                y=-0.2,
                xanchor='center',
                x=0.5
            ),
            xaxis=dict(
                showgrid=True,
                gridcolor='#e5e7eb',
                dtick=1
            ),
            yaxis=dict(
                title='Produkcja dzienna',
                showgrid=True,
                gridcolor='#e5e7eb',
                side='left',
                range=[0, max_value]
            ),
            yaxis2=dict(
                title='Produkcja narastająca',
                showgrid=False,
                overlaying='y',
                side='right',
                range=[0, max_value]
            )
        )
        
        # Generuj HTML wykresu z w pełni osadzoną biblioteką Plotly (inline)
        plot_html = plot(fig, output_type='div', include_plotlyjs=True)
        
    else:
        maszyny = []
        default_kod = ''
        default_nazwa = ''
        plot_html = '<div class="text-center text-gray-600 p-8">Brak danych - proszę dodać plik Export.xlsx</div>'
    
    return render_template('wykres.html',
                         maszyny=maszyny,
                         default_kod=default_kod,
                         default_nazwa=default_nazwa,
                         plot_html=plot_html)

@app.route('/api/series')
def api_series():
    """Zwróć dane wszystkich serii dla wykresu kombinowanego w formacie JSON"""
    # Pobierz kod maszyny z query string
    kod = request.args.get('kod', '')
    
    df_long = load_long()
    
    if df_long.empty or not kod:
        return jsonify({
            'series': [],
            'kod': kod,
            'nazwa': ''
        })
    
    # Pobierz nazwę maszyny
    maszyna_df = df_long[df_long['Kod'] == kod][['Nazwa']].drop_duplicates()
    nazwa = maszyna_df.iloc[0]['Nazwa'] if not maszyna_df.empty else ''
    
    # Przygotuj dane dla wszystkich serii
    series_data = []
    
    # Kolory dla brygad
    kolory_slupki = {'A': '#0ea5e9', 'B': '#FF6B35', 'C': '#6b7280'}
    kolory_linie = {'A': '#0284c7', 'B': '#f97316', 'C': '#4b5563'}
    
    # Słupki dla wartości dziennych (brygady A, B, C) - oś Y lewa
    for brygada in ['A', 'B', 'C']:
        mask = (df_long['Typ'] == 'Dzienne') & (df_long['Kod'] == kod) & (df_long['Brygada'] == brygada)
        filtered = df_long[mask].copy().sort_values('Dzien')
        
        if not filtered.empty:
            series_data.append({
                'type': 'bar',
                'name': brygada,
                'x': filtered['Dzien'].tolist(),
                'y': filtered['Wartosc'].tolist(),
                'color': kolory_slupki.get(brygada, '#999999'),
                'yaxis': 'y'
            })
    
    # Linie dla wartości narastających (brygady A, B, C) - oś Y prawa
    for brygada in ['A', 'B', 'C']:
        mask = (df_long['Typ'] == 'Narastające') & (df_long['Kod'] == kod) & (df_long['Brygada'] == brygada)
        filtered = df_long[mask].copy().sort_values('Dzien')
        
        if not filtered.empty:
            series_data.append({
                'type': 'line',
                'name': f'Narastająco {brygada}',
                'x': filtered['Dzien'].tolist(),
                'y': filtered['Wartosc'].tolist(),
                'color': kolory_linie.get(brygada, '#666666'),
                'yaxis': 'y2'
            })
    
    return jsonify({
        'series': series_data,
        'kod': kod,
        'nazwa': nazwa
    })

# ==================== URUCHOMIENIE APLIKACJI ====================

def load_jumbo():
    """Wczytaj dane z pliku Jumbo.xlsx"""
    try:
        df = pd.read_excel('Jumbo.xlsx', engine='openpyxl')
        
        # Standaryzacja nazw kolumn - usuwamy białe znaki
        df.columns = [str(c).strip() for c in df.columns]
        
        # Konwersja mtf_report_date (jeśli to serial Excela)
        if 'mtf_report_date' in df.columns:
            # Sprawdź czy to liczby (serial Excela)
            if pd.api.types.is_numeric_dtype(df['mtf_report_date']):
                # Konwersja seriala Excela (start od 1899-12-30 dla openpyxl/pandas)
                df['mtf_report_date'] = pd.to_datetime(df['mtf_report_date'], unit='D', origin='1899-12-30')
            else:
                df['mtf_report_date'] = pd.to_datetime(df['mtf_report_date'], errors='coerce')
        
        return df
    except Exception as e:
        print(f"Błąd wczytywania Jumbo.xlsx: {e}")
        return pd.DataFrame()

@app.route('/api/jumbo-data')
def get_jumbo_data():
    """API dla wykresu wydajności z Jumbo.xlsx"""
    try:
        segments = request.args.getlist('segments[]')
        brygada = request.args.get('brygada', 'All')
        
        df = load_jumbo()
        if df.empty:
            return jsonify({'series': []})
            
        # Mapowanie kolumn technicznych - szukanie najbardziej zbliżonych
        cols = df.columns.tolist()
        
        # Szukamy kolumn technicznych ignorując wielkość liter i spacje
        col_map = {}
        for tech in ['mtf_report_date', 'Speed_m2_wh', 'Cum_Speed_m2_wh', 'Segment', 'Brygada']:
            # Najpierw szukamy dokładnego dopasowania (case-insensitive i strip)
            found = next((c for c in cols if c.lower().strip() == tech.lower()), None)
            
            # Jeśli nie znaleziono, spróbuj znaleźć po fragmentach dla kolumn prędkości
            if not found:
                if 'speed' in tech.lower() and 'cum' not in tech.lower():
                    # SZUKAMY DOKŁADNIE: Prędkość dzienna [m2/wh]
                    found = next((c for c in cols if 'prędkość dzienna' in c.lower()), None)
                elif 'cum_speed' in tech.lower():
                    # SZUKAMY DOKŁADNIE: Narastająca prędkość [m2/wh]
                    found = next((c for c in cols if 'narastająca prędkość' in c.lower()), None)
                elif 'date' in tech.lower():
                    found = next((c for c in cols if 'dzień' in c.lower()), None)
                elif 'segment' in tech.lower():
                    found = next((c for c in cols if 'segment' in c.lower()), None)
                elif 'brygada' in tech.lower():
                    found = next((c for c in cols if 'brygada' in c.lower()), None)

            if found:
                col_map[tech] = found
                print(f"✅ Zmapowano {tech} -> {found}")
            else:
                if tech == 'mtf_report_date':
                    # Jeśli nadal brak mtf_report_date, spróbuj użyć kolumny 'Dzień'
                    date_like = next((c for c in cols if 'dzień' in c.lower()), None)
                    if date_like:
                        col_map[tech] = date_like
                        print(f"⚠️ Używam {date_like} jako mtf_report_date")
                    else:
                        print(f"❌ Brak wymaganej kolumny technicznej: {tech}. Dostępne: {cols}")
                        return jsonify({'series': [], 'error': f"Brak kolumny {tech}"})
                else:
                    # Jeśli nie znaleziono kolumny prędkości, to krytyczny błąd
                    if tech in ['Speed_m2_wh', 'Cum_Speed_m2_wh']:
                        print(f"❌ Brak wymaganej kolumny z Excela: {tech}")
                        return jsonify({'series': [], 'error': f"Brak kolumny {tech}"})
                    col_map[tech] = tech # Fallback

        # Używamy zmapowanych kolumn
        date_col = col_map['mtf_report_date']
        speed_col = col_map['Speed_m2_wh']
        cum_col = col_map['Cum_Speed_m2_wh']
        seg_col = col_map['Segment']
        bryg_col = col_map['Brygada']

        # Czyszczenie i konwersja typów
        df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
        df = df.dropna(subset=[date_col])
        
        # Filtrowanie brygady
        if brygada != 'All':
            df = df[df[bryg_col].astype(str).str.contains(brygada, case=False, na=False)]
            
        # Filtrowanie segmentów
        if segments:
            df = df[df[seg_col].isin(segments)]
        
        if df.empty:
            return jsonify({'series': []})

        # Ograniczenie zakresu do ostatnich 14 dni aktywności w danych
        max_date = df[date_col].max()
        min_date_limit = max_date - pd.Timedelta(days=14)
        df = df[df[date_col] > min_date_limit]
        
        # Przygotowanie osi X (posortowane unikalne daty)
        unique_days = sorted(df[date_col].unique())
        unique_days_str = [d.strftime('%d.%m.%Y') for d in pd.to_datetime(unique_days)]
        
        series_data = []
        kolory_slupki = {'Amazon': '#004E89', 'Reszta': '#15803d'}
        kolory_narastajace = {'Amazon': '#FF6B35', 'Reszta': '#38bdf8'}
        
        for segment in segments:
            seg_df = df[df[seg_col] == segment].copy()
            if seg_df.empty:
                continue
            
            # Konwersja na liczby
            seg_df[speed_col] = pd.to_numeric(seg_df[speed_col], errors='coerce').fillna(0)
            seg_df[cum_col] = pd.to_numeric(seg_df[cum_col], errors='coerce').fillna(0)
            
            # Agregacja: SUM dla dziennej, LAST dla narastającej (zgodnie z logiką analityczną)
            # Sortujemy po dacie przed agg aby 'last' było poprawne
            seg_df = seg_df.sort_values(date_col)
            seg_df['Dzien_Str'] = seg_df[date_col].dt.strftime('%d.%m.%Y')
            
            grouped = seg_df.groupby('Dzien_Str').agg({
                speed_col: 'sum',
                cum_col: 'last'
            }).reset_index()
            
            # Sortujemy zgrupowane dane według daty (nie alfabetycznie po stringu)
            grouped['SortDate'] = pd.to_datetime(grouped['Dzien_Str'], format='%d.%m.%Y')
            grouped = grouped.sort_values('SortDate')
            
            # Mapowanie do pełnej listy dni zakresu
            seg_data_daily = []
            seg_data_cum = []
            for d_str in unique_days_str:
                row = grouped[grouped['Dzien_Str'] == d_str]
                seg_data_daily.append(float(row[speed_col].iloc[0]) if not row.empty else 0)
                seg_data_cum.append(float(row[cum_col].iloc[0]) if not row.empty else 0)

            if any(seg_data_daily) or any(seg_data_cum):
                # Dzienne jako słupki
                series_data.append({
                    'type': 'bar',
                    'name': f'{segment} (Dziennie)',
                    'x': unique_days_str,
                    'y': [round(v, 0) for v in seg_data_daily],
                    'color': kolory_slupki.get(segment, '#999999')
                })
                # Narastające jako linia
                series_data.append({
                    'type': 'line',
                    'name': f'{segment} (Narastająco)',
                    'x': unique_days_str,
                    'y': [round(v, 0) for v in seg_data_cum],
                    'color': kolory_narastajace.get(segment, '#cccccc'),
                    'line': {'width': 3},
                    'marker': {'size': 8}
                })
                
        return jsonify({'series': series_data})
    except Exception as e:
        print(f"Błąd API jumbo: {e}")
        return jsonify({'series': [], 'error': str(e)})

if __name__ == '__main__':
    # Inicjalizuj bazę danych
    init_db()
    
    # Utwórz folder na zdjęcia jeśli nie istnieje
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Wymuś inicjalizację bazy przy starcie (dodatkowe zabezpieczenie)
    init_db()
    
    # Uruchom serwer produkcyjny Waitress
    print("=" * 60)
    print("🚀 Firmowy Kiosk - Aplikacja uruchomiona!")
    print("=" * 60)
    print("📍 Adres lokalny: http://0.0.0.0:5000")
    print("🔐 Panel admina: http://0.0.0.0:5000/admin")
    print("🔑 PIN administracyjny: 7456")
    print("=" * 60)
    
    # Bind do 0.0.0.0:5000 dla Replit
    serve(app, host='0.0.0.0', port=5000, threads=4)
