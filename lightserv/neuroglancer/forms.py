from flask import session, current_app
from flask_wtf import FlaskForm
from wtforms import (StringField, SubmitField, TextAreaField,
					 SelectField, BooleanField, IntegerField,
					 DecimalField, FieldList,FormField,HiddenField)
# from wtforms.fields.html5 import DateField
from wtforms.validators import (DataRequired, Length, InputRequired,
	ValidationError, Optional)

""" Raw data """

class ChannelForm(FlaskForm):
	""" A sub-form for each channel in an ImageResolutionForm """
	channel_name = HiddenField('Channel Name')
	viz_left_lightsheet = BooleanField("Visualize?")
	viz_right_lightsheet = BooleanField("Visualize?")

class ImageResolutionForm(FlaskForm):
	""" A sub-form for each image resolution in RawDataSetupForm """
	image_resolution = HiddenField('image resolution')
	channel_forms = FieldList(FormField(ChannelForm),min_entries=0,max_entries=4)

class RawDataSetupForm(FlaskForm):
	""" A form for setting up how user wants to visualize
	their raw data for a given imaging request in Neuroglancer
	"""
	image_resolution_forms = FieldList(FormField(ImageResolutionForm),min_entries=0,max_entries=4)
	submit = SubmitField('Submit') # renders a new resolution table
	
	def validate_image_resolution_forms(self,image_resolution_forms):
		""" Check to make sure at least one checkbox was checked """
		any_checked = False
		for image_resolution_dict in self.image_resolution_forms.data:
			for channel_dict in image_resolution_dict['channel_forms']:
				if channel_dict['viz_left_lightsheet'] or channel_dict['viz_right_lightsheet']:
					any_checked=True
		if not any_checked:
			raise ValidationError("No light sheets were chosen to display."
								  " You must choose at least one in order to proceed.")

""" Stitched data """

class StitchedDataSetupForm(FlaskForm):
	""" A form for setting up how user wants to visualize
	their stitched (full resolution) data for a given processing request in Neuroglancer.
	"""
	image_resolution_forms = FieldList(FormField(ImageResolutionForm),min_entries=0,max_entries=4)
	submit = SubmitField('Submit') # renders a new resolution table
	
	def validate_image_resolution_forms(self,image_resolution_forms):
		""" Check to make sure at least one checkbox was checked """
		any_checked = False
		for image_resolution_dict in self.image_resolution_forms.data:
			for channel_dict in image_resolution_dict['channel_forms']:
				if channel_dict['viz_left_lightsheet'] or channel_dict['viz_right_lightsheet']:
					any_checked=True
		if not any_checked:
			raise ValidationError("No light sheets were chosen to display."
								  " You must choose at least one in order to proceed.")

""" Blended data """

class BlendedChannelForm(FlaskForm):
	""" A sub-form for each channel in an ImageResolutionForm """
	channel_name = HiddenField('Channel Name')
	viz = BooleanField("Visualize?",default=0)

class BlendedImageResolutionForm(FlaskForm):
	""" A sub-form for each image resolution in RawDataSetupForm """
	image_resolution = HiddenField('image resolution')
	channel_forms = FieldList(FormField(BlendedChannelForm),min_entries=0,max_entries=4)

class BlendedDataSetupForm(FlaskForm):
	""" A form for setting up how user wants to visualize
	their blended (full resolution) data for a given processing request in Neuroglancer.
	"""
	image_resolution_forms = FieldList(
		FormField(BlendedImageResolutionForm),min_entries=0,max_entries=4)
	submit = SubmitField('Submit') # renders a new resolution table
	
	def validate_image_resolution_forms(self,image_resolution_forms):
		""" Check to make sure at least one checkbox was checked """
		any_checked = False
		for image_resolution_dict in self.image_resolution_forms.data:
			for channel_dict in image_resolution_dict['channel_forms']:
				if channel_dict['viz']:
					any_checked=True
		if not any_checked:
			raise ValidationError("No channels were chosen to display."
								  " You must choose at least one in order to proceed.")

""" Downsized data """

class DownsizedChannelForm(FlaskForm):
	""" A sub-form for each channel in an ImageResolutionForm """
	channel_name = HiddenField('Channel Name')
	viz = BooleanField("Visualize?",default=0)

class DownsizedImageResolutionForm(FlaskForm):
	""" A sub-form for each image resolution in RawDataSetupForm """
	image_resolution = HiddenField('image resolution')
	channel_forms = FieldList(FormField(DownsizedChannelForm),min_entries=0,max_entries=4)

class DownsizedDataSetupForm(FlaskForm):
	""" A form for setting up how user wants to visualize
	their Downsized (full resolution) data for a given imaging request in Neuroglancer.
	"""
	image_resolution_forms = FieldList(
		FormField(DownsizedImageResolutionForm),min_entries=0,max_entries=4)
	submit = SubmitField('Submit') # renders a new resolution table
	
	def validate_image_resolution_forms(self,image_resolution_forms):
		""" Check to make sure at least one checkbox was checked """
		any_checked = False
		for image_resolution_dict in self.image_resolution_forms.data:
			for channel_dict in image_resolution_dict['channel_forms']:
				if channel_dict['viz']:
					any_checked=True
		if not any_checked:
			raise ValidationError("No channels were chosen to display."
								  " You must choose at least one in order to proceed.")

""" Registered data """

class RegisteredChannelForm(FlaskForm):
	""" A sub-form for each channel in an ImageResolutionForm """
	channel_name = HiddenField('Channel Name')
	viz = BooleanField("Visualize?",default=0)
	viz_atlas = BooleanField("Overlay Atlas?",default=0)

class RegisteredImageResolutionForm(FlaskForm):
	""" A sub-form for each image resolution in RawDataSetupForm """
	image_resolution = HiddenField('image resolution')
	channel_forms = FieldList(FormField(RegisteredChannelForm),min_entries=0,max_entries=4)

class RegisteredDataSetupForm(FlaskForm):
	""" A form for setting up how user wants to visualize
	their registered data for a given processing request in Neuroglancer.
	"""
	image_resolution_forms = FieldList(
		FormField(RegisteredImageResolutionForm),min_entries=0,max_entries=4)
	submit = SubmitField('Submit') # renders a new resolution table
	
	def validate_image_resolution_forms(self,image_resolution_forms):
		""" Check to make sure at least one checkbox was checked """
		any_checked = False
		for image_resolution_dict in self.image_resolution_forms.data:
			for channel_dict in image_resolution_dict['channel_forms']:
				if channel_dict['viz']:
					any_checked=True
		if not any_checked:
			raise ValidationError("No channels were chosen to display."
								  " You must choose at least one in order to proceed.")

""" General visualization form """

class GeneralImageResolutionForm(FlaskForm):
	""" A sub-form for each image resolution """
	image_resolution = HiddenField('image resolution')
	raw_channel_forms = FieldList(FormField(ChannelForm),min_entries=0,max_entries=4)
	stitched_channel_forms = FieldList(FormField(ChannelForm),min_entries=0,max_entries=4)
	blended_channel_forms = FieldList(FormField(BlendedChannelForm),min_entries=0,max_entries=4)
	downsized_channel_forms = FieldList(FormField(DownsizedChannelForm),min_entries=0,max_entries=4)
	registered_channel_forms = FieldList(FormField(RegisteredChannelForm),min_entries=0,max_entries=4)

class GeneralDataSetupForm(FlaskForm):
	""" A form for setting up how user wants to visualize
	their precomputed data products for a given processing request in Neuroglancer.
	"""
	image_resolution_forms = FieldList(
		FormField(GeneralImageResolutionForm),min_entries=0,max_entries=4)
	submit = SubmitField('Submit') # renders a new resolution table
	
	def validate_image_resolution_forms(self,image_resolution_forms):
		""" Check to make sure at least one checkbox was checked 
		out of all types of forms"""
		any_checked=False
		for image_resolution_dict in self.image_resolution_forms.data:
			for channel_dict in image_resolution_dict['raw_channel_forms']:
				if channel_dict['viz_left_lightsheet'] or channel_dict['viz_right_lightsheet']:
					any_checked=True
			for channel_dict in image_resolution_dict['stitched_channel_forms']:
				if channel_dict['viz_left_lightsheet'] or channel_dict['viz_right_lightsheet']:
					any_checked=True
			for channel_dict in image_resolution_dict['blended_channel_forms']:
				if channel_dict['viz']:
					any_checked=True
			for channel_dict in image_resolution_dict['downsized_channel_forms']:
				if channel_dict['viz']:
					any_checked=True
			for channel_dict in image_resolution_dict['registered_channel_forms']:
				if channel_dict['viz']:
					any_checked=True
		if not any_checked:
			raise ValidationError("No channels were chosen to display."
								  " You must choose at least one in order to proceed.")


""" Brain selection form for Jess' c-Fos experiments """

class AnimalForm(FlaskForm):
	""" A sub-form for each image resolution in RawDataSetupForm """
	dataset = HiddenField('dataset')
	animal_id = HiddenField('animal_id')
	eroded_cells = HiddenField('Eroded cells?')
	viz = BooleanField("Visualize?")

class CfosSetupForm(FlaskForm):
	""" A form for setting up how user wants to visualize
	their raw data for a given imaging request in Neuroglancer
	"""
	animal_forms = FieldList(FormField(AnimalForm),min_entries=0,max_entries=40)
	submit = SubmitField('Submit')
	
	def validate_animal_forms(self,animal_forms):
		""" Check to make sure at 1 checkbox was checked. No more no less."""
		n_checked = [animal_form.data['viz']==True for animal_form in self.animal_forms].count(True)
		if n_checked == 0:
			raise ValidationError("No animal ids were checked when you hit submit. One needs to be checked")
		elif n_checked >1:
			raise ValidationError("Only one box can be checked when you hit submit.")
		
