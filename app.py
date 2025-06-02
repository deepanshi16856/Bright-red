from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS
from flask_mail import Mail, Message
import re,random
from math import radians, sin, cos, asin, sqrt
from flask import make_response
import string,pyodbc,time
from geopy.geocoders import Nominatim
import requests
from datetime import timedelta
from chatbot import get_bot_reply  

geolocator = Nominatim(user_agent="organ_donation_app")

app = Flask(__name__)
CORS(app)

app.secret_key = 'your_secret_key'  # Use a strong secret key
app.permanent_session_lifetime = timedelta(minutes=15)

# Database connection
conn = pyodbc.connect(
    'DRIVER={ODBC Driver 17 for SQL Server};'
    'SERVER=LAPTOP-0KRNNRJ1\\SQLEXPRESS;'
    'DATABASE=OrganDonationDB;'
    'Trusted_Connection=yes;'
)

# Mail configuration
app.config.update(
    MAIL_SERVER='smtp.gmail.com',
    MAIL_PORT=587,
    MAIL_USE_TLS=True,
    MAIL_USERNAME='khushi.tikoo10@gmail.com',
    MAIL_PASSWORD='bwir fecb kaja dpyz'
)

mail = Mail(app)

# Helper functions
def generate_token(length=30):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def generate_otp():
    return random.randint(100000, 999999)

def send_email(email, token):
    verify_link = f"http://localhost:5000/verify_email?token={token}"
    msg = Message('Verify Your Email', sender=app.config['MAIL_USERNAME'], recipients=[email])
    msg.body = f'Click the link to verify your email: {verify_link}'
    mail.send(msg)

def send_otp_to_mobile(contact, otp):
    print(f"[DEBUG] OTP for {contact}: {otp}")

# Validators
def is_valid_aadhar(aadhar):
    aadhar = str(aadhar).strip()
    return re.fullmatch(r'\d{12}', aadhar) is not None

def is_valid_phone(phone):
    return re.fullmatch(r'[6-9]\d{9}', phone) is not None

def is_valid_email(email):
    return re.fullmatch(r"[^@]+@[^@]+\.[^@]+", email) is not None

def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in km
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2)**2
    c = 2 * asin(sqrt(a))
    return R * c

# Function to get lat/lon using Nominatim
def get_lat_lon(city):
    try:
        url = f"https://nominatim.openstreetmap.org/search"
        params = {
            "q": city,
            "format": "json",
            "limit": 1
        }
        headers = {
            "User-Agent": "OrganDonationApp/1.0"
        }
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()
        if data:
            return float(data[0]['lat']), float(data[0]['lon'])
    except Exception as e:
        print(f"Error for {city}: {e}")
    return None, None

# Missing helper functions that were referenced but not defined
def get_matched_pairs():
    """Get matched donor-recipient pairs"""
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT d.DonorID, r.Recipient_ID
            FROM Donors d
            JOIN Recipients r ON d.BloodGroup = r.BloodGroup
            WHERE d.latitude IS NOT NULL AND d.longitude IS NOT NULL
            AND r.latitude IS NOT NULL AND r.longitude IS NOT NULL
        """)
        return cursor.fetchall()
    except Exception as e:
        print(f"Error getting matched pairs: {e}")
        return []

def get_all_donors():
    """Get all donors with coordinates"""
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT DonorID, FullName, BloodGroup, OrganToDonate, latitude, longitude
            FROM Donors
            WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        """)
        return [{'id': row[0], 'name': row[1], 'blood_group': row[2], 
                'organ': row[3], 'lat': row[4], 'lon': row[5]} for row in cursor.fetchall()]
    except Exception as e:
        print(f"Error getting donors: {e}")
        return []

def get_all_recipients():
    """Get all recipients with coordinates"""
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT Recipient_ID, FullName, BloodGroup, OrgansNeeded, latitude, longitude
            FROM Recipients
            WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        """)
        return [{'id': row[0], 'name': row[1], 'blood_group': row[2], 
                'organ': row[3], 'lat': row[4], 'lon': row[5]} for row in cursor.fetchall()]
    except Exception as e:
        print(f"Error getting recipients: {e}")
        return []

def get_user_by_id(user_id):
    """Get user data by ID"""
    cursor = conn.cursor()
    try:
        # Try donors first
        cursor.execute("""
            SELECT DonorID, FullName, BloodGroup, OrganToDonate, latitude, longitude
            FROM Donors WHERE DonorID = ?
        """, (user_id,))
        result = cursor.fetchone()
        if result:
            return {'id': result[0], 'name': result[1], 'blood_group': result[2], 
                   'organ': result[3], 'lat': result[4], 'lon': result[5]}
        
        # Try recipients
        cursor.execute("""
            SELECT Recipient_ID, FullName, BloodGroup, OrgansNeeded, latitude, longitude
            FROM Recipients WHERE Recipient_ID = ?
        """, (user_id,))
        result = cursor.fetchone()
        if result:
            return {'id': result[0], 'name': result[1], 'blood_group': result[2], 
                   'organ': result[3], 'lat': result[4], 'lon': result[5]}
    except Exception as e:
        print(f"Error getting user by ID: {e}")
    return None

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

# Routes
@app.route('/')
def main():
    return render_template('main.html')

@app.route('/quiz')
def quiz():
    return render_template('quiz.html')

@app.route('/organ-game')
def organ_game():
    return render_template('organ_game.html')

@app.route('/chat')
def chat():
    return render_template('chatbot.html')

@app.route("/chatbot", methods=["POST"])
def chatbot_reply():
    data = request.json
    message = data.get("message", "")
    
    if not message.strip():
        return jsonify({"response": "Please enter a message."})
    
    reply = get_bot_reply(message)
    if reply is None:
        reply = "Sorry, I couldn't understand that. Try rephrasing."
    
    return jsonify({"reply": reply})

@app.route('/register')
def register():
    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    if 'user_name' not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for('login'))
    return render_template('dashboard.html')

@app.route('/form', methods=['GET', 'POST'])
def form():
    if request.method == 'POST':
        # Handle form submission and redirect to password page
        data = request.form.to_dict()
        return render_template('donor_password.html', personal_data=data)
    return render_template('form.html')

@app.route('/recipient_form', methods=['GET', 'POST'])
def recipient_form():
    if request.method == 'POST':
        # Handle form submission and redirect to password page
        data = request.form.to_dict()
        return render_template('recipient_password.html', personal_data=data)
    return render_template('recipient_form.html')

@app.route('/donor_password', methods=['GET', 'POST'])
def donor_password():
    if request.method == 'POST':
        data = request.form.to_dict()
        return render_template('donor_password.html', personal_data=data)
    return render_template('donor_password.html')

@app.route('/recipient_password', methods=['GET', 'POST'])
def recipient_password():
    if request.method == 'POST':
        data = request.form.to_dict()
        return render_template('recipient_password.html', personal_data=data)
    return render_template('recipient_password.html')

@app.route('/register_donor', methods=['POST'])
def register_donor():
    data = request.form.to_dict()

    password = data.get('password')
    confirm_password = data.get('confirm_password')

    if password != confirm_password:
        flash("Passwords do not match.")
        print(f"Password: {password}, Confirm: {confirm_password}")
        return render_template('donor_password.html', personal_data=data)

    if 'terms' not in data:
        flash("You must accept the terms and conditions.")
        return render_template('donor_password.html', personal_data=data)

    aadhar = data.get('Aadhar')
    phone = data['contact']
    email = data['email']

    if not is_valid_aadhar(aadhar):
        flash("Invalid Aadhar number. It should be a 12-digit number.")
        return redirect(url_for('form'))

    if not is_valid_phone(phone):
        flash("Invalid phone number. Enter a valid 10-digit Indian mobile number.")
        return redirect(url_for('form'))

    if not is_valid_email(email):
        flash("Invalid email address format.")
        return redirect(url_for('form'))

    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM Donors WHERE AadharNo = ? OR ContactNumber = ? OR Email = ?
    """, (aadhar, phone, email))

    if cursor.fetchone():
        flash("A donor with the same Aadhar, phone number, or email already exists.")
        return redirect(url_for('form'))

    city = data['City']
    try:
        location = geolocator.geocode(city)
        if location is None:
            raise ValueError("Could not determine coordinates")
        latitude = location.latitude
        longitude = location.longitude
    except Exception as e:
        flash("Unable to determine location coordinates. Try using a different or more specific city name.")
        return redirect(url_for('form'))

    password_hash = generate_password_hash(password)
    token = generate_token()
    otp = generate_otp()

    cursor.execute("""
        INSERT INTO Donors 
        (FullName, Age, Gender, BloodGroup, OrganToDonate, City, ContactNumber, Email, AadharNo, PasswordHash, email_verification_token, otp, is_email_verified, is_mobile_verified, latitude, longitude) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?, ?)
    """, (
        data['full_name'], data['age'], data['gender'], data['bloodGroup'],
        ', '.join(request.form.getlist('organ')), city, phone,
        email, aadhar, password_hash, token, otp, latitude, longitude
    ))
    conn.commit()

    send_email(email, token)
    send_otp_to_mobile(phone, otp)

    return redirect(url_for('thank_you', msg='Check your email and mobile for verification.'))

@app.route('/register_recipient', methods=['POST'])
def register_recipient():
    data = request.form.to_dict()

    password = data.get('password')
    confirm_password = data.get('confirm_password')

    if password != confirm_password:
        flash("Passwords do not match.")
        return render_template('recipient_password.html', personal_data=data)

    if 'terms' not in data:
        flash("You must accept the terms and conditions.")
        return render_template('recipient_password.html', personal_data=data)

    aadhar = data.get('Aadhar')
    phone = data['contact']
    email = data['email']

    if not is_valid_aadhar(aadhar):
        flash("Invalid Aadhar number. It should be a 12-digit number.")
        return redirect(url_for('recipient_form'))

    if not is_valid_phone(phone):
        flash("Invalid phone number. Enter a valid 10-digit Indian mobile number.")
        return redirect(url_for('recipient_form'))

    if not is_valid_email(email):
        flash("Invalid email address format.")
        return redirect(url_for('recipient_form'))

    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM Recipients WHERE AadharNo = ? OR ContactNumber = ? OR Email = ?
    """, (aadhar, phone, email))

    if cursor.fetchone():
        flash("A recipient with the same Aadhar, phone number, or email already exists.")
        return redirect(url_for('recipient_form'))

    city = data['City']
    try:
        location = geolocator.geocode(city)
        if location is None:
            raise ValueError("Could not determine coordinates")
        latitude = location.latitude
        longitude = location.longitude
    except Exception as e:
        flash("Unable to determine location coordinates. Try using a different or more specific city name.")
        return redirect(url_for('recipient_form'))

    password_hash = generate_password_hash(password)
    token = generate_token()
    otp = generate_otp()

    cursor.execute("""
        INSERT INTO Recipients 
        (FullName, Age, Gender, BloodGroup, OrganNeeded, City, ContactNumber, Email, AadharNo, PasswordHash, email_verification_token, otp, is_email_verified, is_mobile_verified, latitude, longitude) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?, ?)
    """, (
        data['full_name'], data['age'], data['gender'], data['bloodGroup'],
        ', '.join(request.form.getlist('organ')), city, phone,
        email, aadhar, password_hash, token, otp, latitude, longitude
    ))
    conn.commit()

    send_email(email, token)
    send_otp_to_mobile(phone, otp)

    return redirect(url_for('thank_you', msg='Check your email and mobile for verification.'))

@app.route('/verify_email')
def verify_email():
    token = request.args.get('token')
    cursor = conn.cursor()

    cursor.execute("SELECT Email FROM Donors WHERE email_verification_token = ?", (token,))
    result = cursor.fetchone()
    if result:
        cursor.execute("UPDATE Donors SET is_email_verified = 1 WHERE email_verification_token = ?", (token,))
        conn.commit()
        email = result[0]
        return render_template('verify_otp.html', email=email)

    cursor.execute("SELECT Email FROM Recipients WHERE email_verification_token = ?", (token,))
    result = cursor.fetchone()
    if result:
        cursor.execute("UPDATE Recipients SET is_email_verified = 1 WHERE email_verification_token = ?", (token,))
        conn.commit()
        email = result[0]
        return render_template('verify_otp.html', email=email)

    return "Invalid or expired token."

@app.route('/verify_otp', methods=['POST'])
def verify_otp():
    otp = request.form['otp']
    email = request.form['email']

    cursor = conn.cursor()

    cursor.execute("SELECT * FROM Donors WHERE Email = ? AND otp = ?", (email, otp))
    if cursor.fetchone():
        cursor.execute("UPDATE Donors SET is_mobile_verified = 1 WHERE Email = ?", (email,))
        conn.commit()
        return "✅ Phone number verified successfully."

    cursor.execute("SELECT * FROM Recipients WHERE Email = ? AND otp = ?", (email, otp))
    if cursor.fetchone():
        cursor.execute("UPDATE Recipients SET is_mobile_verified = 1 WHERE Email = ?", (email,))
        conn.commit()
        return "✅ Phone number verified successfully."

    return "❌ Invalid OTP."

@app.route('/available_donors', methods=['GET']) 
def available_donors():
    if 'user_type' not in session or session['user_type'] != 'recipient':
        flash("Access denied.", "danger")
        return redirect(url_for('login'))

    cursor = conn.cursor()
    query = """
    SELECT FullName, Age, Gender, BloodGroup, OrganToDonate, City, ContactNumber
    FROM Donors WHERE 1=1
    """
    params = []

    organs = request.args.get('organ', '').strip()
    blood_group = request.args.get('blood_group', '').strip()
    city = request.args.get('city', '').strip()

    if organs:
        query += " AND OrganToDonate LIKE ?"
        params.append(f"%{organs}%")
    if blood_group:
        query += " AND BloodGroup = ?"
        params.append(blood_group)
    if city:
        query += " AND LOWER(City) = LOWER(?)"
        params.append(city)

    cursor.execute(query, params)
    rows = cursor.fetchall()
    donors = [{
        'name': row[0], 'age': row[1], 'gender': row[2], 'blood_group': row[3],
        'organ': row[4], 'location': row[5], 'contact': row[6]
    } for row in rows]

    return render_template('available_donors.html', donors=donors)

@app.route('/thank_you')
def thank_you():
    msg = request.args.get('msg', 'Thank you for registering.')
    return render_template('thank_you.html', message=msg)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_type = request.form['user_type']
        identifier = request.form['identifier']
        password = request.form['password']

        cursor = conn.cursor()
        if user_type == 'donor':
            cursor.execute("SELECT DonorID, FullName, BloodGroup, OrganToDonate, City, PasswordHash FROM Donors WHERE Email = ?", (identifier,))
        else:
            cursor.execute("SELECT Recipient_ID, FullName, BloodGroup, OrgansNeeded, City, PasswordHash FROM Recipients WHERE Email = ?", (identifier,))

        result = cursor.fetchone()
        if result and check_password_hash(result[5], password):
            session.permanent = True 
            session.update({
                'user_id': result[0], 'email': identifier, 'user_name': result[1],
                'user_type': user_type, 'blood_group': result[2],
                'organs': result[3], 'city': result[4]
            })
            return redirect(url_for('index'))
        flash("Invalid credentials", "danger")

    response = make_response(render_template('login.html'))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/index')
def index():
    if 'user_name' not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for('login'))

    response = make_response(render_template('index.html', **session))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main'))

@app.route('/logged_out')
def logged_out():
    response = make_response(render_template('main.html'))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

# Fixed map routes
@app.route("/map", methods=['GET'])
def show_map():
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    user_type = session.get("user_type")
    user_id = session.get("user_id")

    matched_pairs = get_matched_pairs()
    all_donors = get_all_donors()
    all_recipients = get_all_recipients()

    if user_type == "donor":
        matched = next((r for d, r in matched_pairs if d == user_id), None)
        return render_template("map.html", donors=[get_user_by_id(user_id)],
                                         recipients=[get_user_by_id(matched)] if matched else [],
                                         show_match=bool(matched), show_all=False)

    elif user_type == "recipient":
        matched = next((d for d, r in matched_pairs if r == user_id), None)
        return render_template("map.html", donors=[get_user_by_id(matched)] if matched else [],
                                         recipients=[get_user_by_id(user_id)],
                                         show_match=bool(matched), show_all=False)

    elif user_type == "admin":
        return render_template("map.html", donors=all_donors, recipients=all_recipients, show_all=True)

    else:
        return redirect(url_for("map"))


@app.route("/get_matches")
def get_matches():
    cursor = conn.cursor()
    try:
        donors = cursor.execute("""
            SELECT FullName, BloodGroup, OrganToDonate, latitude, longitude
            FROM Donors
            WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        """).fetchall()

        recipients = cursor.execute("""
            SELECT FullName, BloodGroup, OrgansNeeded, latitude, longitude
            FROM Recipients
            WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        """).fetchall()

        matches = []
        max_distance_km = 50

        for d in donors:
            donor_organs = [x.strip().lower() for x in d[2].split(',')]
            donor_blood = d[1].lower()
            for r in recipients:
                recipient_organs = [x.strip().lower() for x in r[2].split(',')]
                recipient_blood = r[1].lower()

                if donor_blood == recipient_blood and any(o in donor_organs for o in recipient_organs):
                    dist = haversine(d[3], d[4], r[3], r[4])
                    if dist <= max_distance_km:
                        matches.append({
                            "donor": {
                                "name": d[0],
                                "blood_group": d[1],
                                "organ": d[2],
                                "latitude": d[3],
                                "longitude": d[4]
                            },
                            "recipient": {
                                "name": r[0],
                                "blood_group": r[1],
                                "organ": r[2],
                                "latitude": r[3],
                                "longitude": r[4]
                            },
                            "distance_km": round(dist, 2)
                        })

        return jsonify(matches)

    except Exception as e:
        print(f"Error in /get_matches: {e}")
        return jsonify({"error": "Server error"}), 500
    
@app.route('/get_user_location')
def get_user_location():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "User not logged in"}), 401

    cursor = conn.cursor()
    # Example: assuming you store latitude and longitude in Donors or Recipients
    cursor.execute("""
        SELECT latitude, longitude FROM Donors WHERE DonorID = ?
        UNION
        SELECT latitude, longitude FROM Recipients WHERE Recipient_ID = ?
    """, (user_id, user_id))

    loc = cursor.fetchone()
    if loc and loc[0] is not None and loc[1] is not None:
        return jsonify({"user": {"latitude": loc[0], "longitude": loc[1]}})
    else:
        return jsonify({"error": "Location not found"}), 404


# Initialize database coordinates (run once)
def initialize_coordinates():
    cursor = conn.cursor()
    
    # Update Donors with missing lat/lon
    cursor.execute("SELECT AadharNo, City FROM Donors WHERE latitude IS NULL OR longitude IS NULL")
    donors = cursor.fetchall()

    for donor in donors:
        aadhar, city = donor
        lat, lon = get_lat_lon(city)
        if lat and lon:
            cursor.execute("""
                UPDATE Donors
                SET latitude = ?, longitude = ?
                WHERE AadharNo = ?
            """, (lat, lon, aadhar))
            print(f"Updated Donor {aadhar} - {city} → ({lat}, {lon})")
            conn.commit()
            time.sleep(1)

    # Update Recipients with missing lat/lon
    cursor.execute("SELECT AadharNo, City FROM Recipients WHERE latitude IS NULL OR longitude IS NULL")
    recipients = cursor.fetchall()

    for recipient in recipients:
        aadhar, city = recipient
        lat, lon = get_lat_lon(city)
        if lat and lon:
            cursor.execute("""
                UPDATE Recipients
                SET latitude = ?, longitude = ?
                WHERE AadharNo = ?
            """, lat, lon, aadhar)
            print(f"Updated Recipient {aadhar} - {city} → ({lat}, {lon})")
            conn.commit()
            time.sleep(1)

    cursor.close()

if __name__ == '__main__':
    
    initialize_coordinates()
    app.run(debug=True)