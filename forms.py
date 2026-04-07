from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, IntegerField, TextAreaField, BooleanField, FileField
from wtforms.validators import DataRequired, Email, Length, Optional

class LoginForm(FlaskForm):
    username = StringField('Identity ID', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])

class AddUserForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=100)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=1)])
    role = SelectField('Role', choices=[('student', 'Student'), ('teacher', 'Teacher'), ('admin', 'Admin')], validators=[DataRequired()])
    full_name = StringField('Full Name', validators=[DataRequired(), Length(max=100)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    mobile = StringField('Mobile', validators=[DataRequired(), Length(max=20)])
    year = StringField('Year', validators=[Optional()]) # handled custom for student
    photo = FileField('Profile Photo') # Handled by request.files custom but valid form helps with CSRF

class FeedbackForm(FlaskForm):
    department = StringField('Department', validators=[DataRequired()])
    teacher = StringField('Teacher', validators=[DataRequired()])
    subject = StringField('Subject', validators=[DataRequired()])
    rating = IntegerField('Rating', validators=[DataRequired()])
    comment = TextAreaField('Comment', validators=[DataRequired()])
    is_anonymous = BooleanField('Submit Anonymously')

class MarkForm(FlaskForm):
    student = StringField('Student', validators=[DataRequired()])
    subject = StringField('Subject', validators=[DataRequired()])
    semester = StringField('Semester', validators=[DataRequired()])
    score = StringField('Score', validators=[DataRequired()])

class SettingsForm(FlaskForm):
    action = StringField('Action', validators=[DataRequired()]) # 'password' or 'theme'
    old_password = PasswordField('Current Password', validators=[Optional()])
    new_password = PasswordField('New Password', validators=[Optional()])
    theme = StringField('Theme', validators=[Optional()])
