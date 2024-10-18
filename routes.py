from flask import Flask, request, jsonify, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
from config import SECRET_KEY, DATABASE_HOST, DATABASE_USER, DATABASE_PASSWORD, DATABASE_NAME

app = Flask(__name__)
app.secret_key = SECRET_KEY  # Set a strong secret key!

# Database connection (move this to a separate file later)
mydb = mysql.connector.connect(
    host=DATABASE_HOST,
    user=DATABASE_USER,
    password=DATABASE_PASSWORD,
    database=DATABASE_NAME
)

@app.route('/register', methods=['POST'])
def register():
    print(request.url) 
    data = request.get_json()
    print(data)
    username = data.get('username')
    password = data.get('password')

    first_name = data.get('first_name')
    last_name = data.get('last_name')
    email = data.get('email')

    role = data.get('role')

    # data validation  
    if not all([username, password, first_name, last_name, email, role]):
        return jsonify({'message': 'Missing required fields'}), 400

    hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

    cursor = mydb.cursor()
    try:
        cursor.execute("INSERT INTO User (Username, Password, FirstName, LastName, Email, Role) VALUES (%s, %s, %s, %s, %s, %s)",
                       (username, hashed_password, first_name, last_name, email, role))
        mydb.commit()
        return jsonify({'message': 'User registered successfully'}), 201
    except mysql.connector.Error as err:
        print(f"Error during registration: {err}")
        return jsonify({'message': 'Registration failed'}), 500

@app.route('/login', methods=['POST'])
def login():
    print(request.url) 
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    # Basic data validation
    if not all([username, password]):
        return jsonify({'message': 'Missing username or password'}), 400

    cursor = mydb.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM User WHERE Username = %s", (username,))
        user = cursor.fetchone()

        if user and check_password_hash(user['Password'], password):

            session['user_id'] = user['UserID']  # Store user ID in session
            return jsonify({'message': 'Login successful', 'user_id': user['UserID']}), 200
        else:
            return jsonify({'message': 'Invalid credentials'}), 401
    except mysql.connector.Error as err:
        print(f"Error during login: {err}")
        return jsonify({'message': 'Login failed'}), 500
    
@app.route('/logout')
def logout():
    print(request.url) 
    session.pop('user_id', None)
    return jsonify({'message': 'Logged out'}), 200

if __name__ == '__main__':
    app.run(debug=True) 