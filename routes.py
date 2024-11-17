from flask import Flask, request, jsonify, session, redirect, url_for, send_from_directory, render_template
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import mysql.connector
from config import (SECRET_KEY, DATABASE_HOST, DATABASE_USER, DATABASE_PASSWORD, 
                   DATABASE_NAME, UPLOAD_FOLDER, ALLOWED_EXTENSIONS)
import datetime
import os
from functools import wraps

app = Flask(__name__)
app.secret_key = SECRET_KEY  # Set a strong secret key!
app.config['UPLOAD_FOLDER'] = r'C:\Users\hassa\OneDrive\Documents\Academics\Semester 5\Assignment Portal\uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max-limit

# Database connection 
mydb = mysql.connector.connect(
    host=DATABASE_HOST,
    user=DATABASE_USER,
    password=DATABASE_PASSWORD,
    database=DATABASE_NAME
)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

"""
University Assignment Portal - Route Definitions

This module contains all the route handlers for the assignment portal, organized by:
1. Common Routes (register, login, logout)
2. Admin Routes (course management, enrollment approval)
3. Professor Routes (assignment creation, grading)
4. Student Routes (assignment submission, course enrollment)

Each route is protected with proper authentication and role verification.
"""

# Authentication Middleware
def login_required(f):
    """Decorator to verify user authentication for protected routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'message': 'Please login to access this page', 'redirect': '/login'}), 401
        return f(*args, **kwargs)
    return decorated_function

# Modify the root route to handle role-based redirection
@app.route('/')
def index():
    if 'user_id' in session:
        role = session.get('role')
        if role == 'admin':
            return redirect(url_for('admin_dashboard_page'))
        elif role == 'professor':
            return redirect(url_for('professor_dashboard_page'))
        else:
            return redirect(url_for('student_dashboard_page'))
    return redirect(url_for('login_page'))

# Add new routes for serving HTML pages
@app.route('/login', methods=['GET'])
def login_page():
    if 'user_id' in session:
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/register', methods=['GET'])
def register_page():
    if 'user_id' in session:
        return redirect(url_for('index'))
    return render_template('register.html')

# Add new routes for serving dashboard pages
@app.route('/admin-dashboard-page')
@login_required
def admin_dashboard_page():
    if session.get('role') != 'admin':
        return redirect(url_for('index'))
    return render_template('admin_dashboard.html')

@app.route('/professor-dashboard-page')
@login_required
def professor_dashboard_page():
    if session.get('role') != 'professor':
        return redirect(url_for('index'))
    return render_template('professor_dashboard.html')

@app.route('/student-dashboard-page')
@login_required
def student_dashboard_page():
    if session.get('role') != 'student':
        return redirect(url_for('index'))
    return render_template('student_dashboard.html')

@app.route('/api/assignments/upload', methods=['POST'])
@login_required
def upload_assignment():
    """Handle assignment file uploads from professors."""
    if session.get('role') != 'professor':
        return jsonify({'success': False, 'message': 'Only professors can upload assignments'}), 403

    try:
        # Verify form data
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': 'No file uploaded'}), 400
            
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'message': 'No file selected'}), 400

        title = request.form.get('title')
        description = request.form.get('description')
        due_date = request.form.get('due_date')
        course_id = request.form.get('course_id')

        if not all([title, description, due_date, course_id]):
            return jsonify({'success': False, 'message': 'Missing required fields'}), 400

        cursor = mydb.cursor(dictionary=True)
        
        # Verify professor teaches this course
        cursor.execute("""
            SELECT 1 FROM Course 
            WHERE CourseID = %s AND InstructorID = %s
        """, (course_id, session['user_id']))
        
        if not cursor.fetchone():
            return jsonify({'success': False, 'message': 'You can only upload assignments to your courses'}), 403

        if file and allowed_file(file.filename):
            try:
                # Create assignment directory with unique identifier
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
                assignment_dir = os.path.join(
                    app.config['UPLOAD_FOLDER'], 
                    f'course_{course_id}', 
                    'assignments',
                    f'{timestamp}_{safe_title}'
                )
                os.makedirs(assignment_dir, exist_ok=True)
                
                # Secure filename and save file
                filename = secure_filename(file.filename)
                file_path = os.path.join(assignment_dir, filename)
                file.save(file_path)

                # Create assignment record
                cursor.execute("""
                    INSERT INTO Assignment (CourseID, Title, Description, DueDate, FilePath, CreatedBy, CreatedAt)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW())
                """, (course_id, title, description, due_date, file_path, session['user_id']))
                
                mydb.commit()

                # Create notification for enrolled students
                cursor.execute("""
                    INSERT INTO Notification (UserID, Message, Timestamp)
                    SELECT e.StudentID, 
                           CONCAT('New assignment posted in ', c.CourseName, ': ', %s),
                           NOW()
                    FROM Enrollment e
                    JOIN Course c ON e.CourseID = c.CourseID
                    WHERE e.CourseID = %s AND e.Status = 'active'
                """, (title, course_id))
                
                mydb.commit()
                
                return jsonify({
                    'success': True,
                    'message': 'Assignment uploaded successfully',
                    'assignment_id': cursor.lastrowid
                }), 201
            
            except OSError as e:
                print(f"OS error: {e}")
                return jsonify({'success': False, 'message': 'Failed to save file'}), 500
        
        return jsonify({'success': False, 'message': 'Invalid file type'}), 400

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return jsonify({'success': False, 'message': 'Database error occurred'}), 500
    except Exception as e:
        print(f"Error uploading assignment: {e}")
        return jsonify({'success': False, 'message': 'Failed to upload assignment'}), 500


# ============ Common Routes ============
# Modify existing register route to handle both form and API requests
@app.route('/register', methods=['POST'])
def register():
    """Handle new user registration for all roles."""
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form

    username = data.get('username')
    password = data.get('password')
    first_name = data.get('firstName')
    last_name = data.get('lastName')
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
        
        if request.is_json:
            return jsonify({'message': 'User registered successfully'}), 201
        return redirect(url_for('login_page'))
    except mysql.connector.Error as err:
        print(f"Error during registration: {err}")
        return jsonify({'message': 'Registration failed'}), 500

# Modify login route to handle proper redirections
@app.route('/login', methods=['POST'])
def login():
    """Authenticate users and create session."""
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form

    username = data.get('username')
    password = data.get('password')

    if not all([username, password]):
        return jsonify({'message': 'Missing username or password'}), 400

    cursor = mydb.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM User WHERE Username = %s", (username,))
        user = cursor.fetchone()

        if user and check_password_hash(user['Password'], password):
            session['user_id'] = user['UserID']
            session['role'] = user['Role']
            session['username'] = user['Username']

            # Redirect based on role
            if user['Role'] == 'admin':
                return redirect(url_for('admin_dashboard_page'))
            elif user['Role'] == 'professor':
                return redirect(url_for('professor_dashboard_page'))
            else:
                return redirect(url_for('student_dashboard_page'))
        else:
            return jsonify({'message': 'Invalid credentials'}), 401
    except mysql.connector.Error as err:
        print(f"Error during login: {err}")
        return jsonify({'message': 'Login failed'}), 500

# Modify logout route to redirect to login page
@app.route('/logout')
@login_required
def logout():
    """End user session and logout."""
    session.clear()
    return redirect(url_for('login_page'))

# Add error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('errors/500.html'), 500

# ============ Admin Routes ============
@app.route('/admin-dashboard')
@login_required
def admin_dashboard():
    """Admin dashboard data API endpoint."""
    if session.get('role') != 'admin':
        return jsonify({'message': 'Only admins can access this route'}), 403

    cursor = mydb.cursor(dictionary=True)
    try:
        # Stats query
        cursor.execute("""
            SELECT 
                (SELECT COUNT(*) FROM User WHERE Role = 'student' AND Active = 1) as student_count,
                (SELECT COUNT(*) FROM User WHERE Role = 'professor' AND Active = 1) as professor_count,
                (SELECT COUNT(*) FROM Course) as active_courses,
                (SELECT COUNT(*) FROM Assignment 
                 WHERE DueDate > CURRENT_TIMESTAMP 
                 AND Status = 'active') as active_assignments
        """)
        stats = cursor.fetchone()

        # Courses query with proper joins and GROUP BY
        cursor.execute("""
            SELECT 
                c.CourseID,
                c.CourseCode,
                c.CourseName,
                c.Year,
                c.Semester,
                CONCAT(u.FirstName, ' ', u.LastName) as InstructorName,
                COUNT(DISTINCT e.StudentID) as EnrolledCount
            FROM Course c
            LEFT JOIN User u ON c.InstructorID = u.UserID
            LEFT JOIN Enrollment e ON c.CourseID = e.CourseID
            GROUP BY c.CourseID, c.CourseCode, c.CourseName, c.Year, c.Semester, 
                     u.FirstName, u.LastName
            ORDER BY c.CourseCode
        """)
        courses = cursor.fetchall()

        # Add enrollment requests query
        cursor.execute("""
            SELECT 
                er.RequestID,
                DATE_FORMAT(er.RequestDate, '%Y-%m-%d %H:%i:%s') as RequestDate,
                er.Status,
                c.CourseName,
                c.CourseCode,
                CONCAT(u.FirstName, ' ', u.LastName) as StudentName
            FROM EnrollmentRequest er
            JOIN Course c ON er.CourseID = c.CourseID
            JOIN User u ON er.StudentID = u.UserID
            ORDER BY er.RequestDate DESC
        """)
        enrollment_requests = cursor.fetchall()

        return jsonify({
            'stats': stats,
            'courses': courses,
            'enrollment_requests': enrollment_requests,
            'admin_name': session.get('username')
        }), 200

    except mysql.connector.Error as err:
        print(f"Error fetching dashboard data: {err}")
        return jsonify({'message': 'Error fetching dashboard data'}), 500

@app.route('/api/professors')
@login_required
def get_professors():
    """Get list of all professors for admin dashboard."""
    if session.get('role') != 'admin':
        return jsonify({'message': 'Unauthorized access'}), 403

    cursor = mydb.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT UserID, FirstName, LastName, Email 
            FROM User 
            WHERE Role = 'professor' AND Active = 1
            ORDER BY FirstName, LastName
        """)
        professors = cursor.fetchall()
        return jsonify({'professors': professors}), 200
    except mysql.connector.Error as err:
        print(f"Error fetching professors: {err}")
        return jsonify({'message': 'Failed to fetch professors'}), 500

# Update the existing admin_create_course route
@app.route('/admin/courses/create', methods=['POST'])
@login_required
def admin_create_course():
    """Create new courses and assign professors."""
    if session.get('role') != 'admin':
        return jsonify({'message': 'Only admins can create courses'}), 403

    data = request.get_json()
    required_fields = ['course_name', 'course_code', 'instructor_id', 'year', 'semester']
    
    if not all(field in data for field in required_fields):
        return jsonify({
            'success': False,
            'message': 'Missing required fields'
        }), 400

    # Validate semester is between 1 and 8
    try:
        semester = int(data['semester'])
        if not 1 <= semester <= 8:
            return jsonify({
                'success': False,
                'message': 'Semester must be between 1 and 8'
            }), 400
    except ValueError:
        return jsonify({
            'success': False,
            'message': 'Invalid semester value'
        }), 400

    cursor = mydb.cursor(dictionary=True)
    try:
        # Verify if selected instructor exists and is a professor
        cursor.execute("""
            SELECT UserID, Role 
            FROM User 
            WHERE UserID = %s AND Role = 'professor' AND Active = 1
        """, (data['instructor_id'],))
        
        if not cursor.fetchone():
            return jsonify({
                'success': False,
                'message': 'Selected instructor is not valid'
            }), 400

        # Create the course
        cursor.execute("""
            INSERT INTO Course (CourseName, CourseCode, InstructorID, Year, Semester) 
            VALUES (%s, %s, %s, %s, %s)
        """, (
            data['course_name'],
            data['course_code'],
            data['instructor_id'],
            data['year'],
            semester  # Now using the validated integer value
        ))
        
        mydb.commit()
        
        return jsonify({
            'success': True,
            'message': 'Course created successfully',
            'course_id': cursor.lastrowid
        }), 201

    except mysql.connector.Error as err:
        print(f"Error creating course: {err}")
        return jsonify({
            'success': False,
            'message': 'Failed to create course'
        }), 500

@app.route('/admin/enrollment/approve/<int:request_id>', methods=['POST'])
@login_required
def approve_enrollment(request_id):
    if session.get('role') != 'admin':
        return jsonify({
            'success': False,
            'message': 'Only admins can approve enrollments'
        }), 403

    cursor = mydb.cursor(dictionary=True)
    try:
        # First get the enrollment request details
        cursor.execute("""
            SELECT StudentID, CourseID, Status 
            FROM EnrollmentRequest 
            WHERE RequestID = %s
        """, (request_id,))
        
        request = cursor.fetchone()
        if not request:
            return jsonify({'message': 'Enrollment request not found'}), 404
            
        if request['Status'] != 'pending':
            return jsonify({'message': 'Request has already been processed'}), 400

        # Start transaction
        cursor.execute("START TRANSACTION")
        try:
            # Update request status to approved
            cursor.execute("""
                UPDATE EnrollmentRequest 
                SET Status = 'approved', ProcessedDate = NOW() 
                WHERE RequestID = %s
            """, (request_id,))

            # Create new enrollment
            cursor.execute("""
                INSERT INTO Enrollment (StudentID, CourseID, EnrollmentDate)
                VALUES (%s, %s, NOW())
            """, (request['StudentID'], request['CourseID']))

            # Create notification for student
            cursor.execute("""
                INSERT INTO Notification (UserID, Message, Timestamp)
                SELECT %s, 
                    CONCAT('Your enrollment request for course ', c.CourseName, ' has been approved'),
                    NOW()
                FROM Course c
                WHERE c.CourseID = %s
            """, (request['StudentID'], request['CourseID']))

            cursor.execute("COMMIT")
            return jsonify({
                'success': True,
                'message': 'Enrollment request approved successfully'
            }), 200
            
        except mysql.connector.Error:
            cursor.execute("ROLLBACK")
            raise
            
    except mysql.connector.Error as err:
        print(f"Error processing enrollment: {err}")
        return jsonify({
            'success': False,
            'message': 'Failed to process enrollment request'
        }), 500

@app.route('/admin/enrollment/reject/<int:request_id>', methods=['POST'])
@login_required
def reject_enrollment(request_id):
    """Reject student enrollment request."""
    if session.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Only admins can reject enrollments'}), 403

    cursor = mydb.cursor(dictionary=True)
    try:
        cursor.execute("""
            UPDATE EnrollmentRequest 
            SET Status = 'rejected', ProcessedDate = NOW() 
            WHERE RequestID = %s AND Status = 'pending'
        """, (request_id,))
        
        if cursor.rowcount == 0:
            return jsonify({'success': False, 'message': 'Request not found or already processed'}), 404
        
        mydb.commit()
        return jsonify({'success': True, 'message': 'Enrollment request rejected successfully'}), 200

    except mysql.connector.Error as err:
        print(f"Error rejecting enrollment: {err}")
        return jsonify({'success': False, 'message': 'Failed to reject enrollment request'}), 500

# Add course deletion route
@app.route('/admin/courses/<int:course_id>/delete', methods=['POST'])
@login_required
def delete_course(course_id):
    if session.get('role') != 'admin':
        return jsonify({
            'success': False,
            'message': 'Only admins can delete courses'
        }), 403

    cursor = mydb.cursor(dictionary=True)
    try:
        # Check if course exists
        cursor.execute("SELECT 1 FROM Course WHERE CourseID = %s", (course_id,))
        if not cursor.fetchone():
            return jsonify({
                'success': False,
                'message': 'Course not found'
            }), 404

        # Delete course (this will cascade to related records if set up in DB)
        cursor.execute("DELETE FROM Course WHERE CourseID = %s", (course_id,))
        mydb.commit()

        return jsonify({
            'success': True,
            'message': 'Course deleted successfully'
        }), 200

    except mysql.connector.Error as err:
        print(f"Error deleting course: {err}")
        return jsonify({
            'success': False,
            'message': 'Failed to delete course'
        }), 500

@app.route('/admin/courses/<int:course_id>/edit', methods=['POST'])
@login_required
def edit_course(course_id):
    """Edit existing course details."""
    if session.get('role') != 'admin':
        return jsonify({
            'success': False,
            'message': 'Only admins can edit courses'
        }), 403

    data = request.get_json()
    required_fields = ['course_name', 'course_code', 'instructor_id', 'year', 'semester']
    
    if not all(field in data for field in required_fields):
        return jsonify({
            'success': False,
            'message': 'Missing required fields'
        }), 400

    # Validate semester is between 1 and 8
    try:
        semester = int(data['semester'])
        if not 1 <= semester <= 8:
            return jsonify({
                'success': False,
                'message': 'Semester must be between 1 and 8'
            }), 400
    except ValueError:
        return jsonify({
            'success': False,
            'message': 'Invalid semester value'
        }), 400

    cursor = mydb.cursor(dictionary=True)
    try:
        # Verify if selected instructor exists and is a professor
        cursor.execute("""
            SELECT UserID, Role 
            FROM User 
            WHERE UserID = %s AND Role = 'professor' AND Active = 1
        """, (data['instructor_id'],))
        
        if not cursor.fetchone():
            return jsonify({
                'success': False,
                'message': 'Selected instructor is not valid'
            }), 400

        # Update the course
        cursor.execute("""
            UPDATE Course 
            SET CourseName = %s, 
                CourseCode = %s, 
                InstructorID = %s, 
                Year = %s, 
                Semester = %s
            WHERE CourseID = %s
        """, (
            data['course_name'],
            data['course_code'],
            data['instructor_id'],
            data['year'],
            semester,
            course_id
        ))
        
        mydb.commit()
        
        return jsonify({
            'success': True,
            'message': 'Course updated successfully'
        }), 200

    except mysql.connector.Error as err:
        print(f"Error updating course: {err}")
        return jsonify({
            'success': False,
            'message': 'Failed to update course'
        }), 500

# ============ Professor Routes ============
@app.route('/professor-dashboard')
@login_required
def professor_dashboard():
    if session.get('role') != 'professor':
        return jsonify({'message': 'Only professors can access this route'}), 403

    cursor = mydb.cursor(dictionary=True)
    try:
        # Get professor stats
        cursor.execute("""
            SELECT 
                (SELECT COUNT(*) FROM Course 
                 WHERE InstructorID = %s) as active_courses,
                (SELECT COUNT(DISTINCT e.StudentID) 
                 FROM Enrollment e 
                 JOIN Course c ON e.CourseID = c.CourseID 
                 WHERE c.InstructorID = %s) as total_students,
                (SELECT COUNT(*) FROM Submission s 
                 JOIN Assignment a ON s.AssignmentID = a.AssignmentID 
                 JOIN Course c ON a.CourseID = c.CourseID 
                 WHERE c.InstructorID = %s AND s.Grade IS NULL) as pending_assignments
        """, (session['user_id'], session['user_id'], session['user_id']))
        
        stats = cursor.fetchone()
        
        # Get teaching courses with detailed information
        cursor.execute("""
            SELECT 
                c.*,
                (SELECT COUNT(DISTINCT e.StudentID) 
                 FROM Enrollment e 
                 WHERE e.CourseID = c.CourseID) as enrolled_students,
                (SELECT COUNT(a.AssignmentID) 
                 FROM Assignment a 
                 WHERE a.CourseID = c.CourseID) as assignment_count,
                (SELECT COUNT(*) 
                 FROM Submission s 
                 JOIN Assignment a ON s.AssignmentID = a.AssignmentID 
                 WHERE a.CourseID = c.CourseID AND s.Grade IS NULL) as pending_submissions
            FROM Course c
            WHERE c.InstructorID = %s
            ORDER BY c.Year DESC, c.Semester DESC
        """, (session['user_id'],))
        
        courses = cursor.fetchall()
        
        return jsonify({
            'stats': stats,
            'courses': courses,
            'professor_name': session.get('username')
        }), 200
        
    except mysql.connector.Error as err:
        print(f"Error fetching dashboard data: {err}")
        return jsonify({'message': 'Error fetching dashboard data'}), 500

@app.route('/submissions/<int:submission_id>/grade', methods=['POST'])
@login_required
def grade_submission(submission_id):
    """Grade and provide feedback on student submissions."""
    if session.get('role') != 'professor':
        return jsonify({'message': 'Only professors can access this route'}), 403

    if 'user_id' not in session or session.get('role') != 'professor':
        return jsonify({'message': 'Unauthorized'}), 401

    data = request.get_json()
    grade = data.get('grade')
    feedback = data.get('feedback')

    if not grade:
        return jsonify({'message': 'Grade is required'}), 400

    cursor = mydb.cursor(dictionary=True)
    try:
        # Verify professor teaches this course
        cursor.execute("""
            SELECT c.CourseID 
            FROM Course c
            JOIN Assignment a ON c.CourseID = a.CourseID
            JOIN Submission s ON a.AssignmentID = s.AssignmentID
            WHERE s.SubmissionID = %s AND c.InstructorID = %s
        """, (submission_id, session['user_id']))

        if not cursor.fetchone():
            return jsonify({'message': 'Not authorized to grade this submission'}), 403

        # Update the submission with grade and feedback
        cursor.execute("""
            UPDATE Submission 
            SET Grade = %s, Feedback = %s, GradedDate = NOW()
            WHERE SubmissionID = %s
        """, (grade, feedback, submission_id))
        
        mydb.commit()

        # Create notification for student
        cursor.execute("""
            INSERT INTO Notification (UserID, Message, Timestamp)
            SELECT s.StudentID, 
                   CONCAT('Your submission for assignment "', a.Title, '" has been graded'), 
                   NOW()
            FROM Submission s
            JOIN Assignment a ON s.AssignmentID = a.AssignmentID
            WHERE s.SubmissionID = %s
        """, (submission_id,))
        
        mydb.commit()
        return jsonify({'message': 'Submission graded successfully'}), 200
    except mysql.connector.Error as err:
        print(f"Error grading submission: {err}")
        return jsonify({'message': 'Failed to grade submission'}), 500

@app.route('/api/assignments/<int:assignment_id>/delete', methods=['POST'])
@login_required
def delete_assignment(assignment_id):
    """Delete an assignment and its associated files."""
    if session.get('role') != 'professor':
        return jsonify({
            'success': False,
            'message': 'Only professors can delete assignments'
        }), 403

    cursor = mydb.cursor(dictionary=True)
    try:
        # First verify the professor owns this assignment
        cursor.execute("""
            SELECT a.*, c.InstructorID 
            FROM Assignment a
            JOIN Course c ON a.CourseID = c.CourseID
            WHERE a.AssignmentID = %s
        """, (assignment_id,))
        
        assignment = cursor.fetchone()
        if not assignment:
            return jsonify({
                'success': False,
                'message': 'Assignment not found'
            }), 404
            
        if assignment['InstructorID'] != session['user_id']:
            return jsonify({
                'success': False,
                'message': 'You can only delete your own assignments'
            }), 403

        # Start transaction
        cursor.execute("START TRANSACTION")
        
        try:
            # Delete associated files if they exist
            if assignment['FilePath'] and os.path.exists(assignment['FilePath']):
                os.remove(assignment['FilePath'])
            
            # Delete submissions and their files
            cursor.execute("""
                SELECT SubmissionPath 
                FROM Submission 
                WHERE AssignmentID = %s
            """, (assignment_id,))
            
            submissions = cursor.fetchall()
            for submission in submissions:
                if submission['SubmissionPath'] and os.path.exists(submission['SubmissionPath']):
                    os.remove(submission['SubmissionPath'])

            # Delete database records
            cursor.execute("DELETE FROM Submission WHERE AssignmentID = %s", (assignment_id,))
            cursor.execute("DELETE FROM Assignment WHERE AssignmentID = %s", (assignment_id,))
            
            # Create notifications for enrolled students
            cursor.execute("""
                INSERT INTO Notification (UserID, Message, Timestamp)
                SELECT e.StudentID, 
                    CONCAT('Assignment "', %s, '" has been deleted from the course'),
                    NOW()
                FROM Enrollment e
                WHERE e.CourseID = %s
            """, (assignment['Title'], assignment['CourseID']))

            cursor.execute("COMMIT")
            return jsonify({
                'success': True,
                'message': 'Assignment deleted successfully'
            }), 200

        except Exception as e:
            cursor.execute("ROLLBACK")
            raise e

    except mysql.connector.Error as err:
        print(f"Error deleting assignment: {err}")
        return jsonify({
            'success': False,
            'message': 'Failed to delete assignment'
        }), 500
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({
            'success': False,
            'message': 'An error occurred while deleting the assignment'
        }), 500

# ============ Student Routes ============
@app.route('/student-dashboard')
@login_required
def student_dashboard():
    """Student dashboard data API endpoint."""
    if session.get('role') != 'student':
        return jsonify({'message': 'Only students can access this route'}), 403

    if 'user_id' not in session or session.get('role') != 'student':
        return jsonify({'message': 'Unauthorized'}), 401

    cursor = mydb.cursor(dictionary=True)
    try:
        # Fetch enrolled courses and available courses
        cursor.execute("""
            SELECT c.*, 
                   u.FirstName as instructor_name,
                   CASE WHEN e.StudentID IS NOT NULL THEN TRUE ELSE FALSE END as is_enrolled
            FROM Course c
            JOIN User u ON c.InstructorID = u.UserID
            LEFT JOIN Enrollment e ON c.CourseID = e.CourseID AND e.StudentID = %s
        """, (session['user_id'],))
        courses = cursor.fetchall()

        return jsonify({
            'enrolled_courses': [c for c in courses if c['is_enrolled']],
            'available_courses': [c for c in courses if not c['is_enrolled']],
            'student_name': session.get('username'),
        }), 200
    except mysql.connector.Error as err:
        return jsonify({'message': 'Error fetching dashboard data'}), 500

@app.route('/assignments/<int:assignment_id>/submit', methods=['POST'])
@login_required
def submit_assignment(assignment_id):
    """Submit assignment files for grading."""
    if session.get('role') != 'student':
        return jsonify({'message': 'Only students can access this route'}), 403

    if 'user_id' not in session:
        return jsonify({'message': 'Unauthorized'}), 401

    cursor = mydb.cursor(dictionary=True)
    try:
        # First verify if user is a student
        cursor.execute("SELECT Role FROM User WHERE UserID = %s", (session['user_id'],))
        user = cursor.fetchone()
        if user['Role'] != 'student':
            return jsonify({'message': 'Only students can submit assignments'}), 403

        # Rest of the submission logic
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
                if err.errno == 1644:  # Custom error from trigger
                    return jsonify({'message': str(err)}), 403
                print(f"Error recording submission: {err}")
                return jsonify({'message': 'Failed to record submission'}), 500

        return jsonify({'message': 'File type not allowed'}), 400

    except mysql.connector.Error as err:
        if err.errno == 1644:  # Custom error from trigger
            return jsonify({'message': str(err)}), 403
        print(f"Error submitting assignment: {err}")
        return jsonify({'message': 'Failed to submit assignment'}), 500

@app.route('/student/courses/request/<int:course_id>', methods=['POST'])
@login_required
def request_enrollment(course_id):
    """Request enrollment in a course."""
    if session.get('role') != 'student':
        return jsonify({'message': 'Only students can access this route'}), 403

    if 'user_id' not in session or session.get('role') != 'student':
        return jsonify({'message': 'Unauthorized'}), 401
    
    cursor = mydb.cursor(dictionary=True)
    try:
        # Check if already enrolled or requested
        cursor.execute("""
            SELECT 1 FROM EnrollmentRequest 
            WHERE StudentID = %s AND CourseID = %s AND Status = 'pending'
        """, (session['user_id'], course_id))
        if cursor.fetchone():
            return jsonify({'message': 'Enrollment request already pending'}), 400

        cursor.execute("""
            INSERT INTO EnrollmentRequest (StudentID, CourseID, RequestDate, Status)
            VALUES (%s, %s, NOW(), 'pending')
        """, (session['user_id'], course_id))
        mydb.commit()
        return jsonify({'message': 'Enrollment request submitted successfully'}), 201
    except mysql.connector.Error as err:
        return jsonify({'message': 'Error submitting enrollment request'}), 500

# Add @login_required to all remaining routes and add role checks
@app.route('/courses/<int:course_id>/materials', methods=['POST'])
@login_required
def upload_course_material(course_id):
    if session.get('role') != 'professor':
        return jsonify({'message': 'Only professors can access this route'}), 403

    if 'user_id' not in session or session.get('role') != 'professor':
        return jsonify({'message': 'Unauthorized'}), 401

    cursor = mydb.cursor(dictionary=True)
    try:
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
                # Set current user for the trigger
                cursor.execute("SET @current_user_id = %s", (session['user_id'],))
                
                # Record the material in database
                cursor.execute("""
                    INSERT INTO CourseMaterial (CourseID, FilePath, Description, UploadDate)
                    VALUES (%s, %s, %s, NOW())
                """, (course_id, file_path, description))
                mydb.commit()
                return jsonify({'message': 'Material uploaded successfully'}), 201
            except mysql.connector.Error as err:
                if err.errno == 1644:  # Custom error from trigger
                    return jsonify({'message': str(err)}), 403
                print(f"Error recording material: {err}")
                return jsonify({'message': 'Failed to record material'}), 500

        return jsonify({'message': 'File type not allowed'}), 400

    except mysql.connector.Error as err:
        print(f"Error uploading material: {err}")
        return jsonify({'message': 'Failed to upload material'}), 500

@app.route('/submissions/<int:submission_id>/download', methods=['GET'])
@login_required
def download_submission(submission_id):
    if session.get('role') != 'professor':
        return jsonify({'message': 'Only professors can access this route'}), 403

    if 'user_id' not in session or session.get('role') != 'professor':
        return jsonify({'message': 'Unauthorized'}), 401

    cursor = mydb.cursor(dictionary=True)
    try:
        # Get submission file path and verify authorization
        cursor.execute("""
            SELECT s.SubmissionPath, s.AssignmentID
            FROM Submission s
            JOIN Assignment a ON s.AssignmentID = a.AssignmentID
            JOIN Course c ON a.CourseID = c.CourseID
            WHERE s.SubmissionID = %s AND c.InstructorID = %s
        """, (submission_id, session['user_id']))
        
        submission = cursor.fetchone()
        if not submission:
            return jsonify({'message': 'Submission not found or unauthorized'}), 404

        return send_from_directory(
            directory=os.path.dirname(submission['SubmissionPath']),
            path=os.path.basename(submission['SubmissionPath'])
        )
    except mysql.connector.Error as err:
        print(f"Error downloading submission: {err}")
        return jsonify({'message': 'Failed to download submission'}), 500

@app.route('/course/<int:course_id>')
@login_required
def course_page(course_id):
    """Serve the course details page."""
    return render_template('course.html')

@app.route('/api/courses/<int:course_id>')
@login_required
def get_course_details(course_id):
    """Get detailed course information."""
    cursor = mydb.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT c.*, 
                   u.FirstName, u.LastName,
                   COUNT(DISTINCT e.StudentID) as enrolled_count
            FROM Course c
            JOIN User u ON c.InstructorID = u.UserID
            LEFT JOIN Enrollment e ON c.CourseID = e.CourseID
            WHERE c.CourseID = %s
            GROUP BY c.CourseID
        """, (course_id,))
        
        course = cursor.fetchone()
        if not course:
            return jsonify({'message': 'Course not found'}), 404

        return jsonify({
            'name': course['CourseName'],
            'code': course['CourseCode'],
            'instructor': f"{course['FirstName']} {course['LastName']}",
            'semester': course['Semester'],
            'year': course['Year'],
            'enrolled_count': course['enrolled_count']
        }), 200

    except mysql.connector.Error as err:
        print(f"Error fetching course details: {err}")
        return jsonify({'message': 'Failed to fetch course details'}), 500

@app.route('/api/user/role')
@login_required
def get_user_role():
    """Get the current user's role."""
    return jsonify({'role': session.get('role')}), 200

@app.route('/assignments')
@login_required
def assignments_page():
    """Serve the assignments listing page."""
    return render_template('assignments.html')

@app.route('/api/assignments')
@login_required
def get_assignments():
    """Get filtered and sorted assignments."""
    course_id = request.args.get('courseId')
    status = request.args.get('status')
    sort_by = request.args.get('sortBy', 'dueDate')

    cursor = mydb.cursor(dictionary=True)
    try:
        # Build the query based on filters
        query = """
            SELECT a.*, c.CourseName, 
                   COALESCE(s.Status, 'pending') as Status
            FROM Assignment a
            JOIN Course c ON a.CourseID = c.CourseID
            LEFT JOIN Submission s ON a.AssignmentID = s.AssignmentID 
                AND s.StudentID = %s
            WHERE 1=1
        """
        params = [session['user_id']]

        if course_id:
            query += " AND a.CourseID = %s"
            params.append(course_id)
        
        if status:
            query += " AND COALESCE(s.Status, 'pending') = %s"
            params.append(status)

        # Add sorting
        if sort_by == 'dueDate':
            query += " ORDER BY a.DueDate"
        elif sort_by == 'title':
            query += " ORDER BY a.Title"
        elif sort_by == 'status':
            query += " ORDER BY COALESCE(s.Status, 'pending')"

        cursor.execute(query, tuple(params))
        assignments = cursor.fetchall()

        return jsonify({'assignments': assignments}), 200
    except mysql.connector.Error as err:
        print(f"Error fetching assignments: {err}")
        return jsonify({'message': 'Failed to fetch assignments'}), 500

@app.route('/student/courses/exit/<int:course_id>', methods=['POST'])
@login_required
def exit_course(course_id):
    """Handle student's request to exit a course."""
    if session.get('role') != 'student':
        return jsonify({'success': False, 'message': 'Only students can exit courses'}), 403

    cursor = mydb.cursor(dictionary=True)
    try:
        # Start a transaction
        cursor.execute("START TRANSACTION")
        
        # Check if student is enrolled in the course
        cursor.execute("""
            SELECT 1 FROM Enrollment 
            WHERE StudentID = %s AND CourseID = %s AND Status = 'active'
        """, (session['user_id'], course_id))
        
        if not cursor.fetchone():
            cursor.execute("ROLLBACK")
            return jsonify({
                'success': False,
                'message': 'You are not enrolled in this course'
            }), 404

        # Delete the enrollment record instead of updating status
        cursor.execute("""
            DELETE FROM Enrollment 
            WHERE StudentID = %s AND CourseID = %s
        """, (session['user_id'], course_id))
        
        # Also delete any pending enrollment requests
        cursor.execute("""
            DELETE FROM EnrollmentRequest 
            WHERE StudentID = %s AND CourseID = %s
        """, (session['user_id'], course_id))
        
        cursor.execute("COMMIT")
        return jsonify({
            'success': True,
            'message': 'Successfully exited from the course'
        }), 200

    except mysql.connector.Error as err:
        cursor.execute("ROLLBACK")
        print(f"Error exiting course: {err}")
        return jsonify({
            'success': False,
            'message': 'Failed to exit course'
        }), 500

@app.route('/api/courses/<int:course_id>/details')
@login_required
def get_course_full_details(course_id):
    """Get comprehensive course details including students and assignments."""
    if session.get('role') != 'professor':
        return jsonify({'message': 'Unauthorized access'}), 403

    cursor = mydb.cursor(dictionary=True)
    try:
        # Get basic course info
        cursor.execute("""
            SELECT c.*, 
                   (SELECT COUNT(DISTINCT e.StudentID) 
                    FROM Enrollment e 
                    WHERE e.CourseID = c.CourseID) as enrolled_count,
                   (SELECT COUNT(*) 
                    FROM Assignment a 
                    WHERE a.CourseID = c.CourseID 
                    AND a.DueDate > NOW()) as active_assignments
            FROM Course c
            WHERE c.CourseID = %s AND c.InstructorID = %s
        """, (course_id, session['user_id']))
        
        course = cursor.fetchone()
        if not course:
            return jsonify({'message': 'Course not found or unauthorized'}), 404

        # Update the enrolled students query to fix progress tracking
        cursor.execute("""
            SELECT 
                u.UserID,
                CONCAT(u.FirstName, ' ', u.LastName) as name,
                u.Email,
                (
                    SELECT COUNT(DISTINCT s.SubmissionID)
                    FROM Submission s
                    JOIN Assignment a ON s.AssignmentID = a.AssignmentID
                    WHERE s.StudentID = u.UserID 
                    AND a.CourseID = %s
                ) as completed_assignments,
                (
                    SELECT COUNT(*)
                    FROM Assignment
                    WHERE CourseID = %s
                ) as total_assignments,
                (
                    SELECT AVG(CAST(s.Grade AS DECIMAL(5,2)))
                    FROM Submission s
                    JOIN Assignment a ON s.AssignmentID = a.AssignmentID
                    WHERE s.StudentID = u.UserID 
                    AND a.CourseID = %s
                    AND s.Grade IS NOT NULL
                ) as average_grade
            FROM User u
            JOIN Enrollment e ON u.UserID = e.StudentID
            WHERE e.CourseID = %s AND e.Status = 'active'
            GROUP BY u.UserID, u.FirstName, u.LastName, u.Email
        """, (course_id, course_id, course_id, course_id))
        
        students = cursor.fetchall()
        
        # Process the students data to handle NULL values
        for student in students:
            student['average_grade'] = float(student['average_grade']) if student['average_grade'] else 0
            student['completed_assignments'] = int(student['completed_assignments']) if student['completed_assignments'] else 0
            student['total_assignments'] = int(student['total_assignments'])
            student['progress'] = round((student['completed_assignments'] / student['total_assignments'] * 100) if student['total_assignments'] > 0 else 0, 1)

        # Get course assignments
        cursor.execute("""
            SELECT 
                a.AssignmentID as id,
                a.Title as title,
                a.DueDate as due_date,
                COUNT(DISTINCT s.StudentID) as submission_count,
                (SELECT COUNT(*) FROM Enrollment WHERE CourseID = %s) as total_students
            FROM Assignment a
            LEFT JOIN Submission s ON a.AssignmentID = s.AssignmentID
            WHERE a.CourseID = %s
            GROUP BY a.AssignmentID
        """, (course_id, course_id))
        assignments = cursor.fetchall()

        return jsonify({
            'name': course['CourseName'],
            'code': course['CourseCode'],
            'semester': course['Semester'],
            'year': course['Year'],
            'enrolled_count': course['enrolled_count'],
            'active_assignments': course['active_assignments'],
            'students': students,
            'assignments': assignments
        }), 200

    except mysql.connector.Error as err:
        print(f"Error fetching course details: {err}")
        return jsonify({'message': 'Failed to fetch course details'}), 500

if __name__ == '__main__':
    app.run(debug=True)