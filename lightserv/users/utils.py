import os
import secrets
from PIL import Image
from flask import url_for, current_app
from flask_mail import Message
from lightserv import  mail

def save_picture(form_picture):
	random_hex = secrets.token_hex(8)
	_, f_ext = os.path.splitext(form_picture.filename)
	picture_fn = random_hex + f_ext
	picture_path = os.path.join(current_app.root_path, 'static/profile_pics', picture_fn)

	output_size = (125, 125)
	i = Image.open(form_picture)
	i.thumbnail(output_size)
	i.save(picture_path)

	return picture_fn


def send_reset_email(user):
	expires_sec = 1800
	expires_min = int(float(expires_sec/60.))
	token = user.get_reset_token(expires_sec=expires_sec)
	msg = Message('Password Reset Request',
		sender='noreply@demo.com',recipients=[user.email])
	msg.body = '''To reset your password, visit the following link:
{0}

The link will expire in {1} minutes.

If you did not make this request then simply ignore this email and no changes will be made. 
'''.format(url_for('reset_token',token=token, _external=True),expires_min) # _external gives the entire domain name rather than the relative path to the url_for response
	mail.send(msg)
