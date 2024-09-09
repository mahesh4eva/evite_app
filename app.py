import os
from datetime import datetime
from flask import Flask, request, render_template, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from werkzeug.utils import secure_filename
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'  # Replace with a real secret key
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///evite.db'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')

db = SQLAlchemy(app)
mail = Mail(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

class Invitation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    event_name = db.Column(db.String(100), nullable=False)
    event_date = db.Column(db.DateTime, nullable=False)
    image_path = db.Column(db.String(200))
    description = db.Column(db.Text)
    location = db.Column(db.String(200))
    theme = db.Column(db.String(100))

class Guest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invitation_id = db.Column(db.Integer, db.ForeignKey('invitation.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    rsvp = db.Column(db.Boolean, default=False)
    rsvp_date = db.Column(db.DateTime)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and user.password == request.form['password']:  # In a real app, use proper password hashing
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    invitations = Invitation.query.filter_by(user_id=current_user.id).all()
    return render_template('dashboard.html', invitations=invitations)

@app.route('/create_invitation', methods=['GET', 'POST'])
@login_required
def create_invitation():
    if request.method == 'POST':
        event_name = request.form['event_name']
        event_date = datetime.strptime(request.form['event_date'], '%Y-%m-%d')
        description = request.form['description']
        location = request.form['location']
        theme = request.form['theme']
        image = request.files['image']
        
        if image:
            filename = secure_filename(image.filename)
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            image_path = os.path.join('uploads', filename)
        else:
            image_path = None
        
        invitation = Invitation(user_id=current_user.id, event_name=event_name, event_date=event_date, 
                                image_path=image_path, description=description, location=location, theme=theme)
        db.session.add(invitation)
        db.session.commit()
        
        flash('Invitation created successfully!')
        return redirect(url_for('preview_invitation', invitation_id=invitation.id))
    
    return render_template('create_invitation.html')

@app.route('/edit_invitation/<int:invitation_id>', methods=['GET', 'POST'])
@login_required
def edit_invitation(invitation_id):
    invitation = Invitation.query.get_or_404(invitation_id)
    if invitation.user_id != current_user.id:
        flash('You do not have permission to edit this invitation.')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        invitation.event_name = request.form['event_name']
        invitation.event_date = datetime.strptime(request.form['event_date'], '%Y-%m-%d')
        invitation.description = request.form['description']
        invitation.location = request.form['location']
        invitation.theme = request.form['theme']

        image = request.files['image']
        if image:
            filename = secure_filename(image.filename)
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            invitation.image_path = os.path.join('uploads', filename)

        db.session.commit()
        flash('Invitation updated successfully!')
        return redirect(url_for('preview_invitation', invitation_id=invitation.id))

    return render_template('edit_invitation.html', invitation=invitation)

@app.route('/delete_invitation/<int:invitation_id>', methods=['POST'])
@login_required
def delete_invitation(invitation_id):
    invitation = Invitation.query.get_or_404(invitation_id)
    if invitation.user_id != current_user.id:
        flash('You do not have permission to delete this invitation.')
        return redirect(url_for('dashboard'))

    db.session.delete(invitation)
    db.session.commit()
    flash('Invitation deleted successfully!')
    return redirect(url_for('dashboard'))

@app.route('/manage_guests/<int:invitation_id>', methods=['GET', 'POST'])
@login_required
def manage_guests(invitation_id):
    invitation = Invitation.query.get_or_404(invitation_id)
    if invitation.user_id != current_user.id:
        flash('You do not have permission to manage guests for this invitation.')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        guest = Guest(invitation_id=invitation_id, name=name, email=email)
        db.session.add(guest)
        db.session.commit()
        flash('Guest added successfully!')

    guests = Guest.query.filter_by(invitation_id=invitation_id).all()
    return render_template('manage_guests.html', invitation=invitation, guests=guests)

@app.route('/remove_guest/<int:guest_id>', methods=['POST'])
@login_required
def remove_guest(guest_id):
    guest = Guest.query.get_or_404(guest_id)
    invitation = Invitation.query.get(guest.invitation_id)
    if invitation.user_id != current_user.id:
        flash('You do not have permission to remove this guest.')
        return redirect(url_for('dashboard'))

    db.session.delete(guest)
    db.session.commit()
    flash('Guest removed successfully!')
    return redirect(url_for('manage_guests', invitation_id=invitation.id))

@app.route('/preview_invitation/<int:invitation_id>')
@login_required
def preview_invitation(invitation_id):
    invitation = Invitation.query.get_or_404(invitation_id)
    if invitation.user_id != current_user.id:
        flash('You do not have permission to view this invitation.')
        return redirect(url_for('dashboard'))
    return render_template('preview_invitation.html', invitation=invitation)

@app.route('/send_invitations/<int:invitation_id>')
@login_required
def send_invitations(invitation_id):
    invitation = Invitation.query.get_or_404(invitation_id)
    if invitation.user_id != current_user.id:
        flash('You do not have permission to send invitations for this event.')
        return redirect(url_for('dashboard'))

    guests = Guest.query.filter_by(invitation_id=invitation_id).all()
    
    for guest in guests:
        msg = Message(f"Invitation to {invitation.event_name}",
                      sender=app.config['MAIL_USERNAME'],
                      recipients=[guest.email])
        msg.html = render_template('email_template.html', invitation=invitation, guest=guest)
        mail.send(msg)
    
    flash('Invitations sent successfully!')
    return redirect(url_for('dashboard'))

@app.route('/rsvp/<int:guest_id>', methods=['GET', 'POST'])
def rsvp(guest_id):
    guest = Guest.query.get_or_404(guest_id)
    invitation = Invitation.query.get(guest.invitation_id)

    if request.method == 'POST':
        guest.rsvp = request.form['rsvp'] == 'yes'
        guest.rsvp_date = datetime.utcnow()
        db.session.commit()
        flash('Thank you for your RSVP!')
        return redirect(url_for('rsvp', guest_id=guest_id))
    
    return render_template('rsvp.html', guest=guest, invitation=invitation)

@app.route('/rsvp_status/<int:invitation_id>')
@login_required
def rsvp_status(invitation_id):
    invitation = Invitation.query.get_or_404(invitation_id)
    if invitation.user_id != current_user.id:
        flash('You do not have permission to view RSVP status for this event.')
        return redirect(url_for('dashboard'))

    guests = Guest.query.filter_by(invitation_id=invitation_id).all()
    return render_template('rsvp_status.html', invitation=invitation, guests=guests)

@app.route('/send_reminders/<int:invitation_id>')
@login_required
def send_reminders(invitation_id):
    invitation = Invitation.query.get_or_404(invitation_id)
    if invitation.user_id != current_user.id:
        flash('You do not have permission to send reminders for this event.')
        return redirect(url_for('dashboard'))

    guests = Guest.query.filter_by(invitation_id=invitation_id, rsvp=False).all()
    
    for guest in guests:
        msg = Message(f"Reminder: RSVP for {invitation.event_name}",
                      sender=app.config['MAIL_USERNAME'],
                      recipients=[guest.email])
        msg.html = render_template('reminder_email_template.html', invitation=invitation, guest=guest)
        mail.send(msg)
    
    flash('Reminders sent successfully!')
    return redirect(url_for('rsvp_status', invitation_id=invitation_id))

@app.route('/upload_image', methods=['POST'])
@login_required
def upload_image():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file:
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        return jsonify({'filename': os.path.join('uploads', filename)}), 200

if __name__ == '__main__':
    db.create_all()
    app.run(debug=True)
