import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, send_from_directory

app = Flask(__name__)
app.secret_key = 'super-secret-business-key'

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
