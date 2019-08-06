from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError
from flask_login import current_user
from lightserv.models import User

class RegistrationForm(FlaskForm):
	""" A form for new user registration """
	username = StringField('Username',
						   validators=[DataRequired(), Length(min=2, max=20)])
	email = StringField('Email',
						validators=[DataRequired(), Email()])
	password = PasswordField('Password', validators=[DataRequired()])
	confirm_password = PasswordField('Confirm Password',
									 validators=[DataRequired(), EqualTo('password')])
	submit = SubmitField('Sign Up')

	def validate_username(self,username):
		''' Check to see if username already in db '''
		user = User.query.filter_by(username=username.data).first()

		if user: 
			raise ValidationError('Username is taken. Please choose a different one.')

	def validate_email(self,email):
		''' Check to see if email already in db '''
		user = User.query.filter_by(email=email.data).first()
		if user: 
			raise ValidationError('Email is taken. Please choose a different one.')

class LoginForm(FlaskForm):
	""" A form for logging in """
	email = StringField('Email',
						validators=[DataRequired(), Email()])
	password = PasswordField('Password', validators=[DataRequired()])
	remember = BooleanField('Remember Me')
	submit = SubmitField('Login')

class UpdateAccountForm(FlaskForm):
	""" A form for updating a user account """
	username = StringField('Username',
						   validators=[DataRequired(), Length(min=2, max=20)])
	email = StringField('Email',
						validators=[DataRequired(), Email()])
	picture = FileField('Update Profile Picture', validators=[FileAllowed(['jpg', 'png'])])
	submit = SubmitField('Update')

	def validate_username(self, username):
		if username.data != current_user.username:
			user = User.query.filter_by(username=username.data).first()
			if user:
				raise ValidationError('That username is taken. Please choose a different one.')

	def validate_email(self, email):
		if email.data != current_user.email:
			user = User.query.filter_by(email=email.data).first()
			if user:
				raise ValidationError('That email is taken. Please choose a different one.')

class RequestResetForm(FlaskForm):
	""" A form for requesting a password reset """
	email = StringField('Email',
						validators=[DataRequired(), Email()])
	submit = SubmitField('Request Password Reset')	

	def validate_email(self,email):
		''' Check to see if email does not exist in db '''
		user = User.query.filter_by(email=email.data).first()
		if user is None: 
			raise ValidationError('There is no account with that email. You must register first.')


class ResetPasswordForm(FlaskForm):
	""" A form for resetting a user password """
	password = PasswordField('Password', validators=[DataRequired()])
	confirm_password = PasswordField('Confirm Password',
									 validators=[DataRequired(), EqualTo('password')])
	submit = SubmitField('Reset Password')	