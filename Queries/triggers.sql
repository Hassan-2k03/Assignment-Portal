DELIMITER //

-- Trigger to ensure only professors can upload course materials
CREATE TRIGGER before_course_material_insert
BEFORE INSERT ON CourseMaterial
FOR EACH ROW
BEGIN
    DECLARE user_role VARCHAR(20);
    
    -- Get the role of the user trying to upload (using session user_id stored in routes.py)
    SELECT Role INTO user_role
    FROM User u
    INNER JOIN Course c ON c.InstructorID = u.UserID
    WHERE c.CourseID = NEW.CourseID;
    
    IF user_role != 'professor' THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Only professors can upload course materials';
    END IF;
END//

-- Trigger to ensure only students can submit assignments
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

DELIMITER ;
