from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField, SelectField, BooleanField
from wtforms.validators import DataRequired, Length, InputRequired, ValidationError, Optional
from wtforms.fields.html5 import DateField
from datetime import datetime
from lightserv import db
# from lightserv.models import Experiment

def OptionalDateField(description='',validators=[]):
	""" A custom field that makes the DateField optional """
	validators.append(Optional())
	field = DateField(description,validators)
	return field

class StatusMonitorSelectForm(FlaskForm):
	""" The form for selecting which microscope  """
	microscope = SelectField('Choose Microscope:', choices=[('light sheet microscope','light sheet microscope'),
			 ('two photon microscope','two photon microscope'),('confocal microscope','confocal microscope')],
	         default='light sheet microscope',validators=[InputRequired()])
	
	submit = SubmitField('Show microscope status')	

class LightSheetStatusForm(FlaskForm):
	""" The form for requesting a new experiment/dataset """
	status = SelectField('Status:', 
		choices=[],validators=[InputRequired()])

class TwoPhotonStatusForm(FlaskForm):
	""" The form for requesting a new experiment/dataset """
	status = SelectField('Status:', 
		choices=[('good','good'),('bad','bad'),('time to replace','time to replace')],validators=[InputRequired()])

class ConfocalStatusForm(FlaskForm):
	""" The form for requesting a new experiment/dataset """
	status = SelectField('Status:', 
		choices=[('good','good'),('bad','bad'),('time to replace','time to replace')],validators=[InputRequired()])

class NewSwapLogEntryForm(FlaskForm):
	""" The form for requesting a new experiment/dataset """
	date = OptionalDateField('Date')
	# date = StringField('Date (e.g. 2019-05-01 for May 1, 2019)',validators=[DataRequired()])
	old_objective = SelectField('Old objective:', choices=[('1.3x','1.3x'),('2x','2x'),('1.3x (air objective)','1.3x (air objective)'),\
	         ('1.3x (dipping cap)','1.3x (dipping cap)'),('4x (dipping cap)','4x (dipping cap)')],\
	         default='1.3x',validators=[InputRequired()]) # for choices first element of tuple is the value of the option, the second is the displayed text
	new_objective = SelectField('New objective:', choices=[('1.3x','1.3x'),('2x','2x'),('1.3x (air objective)','1.3x (air objective)'),\
	         ('1.3x (dipping cap)','1.3x (dipping cap)'),('4x (dipping cap)','4x (dipping cap)'),],\
	         default='4x (dipping cap)',validators=[InputRequired()]) # for choices first element of tuple is the value of the option, the second is the displayed text
	swapper = StringField('Swapper',validators=[DataRequired(),Length(max=250)])
	calibration = TextAreaField('Calibration',validators=[DataRequired(),Length(max=1000)])
	notes = TextAreaField('Notes',validators=[DataRequired(),Length(max=1000)])

	submit = SubmitField('Submit new entry to swap log')	

	# def validate_date(self,date):
	# 	''' Makes sure that the date is in the proper format  '''
	# 	try:
	# 		datetime_object=datetime.strptime(date.data,"%Y-%m-%d")
	# 	except:
	# 		raise ValidationError('Date not in correct format. Try again')

class UpdateSwapLogEntryForm(FlaskForm):
	""" The form for requesting a new experiment/dataset """

	date = OptionalDateField('Date')
	old_objective = SelectField('Old objective:', choices=[('1.3x','1.3x'),('2x','2x'),('1.3x (air objective)','1.3x (air objective)'),\
	         ('1.3x (dipping cap)','1.3x (dipping cap)'),('4x (dipping cap)','4x (dipping cap)')],\
	         default='1.3x',validators=[InputRequired()]) # for choices first element of tuple is the value of the option, the second is the displayed text
	new_objective = SelectField('New objective:', choices=[('1.3x','1.3x'),('2x','2x'),('1.3x (air objective)','1.3x (air objective)'),\
	         ('1.3x (dipping cap)','1.3x (dipping cap)'),('4x (dipping cap)','4x (dipping cap)'),],\
	         default='4x (dipping cap)',validators=[InputRequired()]) # for choices first element of tuple is the value of the option, the second is the displayed text
	swapper = StringField('Swapper',validators=[DataRequired(),Length(max=250)])
	calibration = TextAreaField('Calibration',validators=[DataRequired(),Length(max=1000)])
	notes = TextAreaField('Notes',validators=[DataRequired(),Length(max=1000)])

	submit = SubmitField('Update Entry')
