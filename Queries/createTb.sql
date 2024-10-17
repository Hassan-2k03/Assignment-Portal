-- User table
CREATE TABLE User (
    UserID INT AUTO_INCREMENT PRIMARY KEY,
    Username VARCHAR(255) UNIQUE NOT NULL,
    Password VARCHAR(255) NOT NULL,  -- Store hashed passwords here
    FirstName VARCHAR(255),
    LastName VARCHAR(255),
    Email VARCHAR(255),
    Role ENUM('student', 'professor', 'admin') NOT NULL
);

-- Course table
CREATE TABLE Course (
    CourseID INT AUTO_INCREMENT PRIMARY KEY,
    CourseName VARCHAR(255) NOT NULL,
    CourseCode VARCHAR(10) NOT NULL,  -- E.g., 'CS101'
    InstructorID INT,
    Year INT, 
    Semester INT,
    FOREIGN KEY (InstructorID) REFERENCES User(UserID)
);

-- Assignment table
CREATE TABLE Assignment (
    AssignmentID INT AUTO_INCREMENT PRIMARY KEY,
    CourseID INT NOT NULL,
    Title VARCHAR(255) NOT NULL,
    Description TEXT,
    DueDate DATETIME,
    FOREIGN KEY (CourseID) REFERENCES Course(CourseID)
);

-- Defines relationship table (between User and Assignment)
CREATE TABLE Defines (
    UserID INT,
    AssignmentID INT,
    PRIMARY KEY (UserID, AssignmentID),  -- Composite primary key
    FOREIGN KEY (UserID) REFERENCES User(UserID),
    FOREIGN KEY (AssignmentID) REFERENCES Assignment(AssignmentID)
);

-- Announcement table
CREATE TABLE Announcement (
    AnnouncementID INT AUTO_INCREMENT PRIMARY KEY,
    Message TEXT,
    Timestamp DATETIME
);


-- Has relationship table (between Course and Announcement)
CREATE TABLE Has (
    CourseID INT,
    AnnouncementID INT,
    PRIMARY KEY (CourseID, AnnouncementID),  -- Composite primary key
    FOREIGN KEY (CourseID) REFERENCES Course(CourseID),
    FOREIGN KEY (AnnouncementID) REFERENCES Announcement(AnnouncementID)  -- Assuming you have an Announcement table
);

-- Submission table
CREATE TABLE Submission (
    SubmissionID INT AUTO_INCREMENT PRIMARY KEY,
    AssignmentID INT NOT NULL,
    StudentID INT NOT NULL,
    SubmissionDate DATETIME,
    SubmittedFiles VARCHAR(255),  -- Can be a comma-separated list of file paths or a JSON array
    Feedback TEXT,
    Grade VARCHAR(5),
    FOREIGN KEY (AssignmentID) REFERENCES Assignment(AssignmentID),
    FOREIGN KEY (StudentID) REFERENCES User(UserID)
);

-- GradeRubric table (linked to Assignment)
CREATE TABLE GradeRubric (
    RubricID INT AUTO_INCREMENT PRIMARY KEY,
    AssignmentID INT NOT NULL,
    Criteria TEXT, 
    Points INT,
    FOREIGN KEY (AssignmentID) REFERENCES Assignment(AssignmentID)
);

-- Notification table
CREATE TABLE Notification (
    NotificationID INT AUTO_INCREMENT PRIMARY KEY,
    UserID INT NOT NULL,
    Message TEXT,
    Timestamp DATETIME,
    Status ENUM('read', 'unread') DEFAULT 'unread',
    FOREIGN KEY (UserID) REFERENCES User(UserID)
);

