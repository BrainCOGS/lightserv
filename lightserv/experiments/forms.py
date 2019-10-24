from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField, SelectField, BooleanField
from wtforms.fields.html5 import DateField
from wtforms.validators import DataRequired, Length, InputRequired, ValidationError, Email, Optional
import os
import glob
from lightserv import db
# from lightserv.models import Experiment

def OptionalDateField(description='',validators=[]):
	""" A custom field that makes the DateField optional """
	validators.append(Optional())
	field = DateField(description,validators)
	return field

class ExpForm(FlaskForm):
	""" The form for requesting a new experiment/dataset """

	# Basic info
	title = StringField('Title',validators=[DataRequired(),Length(max=100)])
	description = TextAreaField('Description',validators=[DataRequired(),Length(max=250)])
	labname = StringField('Lab name(s) (e.g. Tank/Brody)',validators=[DataRequired(),Length(max=100)])
	correspondence_email = StringField('Correspondence email (default is princeton email)',
		validators=[DataRequired(),Length(max=100),Email()])

	species = SelectField('Species:', choices=[('mouse','mouse'),('rat','rat'),('primate','primate'),('marsupial','marsupial')],validators=[InputRequired(),Length(max=50)]) # for choices first element of tuple is the value of the option, the second is the displayed text
	# Clearing info
	perfusion_date = OptionalDateField('Perfusion Date (leave blank if unsure):')
	expected_handoff_date = OptionalDateField('Expected date of hand-off (leave blank if unsure):')
	clearing_protocol = SelectField('Clearing Protocol:', choices= \
		[('iDISCO abbreviated clearing','iDISCO for non-oxidizable fluorophores (abbreviated clearing)'),
		 ('iDISCO abbreviated clearing (rat)','Rat: iDISCO for non-oxidizable fluorophores (abbreviated clearing)'),
	     ('iDISCO+_immuno','iDISCO+ (immunostaining)'),
	     ('uDISCO','uDISCO'),('iDISCO_EdU','Wang Lab iDISCO Protocol-EdU')],validators=[InputRequired()]) # for choices first element of tuple is the value of the option, the second is the displayed text
	antibody1 = TextAreaField('Primary antibody and concentrations desired (if doing immunostaining)',validators=[Length(max=100)])
	antibody2 = TextAreaField('Secondary antibody and concentrations desired (if doing immunostaining)',validators=[Length(max=100)])
	
	# Imaging info
	channel488 = SelectField('488 nm channel purpose',choices=[
							('','None'),
							('registration','registration'),
							('injection_detection','injection_detection'),
							('probe_detection','probe_detection'),
							('cell_detection','cell_detection')]
							)
	channel555 = SelectField('555 nm channel purpose',choices=[
							('','None'),
							('registration','registration'),
							('injection_detection','injection_detection'),
							('probe_detection','probe_detection'),
							('cell_detection','cell_detection')]
							)
	channel647 = SelectField('647 nm channel purpose',choices=[
							('','None'),
							('registration','registration'),
							('injection_detection','injection_detection'),
							('probe_detection','probe_detection'),
							('cell_detection','cell_detection')]
							)
	channel790 = SelectField('790 nm channel purpose',choices=[
							('','None'),
							('registration','registration'),
							('injection_detection','injection_detection'),
							('probe_detection','probe_detection'),
							('cell_detection','cell_detection')]
							)
	image_resolution = SelectField('Image Resolution:', 
		choices=[('1.3x','1.3x (low-res: good for site detection, whole brain c-fos quantification, or registration)'),
	('4x','4x (high-res: good for tracing, cell detection)')],validators=[InputRequired()]) # for choices first element of tuple is the value of the option, the second is the displayed text
	submit = SubmitField('Submit Request')	

	def validate_antibody1(self,antibody1):
		''' Makes sure that primary antibody is not blank if immunostaining clearing protocol
		is chosen  '''
		if self.clearing_protocol.data == 'iDISCO+_immuno' and antibody1.data == '':
			raise ValidationError('Antibody must be specified because you selected \
				an immunostaining clearing protocol')

	def validate_clearing_protocol(self,clearing_protocol):
		''' Makes sure that the clearing protocol selected is appropriate for the species selected. '''
		if clearing_protocol.data == 'iDISCO abbreviated clearing' and self.species.data == 'rat':
			raise ValidationError('This clearing protocol is not allowed for rats. \
				Did you mean to choose: Rat: iDISCO for non-oxidizable fluorophores (abbreviated clearing)?')
		elif clearing_protocol.data == 'iDISCO abbreviated clearing (rat)' and self.species.data != 'rat':
			raise ValidationError('This clearing protocol is only allowed for rats. \
				Did you mean to choose: iDISCO for non-oxidizable fluorophores (abbreviated clearing)?')

def Directory_validator(form,field):
	''' Makes sure that the raw data directories exist on jukebox  '''
	if not os.path.isdir(field.data):
		raise ValidationError('This is not a valid directory. Please try again')
	elif field.data[0:8] != '/jukebox':
		raise ValidationError('Path must start with "/jukebox" ')
	elif len(glob.glob(field.data + '/*RawDataStack*ome.tif')) == 0:
		raise ValidationError('No raw data files found in that directory. Try again')	
		
class StartProcessingForm(FlaskForm):
	""" The form for requesting to start the data processing """
	rawdata_directory_channel488 = TextAreaField(\
		'Channel 488 raw data directory (on /jukebox)',validators=[Optional(),Length(max=500),Directory_validator])
	rawdata_directory_channel555 = TextAreaField(\
		'Channel 555 raw data directory (on /jukebox)',validators=[Optional(),Length(max=500),Directory_validator])
	rawdata_directory_channel647 = TextAreaField(\
		'Channel 647 raw data directory (on /jukebox)',validators=[Optional(),Length(max=500),Directory_validator])
	rawdata_directory_channel790 = TextAreaField(\
		'Channel 790 raw data directory (on /jukebox)',validators=[Optional(),Length(max=500),Directory_validator])

	submit = SubmitField('Start the processing')	


class UpdateNotesForm(FlaskForm):
	""" The form for requesting a new experiment/dataset """
	notes = TextAreaField('Notes',validators=[Length(max=1000)])
	submit = SubmitField('Submit Changes')	
