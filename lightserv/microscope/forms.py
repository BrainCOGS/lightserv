from flask_wtf import FlaskForm
from wtforms import (StringField, SubmitField, TextAreaField,
        			 SelectField, BooleanField, RadioField,
        			 IntegerField)
from wtforms.validators import DataRequired, Length, InputRequired, ValidationError, Optional, url
from wtforms.fields.html5 import DateField, URLField
from wtforms.widgets import html5
from datetime import datetime
from lightserv import db_lightsheet, db_microscope
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
	""" The form for selecting whether we are doing microscope maintenance or data entry """
	action = SelectField('Choose what to do:', choices=[('microscope_maintenance','Microscope maintenance'),
		('enter_data','Enter new data')],default='value')
	submit = SubmitField('Submit')	

class DataEntrySelectForm(FlaskForm):
	""" The form for selecting which form we need for data entry  """
	data_entry_type = SelectField('Select which data entry form to access:', choices=[('new_microscope','New microscope'),
		('new_laser','New laser'),('new_channel','New channel (for microscope)'),
		('new_dichroic','New dichroic'),('new_filter','New filter'),('new_objective','New objective'),
		('new_scanner','New scanner'),('new_pmt','New PMT'),('new_daq','New DAQ'),
		('new_acq_software','New acquisition software')],default='new_microscope')
	submit = SubmitField('Submit')	

class NewMicroscopeForm(FlaskForm):
	""" The form for entering in a new microscope """
	microscope_name = StringField('Microscope name',validators=[InputRequired(),Length(max=32)])
	center = SelectField('Center',choices=[('Bezos Center','Bezos Center'),('McDonnell Center','McDonnell Center')],
		validators=[InputRequired()])
	room_number = StringField('Room number',validators=[InputRequired(),Length(max=16)])
	optical_bay = StringField('Optical bay',validators=[InputRequired(),Length(max=8)])
	loc_on_table = StringField('Location on table',validators=[InputRequired(),Length(max=16)])
	microscope_description = TextAreaField('Microscope description',validators=[InputRequired(),Length(max=2047)])
	submit = SubmitField('Submit new entry')

class NewLaserForm(FlaskForm):
	""" The form for entering in a new laser """
	laser_name = StringField('Laser name',validators=[InputRequired(),Length(max=32)])
	laser_model = StringField('Laser model',validators=[InputRequired(),Length(max=64)])
	laser_serial = StringField('Laser serial',validators=[InputRequired(),Length(max=64)])
	submit = SubmitField('Submit new entry')

class NewChannelForm(FlaskForm):
	""" The form for requesting a new experiment/dataset """
	microscopes = db_microscope.Microscope().fetch('microscope_name')
	microscope_name = SelectField('Microscope name',
		choices=[(microscope,microscope) for microscope in microscopes],validators=[InputRequired()])
	channel_name = StringField('Channel name',validators=[InputRequired(),Length(max=16)])
	submit = SubmitField('Submit new entry')

class NewChannelForm(FlaskForm):
	""" The form for requesting a new experiment/dataset """
	microscopes = db_microscope.Microscope().fetch('microscope_name')
	microscope_name = SelectField('Microscope name',
		choices=[(microscope,microscope) for microscope in microscopes],validators=[InputRequired()])
	channel_name = StringField('Channel name',validators=[InputRequired(),Length(max=16)])
	submit = SubmitField('Submit new entry')

class NewDichroicForm(FlaskForm):
	""" The form for requesting a new experiment/dataset """
	mirror_type = StringField('Mirror type',validators=[InputRequired(),Length(max=16)])
	mirror_brand = StringField('Mirror brand',validators=[InputRequired(),Length(max=64)])
	mirror_model = StringField('Mirror model',validators=[InputRequired(),Length(max=64)])
	mirror_spectrum = URLField('Mirror spectrum (link to google drive picture; include "https://"). ',
		validators=[Optional(),Length(max=255),url()])

	submit = SubmitField('Submit new entry')


class NewFilterForm(FlaskForm):
	""" The form for requesting a new experiment/dataset """
	filter_type = StringField('Filter type',validators=[InputRequired(),Length(max=32)])
	filter_brand = StringField('Filter brand',validators=[InputRequired(),Length(max=64)])
	filter_model = StringField('Filter model',validators=[InputRequired(),Length(max=64)])
	filter_spectrum = URLField('Filter spectrum (link to google drive picture; include "https://"). ',
		validators=[Optional(),Length(max=255),url()])

	submit = SubmitField('Submit new entry')

class NewObjectiveForm(FlaskForm):
	""" The form for requesting a new experiment/dataset """
	lens_type = StringField('Lens type',validators=[InputRequired(),Length(max=32)])
	lens_brand = StringField('Lens brand',validators=[InputRequired(),Length(max=64)])
	lens_model = StringField('Lens model',validators=[InputRequired(),Length(max=64)])

	submit = SubmitField('Submit new entry')

class NewScannerForm(FlaskForm):
	""" The form for requesting a new experiment/dataset """

	scanner_type = SelectField('Scanner type',
		choices=[('galvo','galvo'),('resonance','resonance')],
		validators=[InputRequired()])
	resonance_freq = IntegerField('Resonance frequency (unit?)',widget=html5.NumberInput(),
		validators=[InputRequired()])
	mirror_size = IntegerField('Mirror size (mm)',widget=html5.NumberInput(),
		validators=[InputRequired()])
	scanner_config = SelectField('Scanner config',
		choices=[('xy','xy'),('xyy','xyy'),
		('conjugated x and y','conjugated x and y'),('other','other')],
		validators=[InputRequired()])
	scanner_info = StringField('Scanner info',validators=[Optional(),Length(max=512)])

	submit = SubmitField('Submit new entry')