import os
import sqlite3
import resend

from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import smtplib
from email.message import EmailMessage

app = Flask('globalcare health')
app.secret_key = 'medi_go_ease'

# CORRECT WAY (Uses environment variable securely):
resend.api_key = os.environ.get("RESEND_API_KEY")
ADMIN_EMAIL = "medigoease@gmail.com"  # Replace with your actual inbox email

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn
@app.route('/submit', methods=['POST'])

def submit_inquiry():
    name = request.form.get('name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    treatment = request.form.get('treatment')
    destination = request.form.get('destination')
    message = request.form.get('message')
    
    # 1. Save to SQLite Database (Admin Portal) - This is instant and reliable
    try:
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO inquiries (name, email, phone, treatment, destination, message)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (name, email, phone, treatment, destination, message))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Database Error: {e}")

    try:
        params = {
            "from": "GlobalCare Health <onboarding@resend.dev>",
            "to": [ADMIN_EMAIL],
            "subject": f"New Medical Tourism Inquiry from {name}",
            "html": f"""
                <h2>New Patient Inquiry Received</h2>
                <p><b>Name:</b> {name}</p>
                <p><b>Email:</b> {email}</p>
                <p><b>Phone:</b> {phone}</p>
                <p><b>Treatment:</b> {treatment}</p>
                <p><b>Destination:</b> {destination}</p>
                <p><b>Message:</b> {message}</p>
            """
        }
        resend.Emails.send(params)
    except Exception as e:
        print(f"Email Error: {e}")

    flash('Your inquiry has been submitted successfully!', 'success')
    return redirect(url_for('contact'))

    # Helper function to connect to SQLite database
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

# Initialize database table for users if it doesn't exist
def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- Patient Authentication Routes ---

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        password = generate_password_hash(request.form['password'])
        
        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO users (name, email, phone, password) VALUES (?, ?, ?, ?)',
                         (name, email, phone, password))
            conn.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Email address already registered.', 'error')
        finally:
            conn.close()
            
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['user_email'] = user['email']
            flash('Logged in successfully!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password.', 'error')
            
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    # You can also fetch user bookings here if you have an inquiries table!
    conn.close()
    
    return render_template('dashboard.html', user=user)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'doc', 'docx'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    # Inquiries/Leads Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inquiries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            treatment TEXT NOT NULL,
            destination TEXT NOT NULL,
            message TEXT,
            filename TEXT,
            status TEXT DEFAULT 'New Lead',
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Doctors Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS doctors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            specialty TEXT NOT NULL,
            experience TEXT NOT NULL,
            background TEXT NOT NULL
        )
    ''')
    
    # Hospitals Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS hospitals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            location TEXT NOT NULL,
            description TEXT NOT NULL
        )
    ''')
    
    # Testimonials Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS testimonials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_name TEXT NOT NULL,
            country TEXT NOT NULL,
            review TEXT NOT NULL
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# --- Public Multi-Page Routes ---
@app.route('/')
def home():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM testimonials')
    testimonials = cursor.fetchall()
    conn.close()
    return render_template('index.html', testimonials=testimonials)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/hospitals')
def hospitals():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM hospitals')
    hospitals_list = cursor.fetchall()
    conn.close()
    return render_template('hospitals.html', hospitals=hospitals_list)

@app.route('/doctors')
def doctors():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM doctors')
    doctors_list = cursor.fetchall()
    conn.close()
    return render_template('doctors.html', doctors=doctors_list)

@app.route('/treatments')
def treatments():
    return render_template('treatments.html')

@app.route('/cost-estimator')
def cost_estimator():
    return render_template('estimator.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        treatment = request.form.get('treatment')
        destination = request.form.get('destination')
        message = request.form.get('message')

        file = request.files.get('medical_report')
        filename = None
        if file and allowed_file(file.filename):
            filename = file.filename
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO inquiries (name, email, phone, treatment, destination, message, filename)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (name, email, phone, treatment, destination, message, filename))
        conn.commit()
        conn.close()

        return render_template('success.html', name=name, treatment=treatment, destination=destination)
    
    return render_template('contact.html')

# --- Admin Portal & Dynamic Content Management ---
@app.route('/admin')
def admin_dashboard():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM inquiries ORDER BY date DESC')
    leads = cursor.fetchall()
    
    cursor.execute('SELECT * FROM doctors')
    doctors = cursor.fetchall()
    
    cursor.execute('SELECT * FROM hospitals')
    hospitals = cursor.fetchall()
    
    cursor.execute('SELECT * FROM testimonials')
    testimonials = cursor.fetchall()
    
    conn.close()
    return render_template('admin.html', leads=leads, doctors=doctors, hospitals=hospitals, testimonials=testimonials)

@app.route('/update-status/<int:lead_id>', methods=['POST'])
def update_status(lead_id):
    new_status = request.form.get('status')
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE inquiries SET status = ? WHERE id = ?', (new_status, lead_id))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/add-doctor', methods=['POST'])
def add_doctor():
    name = request.form.get('name')
    specialty = request.form.get('specialty')
    experience = request.form.get('experience')
    background = request.form.get('background')
    
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO doctors (name, specialty, experience, background) VALUES (?, ?, ?, ?)',
                   (name, specialty, experience, background))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/add-hospital', methods=['POST'])
def add_hospital():
    name = request.form.get('name')
    location = request.form.get('location')
    description = request.form.get('description')
    
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO hospitals (name, location, description) VALUES (?, ?, ?)',
                   (name, location, description))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/add-testimonial', methods=['POST'])
def add_testimonial():
    patient_name = request.form.get('patient_name')
    country = request.form.get('country')
    review = request.form.get('review')
    
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO testimonials (patient_name, country, review) VALUES (?, ?, ?)',
                   (patient_name, country, review))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
