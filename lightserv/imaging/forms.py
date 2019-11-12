from flask_wtf import FlaskForm
from wtforms import SubmitField, TextAreaField
from wtforms.fields.html5 import DateField, DateTimeLocalField
from wtforms.validators import DataRequired, Length, InputRequired, ValidationError, Optional

datetimeformat='%Y-%m-%dT%H:%M' # To get form.field.data to work. Does not work with the default (bug)

def OptionalDateField(description='',validators=[]):
	""" A custom field that makes the DateField optional """
	validators.append(Optional())
	field = DateField(description,validators)
	return field

def OptionalDateTimeLocalField(description='',validators=[],format=datetimeformat):
	""" A custom field that makes the DateTimeLocalField optional
	and applies a specific formatting to fix a bug in the default formatting """
	validators.append(Optional())
	field = DateTimeLocalField(description,validators,format=format)
	return field

class NewImagingForm(FlaskForm):
	""" The form for entering clearing information """
	title = 'iDISCO+ Immunostaining'
	exp_notes = TextAreaField('Experiment Notes: If anything unusual happened during the \
		experiment that might affect clearing, please note it here.',validators=[Length(max=500)])
	exp_notes_submit = SubmitField('Update')
	
	dehydr_date = OptionalDateField('Day 1: Dehydration')
	dehydr_date_submit = SubmitField('Push date to calendar (optional)')
	time_dehydr_pbs_wash1 = OptionalDateTimeLocalField('1xPBS 30 min R@RT')
	time_dehydr_pbs_wash1_submit = SubmitField('Update')
