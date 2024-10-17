import unittest
from app import app, mydb  # Import your Flask app instance and mydb

class TestRoutes(unittest.TestCase):
    mydb = mydb  # Make mydb a class attribute

    def setUp(self):
        """Set up the test client and any necessary test data."""
        self.app = app.test_client()
        self.app_context = app.app_context()
        self.app_context.push()
        # Create a test user (you might need to adjust this based on your registration logic)
        self.test_user = {
            "username": "testuser",
            "password": "testpassword",
            "first_name": "Test",
            "last_name": "User",
            "email": "test@example.com",
            "role": "student"
        }
        self.app.post('/register', json=self.test_user)

    def tearDown(self):
        """Clean up any test data."""
        cursor = self.mydb.cursor()  # Access mydb as self.mydb
        try:
            cursor.execute("DELETE FROM User WHERE Username = %s", (self.test_user['username'],))
            self.mydb.commit()
        except Exception as e:
            print(f"Error during tearDown: {e}")
        self.app_context.pop()

    def test_registration(self):
        """Test user registration."""
        new_user = {
            "username": "newuser",
            "password": "newpassword",
            "first_name": "New",
            "last_name": "User",
            "email": "newuser@example.com",
            "role": "professor"
        }
        response = self.app.post('/register', json=new_user)
        self.assertEqual(response.status_code, 201)
        self.assertIn(b'User registered successfully', response.data)

    def test_login_success(self):
        """Test successful login."""
        response = self.app.post('/login', json={
            "username": self.test_user['username'],
            "password": self.test_user['password']
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Login successful', response.data)

    def test_login_failure(self):
        """Test login with incorrect password."""
        response = self.app.post('/login', json={
            "username": self.test_user['username'],
            "password": "incorrectpassword"
        })
        self.assertEqual(response.status_code, 401)
        self.assertIn(b'Invalid credentials', response.data)

    def test_logout(self):
        """Test user logout."""
        # First, log in the user
        self.app.post('/login', json={
            "username": self.test_user['username'],
            "password": self.test_user['password']
        })
        response = self.app.get('/logout')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Logged out', response.data)

if __name__ == '__main__':
    unittest.main()