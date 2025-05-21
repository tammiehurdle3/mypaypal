from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import os
import json

app = Flask(__name__)
app.secret_key = os.urandom(24)

# --- Simulate a "database" of users and their info ---
DB_FILE = 'users_db.json'

def load_users_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}

def save_users_db(db):
    with open(DB_FILE, 'w') as f:
        json.dump(db, f, indent=4)

users_db = load_users_db()
if not users_db:
    users_db = {
        "test@example.com": {
            "password": "password123",
            "fullname": "",
            "phonenumber": "",
            "profile_picture_base64": ""
        }
    }
    save_users_db(users_db)
else:
    for user_id, details in users_db.items():
        if "fullname" not in details:
            details["fullname"] = ""
        if "phonenumber" not in details:
            details["phonenumber"] = ""
        if "profile_picture_base64" not in details:
            details["profile_picture_base64"] = ""
    save_users_db(users_db)

# --- ROUTES ---

@app.route('/')
def index():
    if session.get('logged_in'):
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    user_id = email
    if user_id not in users_db:
        users_db[user_id] = {
            "password": password,
            "fullname": "",
            "phonenumber": "",
            "profile_picture_base64": ""
        }
        save_users_db(users_db)
    
    session['logged_in'] = True
    session['user_email'] = email
    session['user_fullname'] = users_db[user_id].get('fullname', '')
    session['user_phonenumber'] = users_db[user_id].get('phonenumber', '')
    session['profile_picture_base64'] = users_db[user_id].get('profile_picture_base64', '')

    return jsonify({'message': 'Login successful'}), 200

@app.route('/verification')
def verification_page():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    return render_template('verification.html')

@app.route('/verify_info', methods=['POST'])
def verify_info():
    if not session.get('logged_in'):
        return jsonify({'message': 'Unauthorized'}), 401

    data = request.get_json()
    new_fullname = data.get('fullName')
    new_phonenumber = data.get('phoneNumber')
    profile_picture_base64 = data.get('photoId', '')
    user_email = session.get('user_email')

    if user_email and user_email in users_db:
        users_db[user_email]['fullname'] = new_fullname
        users_db[user_email]['phonenumber'] = new_phonenumber
        users_db[user_email]['profile_picture_base64'] = profile_picture_base64
        save_users_db(users_db)

        session['user_fullname'] = new_fullname
        session['user_phonenumber'] = new_phonenumber
        session['profile_picture_base64'] = profile_picture_base64

        return jsonify({'message': 'Info updated successfully'}), 200
    else:
        return jsonify({'message': 'User session or data not found'}), 400

@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    return render_template('dashboard.html')

@app.route('/admin_panel')
def admin_panel():
    return render_template('admin.html', users=users_db)

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': 'Logged out successfully'}), 200

if __name__ == '__main__':
    if not os.path.exists('templates'):
        os.makedirs('templates')
    users_db = load_users_db()
    if not users_db:
        users_db = {
            "test@example.com": {
                "password": "password123",
                "fullname": "",
                "phonenumber": "",
                "profile_picture_base64": ""
            }
        }
        save_users_db(users_db)
    else:
        needs_save = False
        for user_id, details in users_db.items():
            if "fullname" not in details:
                details["fullname"] = ""
                needs_save = True
            if "phonenumber" not in details:
                details["phonenumber"] = ""
                needs_save = True
            if "profile_picture_base64" not in details:
                details["profile_picture_base64"] = ""
                needs_save = True
        if needs_save:
            save_users_db(users_db)

    # --- CRITICAL CHANGE FOR RENDER DEPLOYMENT ---
    port = int(os.environ.get("PORT", 5000)) # Get port from environment variable, default to 5000
    app.run(host='0.0.0.0', port=port, debug=False) # Bind to 0.0.0.0 and disable debug for production
    # --- END CRITICAL CHANGE ---