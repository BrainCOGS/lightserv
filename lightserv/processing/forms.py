from flask_wtf import FlaskForm
from wtforms import (StringField, SubmitField, TextAreaField,
					 SelectField, BooleanField, IntegerField,
					 DecimalField, FieldList,FormField,HiddenField)
from wtforms.fields.html5 import DateField
from wtforms.validators import DataRequired, Length, InputRequired, ValidationError, Email, Optional
from wtforms.widgets import html5, HiddenInput

	
class StartProcessingForm(FlaskForm):
	""" The form for requesting to start the data processing """
	max_number_of_channels=4
	notes_from_processing = TextAreaField("Note down anything additional about the processing"
									   " that you would like recorded.")
	atlas_name = SelectField('Choose atlas for registration (defaults to choice selected in request form):',
		choices=[('allen_2017','Allen atlas (2017)'),('allen_2011','Allen atlas (pre-2017)'),
				 ('princeton_mouse_atlas','Princeton Mouse Atlas')],validators=[InputRequired()])
	finalorientation = SelectField('Select the desired orientation of all volumetric data',
		choices=[('sagittal','Sagittal'),('coronal','Coronal'),('horizontal','Horizontal')],
		validators=[InputRequired()])
	submit = SubmitField('Start the processing pipeline for this sample')	