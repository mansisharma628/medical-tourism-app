import os
import sqlite3
from flask import Flask, render_template, request, flash, redirect, url_for, g, session, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import requests
from dotenv import load_dotenv

# Load environment variables from the .env file automatically
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'fallback_secret_key')

# Configuration from .env
DATABASE = 'database.db'
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

BREVO_API_KEY = os.environ.get('BREVO_API_KEY') 
SENDER_EMAIL = os.environ.get('SENDER_EMAIL')   
ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL')               

# Ensure upload folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Database Helper Functions
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        # Users Table
        db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                phone TEXT,
                password TEXT NOT NULL
            )
        ''')
        # Inquiries / Leads Table
        db.execute('''
            CREATE TABLE IF NOT EXISTS inquiries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                phone TEXT NOT NULL,
                treatment TEXT NOT NULL,
                destination TEXT,
                message TEXT,
                filename TEXT,
                status TEXT DEFAULT 'New Lead',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Doctors CMS Table
        db.execute('''
            CREATE TABLE IF NOT EXISTS doctors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                specialty TEXT NOT NULL,
                experience TEXT NOT NULL,
                background TEXT NOT NULL
            )
        ''')
        # Hospitals CMS Table
        db.execute('''
            CREATE TABLE IF NOT EXISTS hospitals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                location TEXT NOT NULL,
                description TEXT NOT NULL
            )
        ''')
        # Testimonials CMS Table
        db.execute('''
            CREATE TABLE IF NOT EXISTS testimonials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_name TEXT NOT NULL,
                country TEXT NOT NULL,
                review TEXT NOT NULL
            )
        ''')
        db.commit()

# --- PUBLIC ROUTES ---
@app.route('/')
def index():
    db = get_db()
    testimonials = db.execute('SELECT * FROM testimonials').fetchall()
    return render_template('index.html', testimonials=testimonials)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/hospitals')
def hospitals():
    db = get_db()
    hospitals_list = db.execute('SELECT * FROM hospitals').fetchall()
    return render_template('hospitals.html', hospitals=hospitals_list)

@app.route('/doctors')
def doctors():
    db = get_db()
    doctors_list = db.execute('SELECT * FROM doctors').fetchall()
    return render_template('doctors.html', doctors=doctors_list)

@app.route('/treatments')
def treatments():
    return render_template('treatment.html')

@app.route('/estimator')
def cost_estimator():
    return render_template('estimator.html')

# --- AUTHENTICATION ROUTES ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        password = generate_password_hash(request.form.get('password'))

        try:
            db = get_db()
            db.execute('INSERT INTO users (name, email, phone, password) VALUES (?, ?, ?, ?)',
                         (name, email, phone, password))
            db.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Email already exists.', 'danger')
            
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        db = get_db()
        user = db.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password.', 'danger')

    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    return render_template('dashboard.html', user=user)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# --- CONTACT & INQUIRY FORM (WITH FILE UPLOAD & BREVO API) ---
@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'GET':
        return render_template('contact.html')

    name = request.form.get('name')
    user_email = request.form.get('email')
    phone = request.form.get('phone')
    treatment = request.form.get('treatment')
    destination = request.form.get('destination')
    message = request.form.get('message')
    
    filename = None
    file = request.files.get('medical_report')
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    if not name or not user_email or not phone:
        flash('Please fill out all required fields.', 'danger')
        return redirect(url_for('contact'))

    # 1. Save to SQLite database
    try:
        db = get_db()
        db.execute('''
            INSERT INTO inquiries (name, email, phone, treatment, destination, message, filename) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (name, user_email, phone, treatment, destination, message, filename))
        db.commit()
    except Exception as e:
        flash(f'Database error: {e}', 'danger')
        return redirect(url_for('contact'))

    # 2. Dispatch Email via Brevo API
    if BREVO_API_KEY:
        brevo_url = "https://api.brevo.com/v3/smtp/email"
        payload = {
            "sender": {"name": "GlobalCare Health Platform", "email": SENDER_EMAIL},
            "to": [{"email": ADMIN_EMAIL, "name": "Admin"}],
            "subject": f"New Medical Inquiry: {treatment} - {name}",
            "htmlContent": f"""
                <h3>New Patient Inquiry Received</h3>
                <p><strong>Name:</strong> {name}</p>
                <p><strong>Email:</strong> {user_email}</p>
                <p><strong>Phone:</strong> {phone}</p>
                <p><strong>Treatment:</strong> {treatment}</p>
                <p><strong>Destination:</strong> {destination}</p>
                <p><strong>Message:</strong> {message}</p>
            """
        }
        headers = {
            "accept": "application/json",
            "api-key": BREVO_API_KEY,
            "content-type": "application/json"
        }
        try:
            requests.post(brevo_url, json=payload, headers=headers)
        except Exception:
            pass 

    flash('Your confidential inquiry has been submitted successfully!', 'success')
    return redirect(url_for('success'))

@app.route('/success')
def success():
    return render_template('success.html')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# --- ADMIN PORTAL & CMS ROUTES ---
@app.route('/admin')
def admin():
    db = get_db()
    leads = db.execute('SELECT * FROM inquiries ORDER BY created_at DESC').fetchall()
    return render_template('admin.html', leads=leads)

@app.route('/update-status/<int:lead_id>', methods=['POST'])
def update_status(lead_id):
    new_status = request.form.get('status')
    db = get_db()
    db.execute('UPDATE inquiries SET status = ? WHERE id = ?', (new_status, lead_id))
    db.commit()
    return redirect(url_for('admin'))

@app.route('/admin/add-doctor', methods=['POST'])
def add_doctor():
    name = request.form.get('name')
    specialty = request.form.get('specialty')
    experience = request.form.get('experience')
    background = request.form.get('background')

    db = get_db()
    db.execute('INSERT INTO doctors (name, specialty, experience, background) VALUES (?, ?, ?, ?)',
                 (name, specialty, experience, background))
    db.commit()
    return redirect(url_for('admin'))

@app.route('/admin/add-hospital', methods=['POST'])
def add_hospital():
    name = request.form.get('name')
    location = request.form.get('location')
    description = request.form.get('description')

    db = get_db()
    db.execute('INSERT INTO hospitals (name, location, description) VALUES (?, ?, ?)',
                 (name, location, description))
    db.commit()
    return redirect(url_for('admin'))

@app.route('/admin/add-testimonial', methods=['POST'])
def add_testimonial():
    patient_name = request.form.get('patient_name')
    country = request.form.get('country')
    review = request.form.get('review')

    db = get_db()
    db.execute('INSERT INTO testimonials (patient_name, country, review) VALUES (?, ?, ?)',
                 (patient_name, country, review))
    db.commit()
    return redirect(url_for('admin'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
