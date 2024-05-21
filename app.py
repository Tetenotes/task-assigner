from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
import os
from pytz import utc
from sqlalchemy.exc import IntegrityError
import json
from datetime import datetime, timedelta
import uuid
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from werkzeug.utils import secure_filename
from itsdangerous import URLSafeTimedSerializer
from sqlalchemy.types import DateTime
app = Flask(__name__)

# Ensure the directory exists
basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'database', 'app.db')
os.makedirs(os.path.dirname(db_path), exist_ok=True)
#  Define a custom filter to get the basename of a file path
def basename(filepath):
    return os.path.basename(filepath)

# Register the custom filter with Jinja2
app.jinja_env.filters['basename'] = basename

# Configuring the SQLite database URI
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'sxndbxnnxnbsnmmwm'
app.config['UPLOAD_FOLDER'] = os.path.join(basedir, 'static/uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)
s = URLSafeTimedSerializer(app.config['SECRET_KEY'])

# Define the database models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    phone = db.Column(db.String(15), nullable=True)

class Mechanic(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    phone = db.Column(db.String(15), nullable=False)
    mechanic_id = db.Column(db.String(50), unique=True, nullable=False)
    photo = db.Column(db.String(100), nullable=True)
    comments = db.Column(db.Text, nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    location = db.Column(db.String(100), nullable=False)

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mechanic_id = db.Column(db.String(50), nullable=False)
    task_description = db.Column(db.Text, nullable=False)
    start_time = db.Column(DateTime(timezone=True), nullable=False)
    end_time = db.Column(DateTime(timezone=True), nullable=False)
    status = db.Column(db.String(20), default='in progress')
    paused_time = db.Column(db.DateTime, nullable=True)  # Track paused time
    total_elapsed_time = db.Column(db.Interval, nullable=True)  # Track total elapsed time

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# Initialize the database
with app.app_context():
    db.create_all()

# Load admin credentials from JSON file
with open('admins.json', 'r') as f:
    admins_data = json.load(f)

# Function to send email notifications
def send_email(subject, recipient, body):
    sender_email = "josephmakaumunyao40@gmail.com"
    app_password = "vzge nzxu mvaz qdsv"

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'plain'))

    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(sender_email, app_password)
            server.sendmail(sender_email, recipient, msg.as_string())
        print("Email sent successfully")
    except Exception as e:
        print(f"Error sending email: {e}")

# Routes
@app.route('/')
def login_page():
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        first_name = request.form['firstName']
        last_name = request.form['lastName']
        email = request.form['email']
        password = request.form['password']
        phone = request.form['phone']
        
        new_user = User(first_name=first_name, last_name=last_name, email=email, password=password, phone=phone)
        try:
            db.session.add(new_user)
            db.session.commit()
            flash('Profile created successfully!', 'success')
            return redirect(url_for('login_page'))
        except IntegrityError:
            db.session.rollback()
            flash('Error: Email already exists.', 'danger')
            return redirect(url_for('register'))
    return render_template('register.html')

@app.route('/login', methods=['POST'])
def login():
    email = request.form['email']
    password = request.form['password']
    
    # Check if the email and password match any admin credentials
    for admin in admins_data:
        if admin['email'] == email and admin['password'] == password:
            # Store the user's email in the session
            session['email'] = email
            # Redirect the user to the admin page
            return redirect(url_for('admin'))
    
    # Check if the user exists in the database
    user = User.query.filter_by(email=email, password=password).first()
    if user:
        # Store the user's email in the session
        session['email'] = email
        # Redirect the user to the portal
        return redirect(url_for('portal'))
    
    # If login fails, redirect back to the login page with an error
    flash('Login failed. Please check your email and password and try again.', 'danger')
    return redirect(url_for('login_page'))

@app.route('/logout')
def logout():
    # Clear the session to log out the user
    session.clear()
    return redirect(url_for('login_page'))


# Calculate elapsed time for in-progress tasks
def calculate_elapsed_time(task):
    if task.status == 'in progress':
        elapsed_time = datetime.utcnow() - task.start_time
        task.total_elapsed_time = elapsed_time
        db.session.commit()

# Update route handlers to calculate elapsed time before rendering the portal
@app.route('/portal')
def portal():
    if 'email' not in session:
        flash('You need to be logged in to view this page.', 'danger')
        return redirect(url_for('login_page'))
        
    mechanics = Mechanic.query.all()
    tasks = Task.query.all()
    notifications = Notification.query.order_by(Notification.timestamp.desc()).limit(10).all()

    # Calculate elapsed time for in-progress tasks before rendering the portal
    for task in tasks:
        calculate_elapsed_time(task)

    # Calculate statistics, average duration, etc.
    total_tasks = len(tasks)
    total_completed_tasks = sum(1 for task in tasks if task.status == 'completed')
    total_in_progress_tasks = sum(1 for task in tasks if task.status == 'in progress')
    total_task_duration = sum((task.end_time - task.start_time).total_seconds() / 60 for task in tasks if task.end_time and task.start_time)
    average_task_duration = total_task_duration / total_tasks if total_tasks > 0 else 0

    return render_template('portal.html', mechanics=mechanics, tasks=tasks, notifications=notifications, total_tasks=total_tasks,
                           total_completed_tasks=total_completed_tasks, total_in_progress_tasks=total_in_progress_tasks,
                           average_task_duration=average_task_duration, os=os, datetime=datetime)
@app.route('/admin')
def admin():
    if 'email' not in session:
        flash('You need to be logged in to view this page.', 'danger')
        return redirect(url_for('login_page'))
        
    mechanics = Mechanic.query.all()
    tasks = Task.query.all()
    notifications = Notification.query.order_by(Notification.timestamp.desc()).limit(10).all()
      # Calculate statistics, average duration, etc.
    total_tasks = len(tasks)
    total_completed_tasks = sum(1 for task in tasks if task.status == 'completed')
    total_in_progress_tasks = sum(1 for task in tasks if task.status == 'in progress')
    total_task_duration = sum((task.end_time - task.start_time).total_seconds() / 60 for task in tasks if task.end_time and task.start_time)
    average_task_duration = total_task_duration / total_tasks if total_tasks > 0 else 0
    return render_template('admin.html', mechanics=mechanics, tasks=tasks, notifications=notifications, total_tasks=total_tasks,
                           total_completed_tasks=total_completed_tasks, total_in_progress_tasks=total_in_progress_tasks,
                           average_task_duration=average_task_duration, os=os, datetime=datetime)
@app.route('/add_mechanic', methods=['POST'])
def add_mechanic():
    if 'email' not in session:
        flash('You need to be logged in to perform this action.', 'danger')
        return redirect(url_for('login_page'))

    first_name = request.form['firstName']
    last_name = request.form['lastName']
    phone = request.form['phoneNumber']
    mechanic_id = request.form['mechanicId']
    photo = request.files.get('photo')  
    comments = request.form['comments']
    email = request.form['email']
    location = request.form['location']

    if photo:
        photo_filename = secure_filename(photo.filename)
        photo.save(os.path.join(app.config['UPLOAD_FOLDER'], photo_filename))
        photo_path = os.path.join(app.config['UPLOAD_FOLDER'], photo_filename)
    else:
        photo_path = None  # Handle case when photo is not uploaded

    new_mechanic = Mechanic(first_name=first_name, last_name=last_name, phone=phone, mechanic_id=mechanic_id, 
                            photo=photo_path, comments=comments, email=email, location=location)
    try:
        db.session.add(new_mechanic)
        db.session.commit()
        flash('Mechanic added successfully!', 'success')
    except IntegrityError:
        db.session.rollback()
        flash('Error: Mechanic ID or Email already exists.', 'danger')

    return redirect(url_for('portal'))
@app.route('/delete_mechanic', methods=['POST'])
def delete_mechanic():
    if 'email' not in session:
        flash('You need to be logged in to delete mechanics.', 'danger')
        return redirect(url_for('login_page'))

    mechanic_id = request.form['mechanicId']
    mechanic = Mechanic.query.filter_by(mechanic_id=mechanic_id).first()

    if mechanic:
        db.session.delete(mechanic)
        db.session.commit()
        flash('Mechanic deleted successfully!', 'success')
    else:
        flash(f'Error: Mechanic with ID {mechanic_id} not found.', 'danger')

    return redirect(url_for('admin'))


@app.route('/assign_task', methods=['POST'])
def assign_task():
    if 'email' not in session:
        flash('You need to be logged in to assign tasks.', 'danger')
        return redirect(url_for('login_page'))

    # Debug: Print form data
    print("Form Data:", request.form)

    # Safely get form data
    mechanic_id = request.form.get('mechanicId')
    task_description = request.form.get('taskDescription')
    start_time_str = request.form.get('from')
    end_time_str = request.form.get('to')

    # Convert datetime strings to datetime objects
    start_time = datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M').replace(tzinfo=utc)
    end_time = datetime.strptime(end_time_str, '%Y-%m-%dT%H:%M').replace(tzinfo=utc)

    # Check if task_description is None
    if not task_description:
        flash('Task description is required.', 'danger')
        return redirect(url_for('portal'))

    new_task = Task(mechanic_id=mechanic_id, task_description=task_description, start_time=start_time, end_time=end_time)
    db.session.add(new_task)
    db.session.commit()

    notification_message = f'New task "{task_description}" assigned to mechanic {mechanic_id}'
    notification = Notification(message=notification_message)
    db.session.add(notification)
    db.session.commit()

    user = User.query.filter_by(email=session['email']).first()
    if user:
        send_email('New Task Assigned', user.email, notification_message)

    flash('Task assigned successfully!', 'success')
    return redirect(url_for('portal'))
@app.route('/update_task', methods=['POST'])
def update_task():
    if 'email' not in session:
        flash('You need to be logged in to update tasks.', 'danger')
        return redirect(url_for('login_page'))

    task_id = request.form.get('taskId')
    task_description = request.form.get('taskDescription')
    start_time_str = request.form.get('startTime')
    end_time_str = request.form.get('endTime')
    status = request.form.get('status')

    task = Task.query.get(task_id)
    if task:
        task.task_description = task_description
        task.start_time = datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M').replace(tzinfo=utc)
        task.end_time = datetime.strptime(end_time_str, '%Y-%m-%dT%H:%M').replace(tzinfo=utc)
        task.status = status
        db.session.commit()

        flash('Task updated successfully!', 'success')

        # Add notification
        notification_message = f'Task "{task.task_description}" updated'
        notification = Notification(message=notification_message)
        db.session.add(notification)
        db.session.commit()

        # Send email notification
        user = User.query.filter_by(email=session['email']).first()
        if user:
            send_email('Task Updated', user.email, notification_message)
    else:
        flash('Error: Task not found.', 'danger')

    return redirect(url_for('portal'))

@app.route('/delete_task', methods=['POST'])
def delete_task():
    if 'email' not in session:
        flash('You need to be logged in to delete tasks.', 'danger')
        return redirect(url_for('login_page'))

    task_id = request.form['taskId']
    task = Task.query.get(task_id)
    
    if task:
        db.session.delete(task)
        db.session.commit()
        flash('Task deleted successfully!', 'success')
        
        # Add notification
        notification_message = f'Task "{task.task_description}" deleted'
        notification = Notification(message=notification_message)
        db.session.add(notification)
        db.session.commit()
        
        # Send email notification
        user = User.query.filter_by(email=session['email']).first()
        if user:
            send_email('Task Deleted', user.email, notification_message)
    else:
        flash('Error: Task not found.', 'danger')

    return redirect(url_for('portal'))

@app.route('/pause_task', methods=['POST'])
def pause_task():
    if 'email' not in session:
        flash('You need to be logged in to pause tasks.', 'danger')
        return redirect(url_for('login_page'))

    task_id = request.form.get('taskId')
    task = Task.query.get(task_id)
    if task:
        task.status = 'paused'
        task.paused_time = datetime.utcnow()
        db.session.commit()
        flash('Task paused successfully!', 'success')
        
        # Add notification
        notification_message = f'Task "{task.task_description}" paused'
        notification = Notification(message=notification_message)
        db.session.add(notification)
        db.session.commit()
        
        # Send email notification
        user = User.query.filter_by(email=session['email']).first()
        if user:
            send_email('Task Paused', user.email, notification_message)
    else:
        flash('Error: Task not found.', 'danger')

    return redirect(url_for('portal'))

@app.route('/resume_task', methods=['POST'])
def resume_task():
    if 'email' not in session:
        flash('You need to be logged in to resume tasks.', 'danger')
        return redirect(url_for('login_page'))

    task_id = request.form.get('taskId')
    task = Task.query.get(task_id)
    if task:
        task.status = 'in progress'
        if task.paused_time:  # Calculate the total elapsed time if the task was paused
            elapsed_time = datetime.utcnow() - task.paused_time
            task.total_elapsed_time += elapsed_time
            task.paused_time = None  # Reset paused time
        db.session.commit()
        flash('Task resumed successfully!', 'success')
        
        # Add notification
        notification_message = f'Task "{task.task_description}" resumed'
        notification = Notification(message=notification_message)
        db.session.add(notification)
        db.session.commit()
        
        # Send email notification
        user = User.query.filter_by(email=session['email']).first()
        if user:
            send_email('Task Resumed', user.email, notification_message)
    else:
        flash('Error: Task not found.', 'danger')

    return redirect(url_for('portal'))

@app.route('/reassign_task', methods=['POST'])
def reassign_task():
    if 'email' not in session:
        flash('You need to be logged in to reassign tasks.', 'danger')
        return redirect(url_for('login_page'))

    task_id = request.form.get('taskId')
    new_mechanic_id = request.form.get('mechanicId')
    task = Task.query.get(task_id)
    if task:
        task.mechanic_id = new_mechanic_id
        db.session.commit()
        flash(f'Task reassigned successfully to mechanic with ID: {new_mechanic_id}', 'success')
        
        # Add notification
        notification_message = f'Task "{task.task_description}" reassigned to mechanic with ID: {new_mechanic_id}'
        notification = Notification(message=notification_message)
        db.session.add(notification)
        db.session.commit()
        
        # Send email notification
        user = User.query.filter_by(email=session['email']).first()
        if user:
            send_email('Task Reassigned', user.email, notification_message)
    else:
        flash('Error: Task not found.', 'danger')

    return redirect(url_for('portal'))
# Forget password route
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        user = User.query.filter_by(email=email).first()
        if user:
            token = s.dumps(email, salt='password-reset-salt')
            reset_url = url_for('reset_password', token=token, _external=True)
            send_email('Password Reset Request', email, f'Click the link to reset your password: {reset_url}')
            flash('A password reset link has been sent to your email.', 'info')
        else:
            flash('No account found with that email.', 'danger')
    return render_template('forgot_password.html')
# Reset password route
@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        email = s.loads(token, salt='password-reset-salt', max_age=3600)
    except:
        flash('The password reset link is invalid or has expired.', 'danger')
        return redirect(url_for('login_page'))

    if request.method == 'POST':
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('reset_password', token=token))
        
        user = User.query.filter_by(email=email).first()
        if user:
            user.password = password
            db.session.commit()
            flash('Your password has been reset successfully.', 'success')
            return redirect(url_for('login_page'))
        else:
            flash('An error occurred. Please try again.', 'danger')
            return redirect(url_for('reset_password', token=token))
    return render_template('reset_password.html', token=token)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)