DELIMITER //

-- Clean up existing triggers
DROP TRIGGER IF EXISTS before_course_material_insert//
DROP TRIGGER IF EXISTS before_submission_insert//
DROP TRIGGER IF EXISTS before_enrollment_insert//
DROP TRIGGER IF EXISTS before_course_insert//
DROP TRIGGER IF EXISTS before_assignment_insert//
DROP TRIGGER IF EXISTS before_course_material_update//
DROP TRIGGER IF EXISTS before_assignment_update//

-- Create course material trigger
CREATE TRIGGER before_course_material_insert
BEFORE INSERT ON CourseMaterial
FOR EACH ROW
BEGIN
    DECLARE user_role VARCHAR(20);
    
    -- Get the role using the session variable
    SELECT Role INTO user_role
    FROM User
    WHERE UserID = @current_user_id;
    
    IF user_role != 'professor' THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Only professors can upload course materials';
    END IF;
    
    -- Also verify if professor teaches this course
    IF NOT EXISTS (
        SELECT 1
        FROM Course
        WHERE CourseID = NEW.CourseID 
        AND InstructorID = @current_user_id
    ) THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'You can only upload materials to courses you teach';
    END IF;
END//

-- Create submission trigger
CREATE TRIGGER before_submission_insert
BEFORE INSERT ON Submission
FOR EACH ROW
BEGIN
    DECLARE user_role VARCHAR(20);
    
    -- Get the role of the user trying to submit
    SELECT Role INTO user_role
    FROM User
    WHERE UserID = NEW.StudentID;
    
    IF user_role != 'student' THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Only students can submit assignments';
    END IF;
END//

-- Create enrollment trigger
CREATE TRIGGER before_enrollment_insert
BEFORE INSERT ON Enrollment
FOR EACH ROW
BEGIN
    IF EXISTS (
        SELECT 1 FROM Enrollment 
        WHERE StudentID = NEW.StudentID 
        AND CourseID = NEW.CourseID 
        AND Status = 'active'
    ) THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Student is already enrolled in this course';
    END IF;
END//

-- Create course creation trigger
CREATE TRIGGER before_course_insert
BEFORE INSERT ON Course
FOR EACH ROW
BEGIN
    DECLARE creator_role VARCHAR(20);
    SELECT Role INTO creator_role FROM User WHERE UserID = @current_user_id;
    
    IF creator_role != 'admin' THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Only administrators can create courses';
    END IF;
END//

-- Create assignment trigger
CREATE TRIGGER before_assignment_insert
BEFORE INSERT ON Assignment
FOR EACH ROW
BEGIN
    IF NEW.DueDate <= NOW() THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Due date must be in the future';
    END IF;
END//

-- Create course material update trigger
CREATE TRIGGER before_course_material_update
BEFORE UPDATE ON CourseMaterial
FOR EACH ROW
BEGIN
    DECLARE user_role VARCHAR(20);
    
    SELECT Role INTO user_role
    FROM User
    WHERE UserID = @current_user_id;
    
    IF user_role != 'professor' THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Only professors can modify course materials';
    END IF;
    
    IF NOT EXISTS (
        SELECT 1
        FROM Course
        WHERE CourseID = NEW.CourseID 
        AND InstructorID = @current_user_id
    ) THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'You can only modify materials in courses you teach';
    END IF;
END//

-- Create assignment update trigger
CREATE TRIGGER before_assignment_update
BEFORE UPDATE ON Assignment
FOR EACH ROW
BEGIN
    IF NEW.DueDate <= NOW() AND OLD.DueDate != NEW.DueDate THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Cannot update due date to a past date';
    END IF;
END//

DELIMITER ;