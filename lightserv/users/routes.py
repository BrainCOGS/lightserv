from flask import render_template, url_for, flash, redirect, request, Blueprint, session
# from flask_login import login_user, current_user, logout_user, login_required
from lightserv import bcrypt
# from lightserv.models import User, Experiment
from lightserv.schemata import db
from lightserv.users.forms import (RegistrationForm, LoginForm, UpdateAccountForm,
                                   RequestResetForm, ResetPasswordForm)
from lightserv.users.utils import save_picture, send_reset_email

users = Blueprint('users',__name__)

@users.route("/register", methods=['GET', 'POST'])
def register():
	# if current_user.is_authenticated:
	if 'user' in session: 
		return redirect(url_for('main.home'))
	form = RegistrationForm()
	if form.validate_on_submit():
		hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
		user_entry = dict(username=form.username.data,password=hashed_password,email=form.email.data)
		db.User.insert1(user_entry)

		flash('Your account has been created! You are now able to log in.', 'success')
		return redirect(url_for('users.login'))
	return render_template('register.html', title='Register', form=form)

def new_route():
	return None

@users.route("/login", methods=['GET', 'POST'])
def login():
	# if current_user.is_authenticated:
	if 'user' in session:
		return redirect(url_for('main.home'))
	form = LoginForm()
	if form.validate_on_submit():
		user_contents = db.User() & f''' username="{form.username.data}" '''
		fetched_password = user_contents.fetch1('password')
		# print(form.email.data)
		if len(user_contents)>0 and bcrypt.check_password_hash(fetched_password, form.password.data):
			# find the username that corresponds to the email provided
			username = user_contents.fetch1('username')
			session['user'] = username
			next_page = request.args.get('next')
			flash(f"Welcome to Lightserv, {session['user']}",'success')
			# return redirect(next_page) if next_page else redirect(url_for('main.home'))
			return redirect(url_for('main.home'))
		else:
			flash('Login unsuccessful. Please check username and password', 'danger')
	return render_template('login.html', form=form)


@users.route("/logout")
def logout():
	# logout_user()
	session.pop('user')
	return redirect(url_for('main.home'))

# @users.route("/account", methods=['GET', 'POST'])
# # @login_required
# def account():
# 	form = UpdateAccountForm()
# 	if form.validate_on_submit():
# 		# if form.picture.data:
# 		# 	picture_file = save_picture(form.picture.data)
# 		# 	current_user.image_file = picture_file

		
# 		flash('Your account has been updated!', 'success')
# 		return redirect(url_for('users.account'))
# 	elif request.method == 'GET': # auto-fills the current credentials when a logged in user goes to their account
# 		form.username.data = current_user.username
# 		form.email.data = current_user.email
# 	image_file = url_for('static', filename='profile_pics/' + current_user.image_file)
# 	return render_template('account.html', title='Account',
# 						   image_file=image_file, form=form)	


@users.route("/reset_password", methods=['GET','POST'])
def reset_request():
	if 'user' in session:
		return redirect(url_for('main.home'))
	form = RequestResetForm()
	if form.validate_on_submit():
		# user = User.query.filter_by(email=form.email.data).first()
		user_contents = db.User() & f''' email="{form.email.data}" '''
		send_reset_email(user)
		flash('An email has been sent with instructions to reset your password.','info')
		return redirect(url_for('users.login'))
	return render_template('reset_request.html',title='Reset Password',form=form)

@users.route("/reset_password/<token>", methods=['GET','POST'])
def reset_token(token):
	if current_user.is_authenticated:
		return redirect(url_for('main.home'))
	user = User.verify_reset_token(token)
	if user is None:
		flash('That is an invalid or expired token','warning')
		return redirect(url_for('users.reset_request'))
	form = ResetPasswordForm()
	if form.validate_on_submit():
		hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
		user.password = hashed_password
		db.session.commit()
		flash('Your password has been reset! You are now able to log in.', 'success')
		return redirect(url_for('users.login'))
	return render_template('reset_token.html',title='Reset Password',form=form)	