from flask import Flask, request, jsonify, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
from config import SECRET_KEY, DATABASE_HOST, DATABASE_USER, DATABASE_PASSWORD, DATABASE_NAME
import datetime

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

@app.route('/courses', methods=['POST'])
def create_course():
    if 'user_id' not in session:
        return jsonify({'message': 'Unauthorized'}), 401

    data = request.get_json()
    course_name = data.get('course_name')
    course_code = data.get('course_code')
    year = data.get('year')
    semester = data.get('semester')

    # Data validation
    if not all([course_name, course_code, year, semester]):
        return jsonify({'message': 'Missing required fields'}), 400

    # Get the role of the logged-in user
    cursor = mydb.cursor(dictionary=True)
    try:
        cursor.execute("SELECT Role FROM User WHERE UserID = %s", (session['user_id'],))
        user = cursor.fetchone()
        if user and user['Role'] == 'professor':
            # Only allow professors to create courses
            instructor_id = session['user_id']
            cursor.execute("INSERT INTO Course (CourseName, CourseCode, InstructorID, Year, Semester) VALUES (%s, %s, %s, %s, %s)",
                           (course_name, course_code, instructor_id, year, semester))
            mydb.commit()

            # Get the newly created course ID
            course_id = cursor.lastrowid  # This gets the ID of the last inserted row

            return jsonify({'message': 'Course created successfully', 'course_id': course_id}), 201
        else:
            return jsonify({'message': 'Only professors can create courses'}), 403  # Forbidden
    except mysql.connector.Error as err:
        print(f"Error creating course: {err}")
        return jsonify({'message': 'Failed to create course'}), 500

@app.route('/courses/<int:course_id>/assignments', methods=['POST'])
def create_assignment(course_id):
    if 'user_id' not in session:
        return jsonify({'message': 'Unauthorized'}), 401

    data = request.get_json()
    title = data.get('title')
    description = data.get('description')
    due_date_str = data.get('due_date')  # Get due_date as a string

    # Data validation
    if not all([title, due_date_str]):
        return jsonify({'message': 'Missing required fields'}), 400

    # Parse the due_date string into a datetime object (compatible with MySQL DATETIME)
    try:
        due_date = datetime.datetime.strptime(due_date_str, '%Y-%m-%d %H:%M:%S')  # Example format: '2024-12-31 23:59:59'
    except ValueError:
        return jsonify({'message': 'Invalid due_date format. Please use YYYY-MM-DD HH:MM:SS'}), 400

    # Get the role of the logged-in user
    cursor = mydb.cursor(dictionary=True)
    try:
        cursor.execute("SELECT Role FROM User WHERE UserID = %s", (session['user_id'],))
        user = cursor.fetchone()
        if user and user['Role'] == 'professor':
            # Only allow professors to create assignments
            cursor.execute("INSERT INTO Assignment (CourseID, Title, Description, DueDate) VALUES (%s, %s, %s, %s)",
                           (course_id, title, description, due_date))  # Use the parsed due_date object
            mydb.commit()
            return jsonify({'message': 'Assignment created successfully'}), 201
        else:
            return jsonify({'message': 'Only professors can create assignments'}), 403  # Forbidden
    except mysql.connector.Error as err:
        print(f"Error creating assignment: {err}")
        return jsonify({'message': 'Failed to create assignment'}), 500

if __name__ == '__main__':
    app.run(debug=True) 