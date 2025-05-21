from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import os
import json

app = Flask(__name__)
app.secret_key = os.urandom(24)

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
# Add a default user if the DB is empty (for testing)
# And ensure existing entries have the new field (important for this KeyError)
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
else: # Loop through existing users to ensure they have the new field
    for user_id, details in users_db.items():
        if "profile_picture_base64" not in details:
            details["profile_picture_base64"] = ""
    save_users_db(users_db) # Save updated structure

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
    
    # --- MODIFIED LINES FOR KEYERROR FIX ---
    # Use .get() method to safely retrieve data, providing a default empty string if key is missing
    session['logged_in'] = True
    session['user_email'] = email
    session['user_fullname'] = users_db[user_id].get('fullname', '') # Use .get()
    session['user_phonenumber'] = users_db[user_id].get('phonenumber', '') # Use .get()
    session['profile_picture_base64'] = users_db[user_id].get('profile_picture_base64', '') # Use .get()
    # --- END MODIFIED LINES ---

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
    profile_picture_base64 = data.get('photoId', '') # Changed from 'profilePicture' to 'photoId' to match verification.html
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
    users_db = load_users_db() # Reload DB to apply initial fix
    if not users_db: # Re-initialize if empty
        users_db = {
            "test@example.com": {
                "password": "password123",
                "fullname": "",
                "phonenumber": "",
                "profile_picture_base64": ""
            }
        }
        save_users_db(users_db)
    else: # This block handles existing users from old JSON structure
        needs_save = False
        for user_id, details in users_db.items():
            if "fullname" not in details: # Ensure all fields are present
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

    app.run(debug=True)