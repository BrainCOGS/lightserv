from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField, SelectField, BooleanField
from wtforms.fields.html5 import DateField, DateTimeLocalField
from wtforms.validators import DataRequired, Length, InputRequired, ValidationError

class iDiscoPlusImmunoForm(FlaskForm):
	""" The form for requesting a new experiment/dataset """
	# notes = TextAreaField('iDISCO+_immuno Notes',validators=[Length(max=1000)])
	datetimeformat='%Y-%m-%dT%H:%M' # To get form.field.data to work. Does not work with the default (bug)
	perfusion_date = DateField('Perfusion date')
	perfusion_date_submit = SubmitField('Update')
	time_dehydr_pbs_wash1 = DateTimeLocalField('1xPBS 30 min R@RT',format=datetimeformat)
	time_dehydr_pbs_wash1_submit = SubmitField('Update')
	time_dehydr_pbs_wash2 = DateTimeLocalField('2xPBS 30 min R@RT',format=datetimeformat)
	time_dehydr_pbs_wash2_submit = SubmitField('Update')
	time_dehydr_pbs_wash3 = DateTimeLocalField('3xPBS 30 min R@RT',format=datetimeformat)
	time_dehydr_pbs_wash3_submit = SubmitField('Update')

	time_dehydr_ch3oh_20percent_wash1 = DateTimeLocalField('20% CH3OH R@RTx1hr',format=datetimeformat)
	time_dehydr_ch3oh_20percent_wash1_submit = SubmitField('Update')
	time_dehydr_ch3oh_40percent_wash1 = DateTimeLocalField('40% CH3OH R@RTx1hr',format=datetimeformat)
	time_dehydr_ch3oh_40percent_wash1_submit = SubmitField('Update')
	time_dehydr_ch3oh_60percent_wash1 = DateTimeLocalField('60% CH3OH R@RTx1hr',format=datetimeformat)
	time_dehydr_ch3oh_60percent_wash1_submit = SubmitField('Update')
	time_dehydr_ch3oh_80percent_wash1 = DateTimeLocalField('80% CH3OH R@RTx1hr',format=datetimeformat)
	time_dehydr_ch3oh_80percent_wash1_submit = SubmitField('Update')
	time_dehydr_ch3oh_100percent_wash1 = DateTimeLocalField('100% CH3OH R@RTx1hr (first hour)',format=datetimeformat)
	time_dehydr_ch3oh_100percent_wash1_submit = SubmitField('Update')
	time_dehydr_ch3oh_100percent_wash2 = DateTimeLocalField('100% CH3OH R@RTx1hr (second hour)',format=datetimeformat)
	time_dehydr_ch3oh_100percent_wash2_submit = SubmitField('Update')

	time_dehydr_h202_wash1 = DateTimeLocalField('5% H2O2(30%) in CH3OH(100%) O/N R@RT (1 part H2O2:5 parts methanol)',format=datetimeformat)
	time_dehydr_h202_wash1_submit = SubmitField('Update')
	time_rehydr_ch3oh_100percent_wash1 = DateTimeLocalField('100% CH3OH R@RTx1hr',format=datetimeformat)
	time_rehydr_ch3oh_100percent_wash1_submit = SubmitField('Update')
	time_rehydr_ch3oh_80percent_wash1 = DateTimeLocalField('80% CH3OH R@RTx1hr',format=datetimeformat)
	time_rehydr_ch3oh_80percent_wash1_submit = SubmitField('Update')
	time_rehydr_ch3oh_60percent_wash1 = DateTimeLocalField('60% CH3OH R@RTx1hr',format=datetimeformat)
	time_rehydr_ch3oh_60percent_wash1_submit = SubmitField('Update')
	time_rehydr_ch3oh_40percent_wash1 = DateTimeLocalField('40% CH3OH R@RTx1hr',format=datetimeformat)
	time_rehydr_ch3oh_40percent_wash1_submit = SubmitField('Update')
	time_rehydr_ch3oh_20percent_wash1 = DateTimeLocalField('20% CH3OH R@RTx1hr',format=datetimeformat)
	time_rehydr_ch3oh_20percent_wash1_submit = SubmitField('Update')
	time_rehydr_pbs_wash1 = DateTimeLocalField('PBS R@RTx1hr',format=datetimeformat)
	time_rehydr_pbs_wash1_submit = SubmitField('Update')
	time_rehydr_sodium_azide_wash1 = DateTimeLocalField('0.2%TritonX-100/1xPBS/0.1% sodium azide R@RTx1hr (first hour)',format=datetimeformat)
	time_rehydr_sodium_azide_wash1_submit = SubmitField('Update')
	time_rehydr_sodium_azide_wash2 = DateTimeLocalField('0.2%TritonX-100/1xPBS/0.1% sodium azide R@RTx1hr (second hour)',format=datetimeformat)
	time_rehydr_sodium_azide_wash2_submit = SubmitField('Update')
	time_rehydr_glycine_wash1 = DateTimeLocalField('20%DMSO/0.3M glycine/0.2% TritonX-100/0.1%sodium azide/1xPBS R@37C for 2 days',format=datetimeformat)
	time_rehydr_glycine_wash1_submit = SubmitField('Update')
	time_blocking_start_roomtemp = DateTimeLocalField('Sample R@RT for ~1.5hrs',format=datetimeformat)
	time_blocking_start_roomtemp_submit = SubmitField('Update')
	time_blocking_donkey_serum = DateTimeLocalField('10% DMSO / 6% Donkey seum / 0.2%TritonX-100 / 0.1%sodium azide / 1xPBS, R@37°C for 2-3 days',format=datetimeformat)
	time_blocking_donkey_serum_submit = SubmitField('Update')
	time_antibody1_start_roomtemp = DateTimeLocalField('Sample R@RT for ~1.5hrs',format=datetimeformat)
	time_antibody1_start_roomtemp_submit = SubmitField('Update')
	time_antibody1_ptwh_wash1 = DateTimeLocalField('PTwH R@RTx1hr (first hour)',format=datetimeformat)
	time_antibody1_ptwh_wash1_submit = SubmitField('Update')
	time_antibody1_ptwh_wash2 = DateTimeLocalField('PTwH R@RTx1hr (second hour)',format=datetimeformat)
	time_antibody1_ptwh_wash2_submit = SubmitField('Update')
	time_antibody1_added = DateTimeLocalField('primary antibody (5% DMSO, 3% donkey serum in PTwH); 37C 7d',format=datetimeformat)
	time_antibody1_added_submit = SubmitField('Update')
	time_wash_start_roomtemp = DateTimeLocalField('primary antibody (5% DMSO, 3% donkey serum in PTwH); 37C 7d',format=datetimeformat)
	time_wash_start_roomtemp_submit = SubmitField('Update')
	time_wash_ptwh_wash1 = DateTimeLocalField('primary antibody (5% DMSO, 3% donkey serum in PTwH); 37C 7d',format=datetimeformat)
	time_wash_ptwh_wash1_submit = SubmitField('Update')
	time_wash_ptwh_wash2 = DateTimeLocalField('primary antibody (5% DMSO, 3% donkey serum in PTwH); 37C 7d',format=datetimeformat)
	time_wash_ptwh_wash2_submit = SubmitField('Update')
	time_wash_ptwh_wash3 = DateTimeLocalField('primary antibody (5% DMSO, 3% donkey serum in PTwH); 37C 7d',format=datetimeformat)
	time_wash_ptwh_wash3_submit = SubmitField('Update')
	time_wash_ptwh_wash4 = DateTimeLocalField('primary antibody (5% DMSO, 3% donkey serum in PTwH); 37C 7d',format=datetimeformat)
	time_wash_ptwh_wash4_submit = SubmitField('Update')
	time_wash_ptwh_wash5 = DateTimeLocalField('primary antibody (5% DMSO, 3% donkey serum in PTwH); 37C 7d',format=datetimeformat)
	time_wash_ptwh_wash5_submit = SubmitField('Update')
	time_antibody2_added = DateTimeLocalField('primary antibody (5% DMSO, 3% donkey serum in PTwH); 37C 7d',format=datetimeformat)
	time_antibody2_added_submit = SubmitField('Update')
	time_clearing_ch3oh_20percent_wash1 = DateTimeLocalField('primary antibody (5% DMSO, 3% donkey serum in PTwH); 37C 7d',format=datetimeformat)
	time_clearing_ch3oh_20percent_wash1_submit = SubmitField('Update')
	time_clearing_ch3oh_40percent_wash1 = DateTimeLocalField('primary antibody (5% DMSO, 3% donkey serum in PTwH); 37C 7d',format=datetimeformat)
	time_clearing_ch3oh_40percent_wash1_submit = SubmitField('Update')
	time_clearing_ch3oh_60percent_wash1 = DateTimeLocalField('primary antibody (5% DMSO, 3% donkey serum in PTwH); 37C 7d',format=datetimeformat)
	time_clearing_ch3oh_60percent_wash1_submit = SubmitField('Update')
	time_clearing_ch3oh_80percent_wash1 = DateTimeLocalField('primary antibody (5% DMSO, 3% donkey serum in PTwH); 37C 7d',format=datetimeformat)
	time_clearing_ch3oh_80percent_wash1_submit = SubmitField('Update')
	time_clearing_ch3oh_100percent_wash1 = DateTimeLocalField('primary antibody (5% DMSO, 3% donkey serum in PTwH); 37C 7d',format=datetimeformat)
	time_clearing_ch3oh_100percent_wash1_submit = SubmitField('Update')
	time_clearing_dcm_66percent_ch3oh_33percent = DateTimeLocalField('primary antibody (5% DMSO, 3% donkey serum in PTwH); 37C 7d',format=datetimeformat)
	time_clearing_dcm_66percent_ch3oh_33percent_submit = SubmitField('Update')
	time_clearing_dcm_wash1 = DateTimeLocalField('primary antibody (5% DMSO, 3% donkey serum in PTwH); 37C 7d',format=datetimeformat)
	time_clearing_dcm_wash1_submit = SubmitField('Update')
	time_clearing_dcm_wash2 = DateTimeLocalField('primary antibody (5% DMSO, 3% donkey serum in PTwH); 37C 7d',format=datetimeformat)
	time_clearing_dcm_wash2_submit = SubmitField('Update')
	time_clearing_dbe = DateTimeLocalField('primary antibody (5% DMSO, 3% donkey serum in PTwH); 37C 7d',format=datetimeformat)
	time_clearing_dbe_submit = SubmitField('Update')
	time_clearing_new_tubes = DateTimeLocalField('primary antibody (5% DMSO, 3% donkey serum in PTwH); 37C 7d',format=datetimeformat)
	time_clearing_new_tubes_submit = SubmitField('Update')
	clearing_notes = TextAreaField('Clearing Notes')

	submit = SubmitField('Submit Changes')

class iDiscoAbbreviatedForm(FlaskForm):
	""" The form for requesting a new experiment/dataset """
	notes = TextAreaField('iDISCO Abbreviated Clearing Notes',validators=[Length(max=1000)])
	submit = SubmitField('Submit Changes')	

class uDiscoForm(FlaskForm):
	""" The form for requesting a new experiment/dataset """
	notes = TextAreaField('uDISCO Notes',validators=[Length(max=1000)])
	submit = SubmitField('Submit Changes')	

class iDiscoPlusForm(FlaskForm):
	""" The form for requesting a new experiment/dataset """
	notes = TextAreaField('iDISCO+ Notes',validators=[Length(max=1000)])
	submit = SubmitField('Submit Changes')	

class iDiscoEduForm(FlaskForm):
	""" The form for requesting a new experiment/dataset """
	notes = TextAreaField('iDISCO_EdU Notes',validators=[Length(max=1000)])
	submit = SubmitField('Submit Changes')	