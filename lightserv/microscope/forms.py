from flask_wtf import FlaskForm
from wtforms import (StringField, SubmitField, TextAreaField,
        			 SelectField, BooleanField, RadioField)
from wtforms.validators import DataRequired, Length, InputRequired, ValidationError, Optional
from wtforms.fields.html5 import DateField
from datetime import datetime
from lightserv import db_lightsheet
# from lightserv.models import Experiment

def OptionalDateField(description='',validators=[]):
	""" A custom field that makes the DateField optional """
	validators.append(Optional())
	field = DateField(description,validators)
	return field

class StatusMonitorSelectForm(FlaskForm):
	""" The form for selecting which microscope  """
	center = SelectField('Choose Facility:', choices=[('Bezos Center','Bezos Center'),
			 ('McDonnell Center','McDonnell Center')],validators=[InputRequired()],id='select_center')
	microscope = SelectField('Choose Microscope:', choices=[('light sheet microscope','light sheet microscope'),
			 ('two photon microscope','two photon microscope'),('confocal microscope','confocal microscope')],
	         default='light sheet microscope',validators=[InputRequired()],id='select_microscope')
	
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


class MicroscopeActionSelectForm(FlaskForm):
	""" The form for selecting whether we are doing maintenance or data entry """
	
	action = SelectField('Choose what to do:', choices=[('microscope_maintenance','Microscope maintenance'),
		('enter_data','Enter new data')],default='value')
	submit = SubmitField('Submit')	

class DataEntrySelectForm(FlaskForm):
	""" The form for selecting which form we need for data entry  """
	
	data_entry_type = SelectField('Select which data entry form to access:', choices=[('new_microscope','New microscope'),
		('new_laser','New laser'),('new_channel','New channel (for microscope)'),
		('new_dichroic','New dichroic'),('new_filter','New filter'),('new_objective','New objective')],default='value')
	submit = SubmitField('Submit')	

class NewMicroscopeForm(FlaskForm):
	""" The form for requesting a new experiment/dataset """
	center = SelectField('Center',choices=[('Bezos Center','Bezos Center'),('McDonnell Center','McDonnell Center')])
	room_number = StringField('Room number',validators=[DataRequired(),Length(max=16)])
	optical_bay = StringField('Optical bay',validators=[DataRequired(),Length(max=8)])
	loc_on_table = StringField('Location on table',validators=[DataRequired(),Length(max=16)])
	microscope_description = TextAreaField('Microscope description',validators=[DataRequired(),Length(max=2047)])
	submit = SubmitField('Submit new entry to swap log')