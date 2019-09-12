from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField, SelectField, BooleanField
# from wtforms.validators import DataRequired, Length, InputRequired, ValidationError
# from lightserv.models import Experiment

class OntologySubmitForm(FlaskForm):
	""" The form for submitting a graph to display a volume in neuroglancer """

	submit = SubmitField('Launch 3D viewer with current ontology configuration')	
