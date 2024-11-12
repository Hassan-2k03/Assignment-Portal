from flask import Flask, request, jsonify, session, redirect, url_for, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import mysql.connector
from config import (SECRET_KEY, DATABASE_HOST, DATABASE_USER, DATABASE_PASSWORD, 
                   DATABASE_NAME, UPLOAD_FOLDER, ALLOWED_EXTENSIONS)
import datetime
import os

app = Flask(__name__)
app.secret_key = SECRET_KEY  # Set a strong secret key!
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max-limit

# Database connection (move this to a separate file later)
mydb = mysql.connector.connect(
    host=DATABASE_HOST,
    user=DATABASE_USER,
    password=DATABASE_PASSWORD,
    database=DATABASE_NAME
)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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

@app.route('/assignments/<int:assignment_id>/submit', methods=['POST'])
def submit_assignment(assignment_id):
    if 'user_id' not in session:
        return jsonify({'message': 'Unauthorized'}), 401

    if 'file' not in request.files:
        return jsonify({'message': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'message': 'No selected file'}), 400

    if file and allowed_file(file.filename):
        # Create submission directory if it doesn't exist
        submission_dir = os.path.join(app.config['UPLOAD_FOLDER'], f'assignment_{assignment_id}')
        os.makedirs(submission_dir, exist_ok=True)
        
        # Secure filename and save file
        filename = secure_filename(f"{session['user_id']}_{file.filename}")
        file_path = os.path.join(submission_dir, filename)
        file.save(file_path)

        cursor = mydb.cursor(dictionary=True)
        try:
            # Record the submission in database
            cursor.execute("""
                INSERT INTO Submission (AssignmentID, StudentID, SubmissionPath, SubmissionDate)
                VALUES (%s, %s, %s, NOW())
            """, (assignment_id, session['user_id'], file_path))
            mydb.commit()
            return jsonify({'message': 'Assignment submitted successfully'}), 201
        except mysql.connector.Error as err:
            print(f"Error recording submission: {err}")
            return jsonify({'message': 'Failed to record submission'}), 500

    return jsonify({'message': 'File type not allowed'}), 400

@app.route('/courses/<int:course_id>/materials', methods=['POST'])
def upload_course_material(course_id):
    if 'user_id' not in session:
        return jsonify({'message': 'Unauthorized'}), 401

    # Verify user is the course instructor
    cursor = mydb.cursor(dictionary=True)
    cursor.execute("SELECT InstructorID FROM Course WHERE CourseID = %s", (course_id,))
    course = cursor.fetchone()
    
    if not course or course['InstructorID'] != session['user_id']:
        return jsonify({'message': 'Unauthorized'}), 403

    if 'file' not in request.files:
        return jsonify({'message': 'No file part'}), 400
    
    file = request.files['file']
    description = request.form.get('description', '')

    if file.filename == '':
        return jsonify({'message': 'No selected file'}), 400

    if file and allowed_file(file.filename):
        # Create materials directory if it doesn't exist
        materials_dir = os.path.join(app.config['UPLOAD_FOLDER'], f'course_{course_id}')
        os.makedirs(materials_dir, exist_ok=True)
        
        filename = secure_filename(file.filename)
        file_path = os.path.join(materials_dir, filename)
        file.save(file_path)

        try:
            # Record the material in database
            cursor.execute("""
                INSERT INTO CourseMaterial (CourseID, FilePath, Description, UploadDate)
                VALUES (%s, %s, %s, NOW())
            """, (course_id, file_path, description))
            mydb.commit()
            return jsonify({'message': 'Material uploaded successfully'}), 201
        except mysql.connector.Error as err:
            print(f"Error recording material: {err}")
            return jsonify({'message': 'Failed to record material'}), 500

    return jsonify({'message': 'File type not allowed'}), 400

@app.route('/download/<path:filename>')
def download_file(filename):
    if 'user_id' not in session:
        return jsonify({'message': 'Unauthorized'}), 401
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)