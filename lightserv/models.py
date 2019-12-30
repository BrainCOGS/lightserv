# from lightserv import db_admin

# class UserActionLog(dj.Manual):
#     definition = """    # event logging table 
#     event_number  : int auto_increment
#     ---
#     timestamp = CURRENT_TIMESTAMP : timestamp 
#     browser_name    : varchar(255)
#     browser_version : varchar(255)
#     platform        : varchar(255)
#     event=""  : varchar(255)  # custom message
#     """

# class User(db_admin.Model):
#     id = db_admin.Column(db_admin.Integer, primary_key=True)
#     username = db_admin.Column(db_admin.String(20), unique=True, nullable=False)
#     email = db_admin.Column(db_admin.String(120), unique=True, nullable=False)
#     password = db_admin.Column(db_admin.String(60), nullable=False)

# class UserActionLog(db_admin.Model):
#     event_number = db_admin.Column(db_admin.Integer, primary_key=True)
#     # timestamp = db_admin.Column(db_admin.Timestamp, unique=True, nullable=False)
#     browser_name = db_admin.Column(db_admin.String(255), nullable=False)
#     # browser_version = db_admin.Column(db_admin.String(255), nullable=False, )
#     # platform = db_admin.Column(db_admin.String(255), nullable=False)
#     event = db_admin.Column(db_admin.String(255), nullable=False)

from datetime import datetime
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from lightserv import db_admin, login_manager
from flask_login import UserMixin
from flask import current_app

@login_manager.user_loader
def load_user(user_id):
	return User.query.get(int(user_id))

class User(db.Model, UserMixin): 
	""" A table in the database containing the user info """
	id = db.Column(db.Integer, primary_key=True) # the index of the user - also the user ID
	username = db.Column(db.String(20), unique=True, nullable=False)
	email = db.Column(db.String(120), unique=True, nullable=False)
	image_file = db.Column(db.String(20), nullable=False, default='default-user.png')
	password = db.Column(db.String(60), nullable=False)
	experiments = db.relationship('Experiment', backref='author', lazy=True)

	def __repr__(self):
		return "User('{username}', '{email}', '{image_file}')".\
			format(username=self.username,email=self.email,image_file=self.image_file)

	def get_reset_token(self,expires_sec=1800):
		''' A token for, e.g. resetting user password '''
		s = Serializer(current_app.config['SECRET_KEY'],expires_sec)
		return s.dumps({'user_id':self.id}).decode('utf-8')

	@staticmethod # means it does not need the "self" argument
	def verify_reset_token(token):
		''' Test whether token is still valid '''
		s = Serializer(current_app.config['SECRET_KEY'])
		try:
			user_id = s.loads(token)['user_id']
		except:
			return None
		return User.query.get(user_id)

class Experiment(db.Model):
	''' A table in the database containing the experiment info'''
	id = db.Column(db.Integer, primary_key=True) # the index of the entry - NOT the user ID

	dataset_hex = db.Column(db.String(10),unique=True,nullable=False)
	title = db.Column(db.String(100), nullable=False)
	date_run = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
	description = db.Column(db.Text, nullable=False)
	species = db.Column(db.String(25),nullable=False)
	clearing_protocol = db.Column(db.Text,nullable=True)
	fluorophores = db.Column(db.Text,nullable=True)
	primary_antibody = db.Column(db.Text,nullable=True)
	secondary_antibody = db.Column(db.Text,nullable=True)
	image_resolution = db.Column(db.Float,nullable=False)
	cell_detection = db.Column(db.Boolean,nullable=False,default=False)
	registration = db.Column(db.Boolean,nullable=False,default=False)
	injection_detection = db.Column(db.Boolean,nullable=False,default=False)
	probe_detection = db.Column(db.Boolean,nullable=False,default=False)
	user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

	def __repr__(self):
		return "Experiment('{title}', '{date_run}')".\
			format(title=self.title,date_run=self.date_run)

