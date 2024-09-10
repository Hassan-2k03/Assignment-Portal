CREATE TABLE User (
    UserID INT PRIMARY KEY AUTO_INCREMENT,
    Username VARCHAR(20) NOT NULL UNIQUE,
    Password VARCHAR(128) NOT NULL,
    FirstName VARCHAR(30) NOT NULL,
    LastName VARCHAR(30) NOT NULL,
    Email VARCHAR(50) NOT NULL UNIQUE,
    Role ENUM('Student', 'Professor', 'Administrator') NOT NULL,
    Status ENUM('Active', 'Inactive') NOT NULL
);

CREATE TABLE Course (
    CourseID INT PRIMARY KEY AUTO_INCREMENT,
    CourseName VARCHAR(50) NOT NULL,
    CourseCode VARCHAR(10) NOT NULL UNIQUE,
    InstructorID INT,
    Semester VARCHAR(10) NOT NULL,
    Year YEAR NOT NULL,
    FOREIGN KEY (InstructorID) REFERENCES User(UserID)
);

CREATE TABLE Assignment (
    AssignmentID INT PRIMARY KEY AUTO_INCREMENT,
    CourseID INT,
    Title VARCHAR(100) NOT NULL,
    Description TEXT NOT NULL,
    DueDate DATETIME NOT NULL,
    FOREIGN KEY (CourseID) REFERENCES Course(CourseID)
);

CREATE TABLE Submission (
    SubmissionID INT PRIMARY KEY AUTO_INCREMENT,
    AssignmentID INT,
    StudentID INT,
    SubmissionDate DATETIME NOT NULL,
    SubmittedFiles VARCHAR(255), -- Assuming file paths are stored
    Grade VARCHAR(5), 
    Feedback TEXT,
    FOREIGN KEY (AssignmentID) REFERENCES Assignment(AssignmentID),
    FOREIGN KEY (StudentID) REFERENCES User(UserID)
);

CREATE TABLE Notification (
    NotificationID INT PRIMARY KEY AUTO_INCREMENT,
    UserID INT,
    Message TEXT,
    Timestamp DATETIME,
    Status ENUM('Read', 'Unread'),
    FOREIGN KEY (UserID) REFERENCES User(UserID)
);

CREATE TABLE GradeRubric (
    RubricID INT PRIMARY KEY AUTO_INCREMENT,
    AssignmentID INT,
    Criteria VARCHAR(255),
    Points INT,
    FOREIGN KEY (AssignmentID) REFERENCES Assignment(AssignmentID)
);

CREATE TABLE Announcement (
    AnnouncementID INT PRIMARY KEY AUTO_INCREMENT,
    CourseID INT,
    Message TEXT,
    Timestamp DATETIME,
    IsRead BOOLEAN,
    FOREIGN KEY (CourseID) REFERENCES Course(CourseID)
);

CREATE TABLE Enrollment (
    EnrollmentID INT PRIMARY KEY AUTO_INCREMENT,
    StudentID INT,
    CourseID INT,
    EnrollmentDate DATE,
    FOREIGN KEY (StudentID) REFERENCES User(UserID),
    FOREIGN KEY (CourseID) REFERENCES Course(CourseID)
);


