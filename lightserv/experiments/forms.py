from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField, SelectField, BooleanField
from wtforms.validators import DataRequired, Length, InputRequired, ValidationError, Email
# from lightserv.models import Experiment

class ExpForm(FlaskForm):
	""" The form for requesting a new experiment/dataset """
	title = StringField('Title',validators=[DataRequired(),Length(max=100)])
	description = TextAreaField('Description',validators=[DataRequired(),Length(max=250)])
	labname = StringField('Lab name(s) (e.g. Tank/Brody)',validators=[DataRequired(),Length(max=100)])
	correspondence_email = StringField('Correspondence email (default is princeton email)',
		validators=[DataRequired(),Length(max=100),Email()])

	species = SelectField('Species:', choices=[('mouse','mouse'),('rat','rat'),('primate','primate'),('marsupial','marsupial')],validators=[InputRequired(),Length(max=50)]) # for choices first element of tuple is the value of the option, the second is the displayed text
	clearing_protocol = SelectField('Clearing Protocol:', choices= \
		[('iDISCO abbreviated clearing','iDISCO for non-oxidizable fluorophores (abbreviated clearing)'),
		 ('iDISCO abbreviated clearing (rat)','Rat: iDISCO for non-oxidizable fluorophores (abbreviated clearing)'),
	     ('iDISCO+_immuno','iDISCO+ (immunostaining)'),
	     ('uDISCO','uDISCO'),('iDISCO_EdU','Wang Lab iDISCO Protocol-EdU')],validators=[InputRequired()]) # for choices first element of tuple is the value of the option, the second is the displayed text
	fluorophores = TextAreaField('Fluorophores/dyes involved (E.g. AlexaFluor 647 or Thy1-YFP mouse)',validators=[Length(max=100)])
	antibody1 = TextAreaField('Primary antibody and concentrations desired (if doing immunostaining)',validators=[Length(max=100)])
	antibody2 = TextAreaField('Secondary antibody and concentrations desired (if doing immunostaining)',validators=[Length(max=100)])
	''' Imaging parameters '''
	image_resolution = SelectField('Image Resolution:', 
		choices=[('1.3x','1.3x (low-res: good for site detection, whole brain c-fos quantification, or registration)'),
	('4x','4x (high-res: good for tracing, cell detection)')],validators=[InputRequired()]) # for choices first element of tuple is the value of the option, the second is the displayed text
	cell_detection = BooleanField('Perform cell detection',default=False)
	registration = BooleanField('Register to atlas',default=False)
	probe_detection = BooleanField('Probe/fiber placement detection',default=False)
	injection_detection = BooleanField('Injection site detection',default=False)
	submit = SubmitField('Start experiment')	

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

class UpdateNotesForm(FlaskForm):
	""" The form for requesting a new experiment/dataset """
	notes = TextAreaField('Notes',validators=[Length(max=1000)])
	submit = SubmitField('Submit Changes')	
