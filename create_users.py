from app import app, db, User
from werkzeug.security import generate_password_hash

def create_initial_users():
    with app.app_context():
        # Create Student
        if not User.query.filter_by(username="student1").first():
            student = User(
                username="student1",
                password_hash=generate_password_hash("password123"),
                role="student",
                full_name="Alice Student",
                email="alice@example.com",
                mobile="1234567890",
                year="2024",
                photo_url="/static/uploads/profile_photos/default.png"
            )
            db.session.add(student)
            print("Student 'student1' created.")
        else:
            print("Student 'student1' already exists.")

        # Create Teacher
        if not User.query.filter_by(username="teacher1").first():
            teacher = User(
                username="teacher1",
                password_hash=generate_password_hash("password123"),
                role="teacher",
                full_name="Dr. Smith",
                email="smith@example.com",
                mobile="0987654321",
                photo_url="/static/uploads/profile_photos/default.png"
            )
            db.session.add(teacher)
            print("Teacher 'teacher1' created.")
        else:
            print("Teacher 'teacher1' already exists.")

        db.session.commit()

if __name__ == "__main__":
    create_initial_users()
