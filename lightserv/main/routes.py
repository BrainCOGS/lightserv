from flask import (render_template, request, redirect,
				   Blueprint, session, url_for, flash,
				   Markup, Request, Response,abort)
from lightserv import db_lightsheet, db_admin, db_spockadmin
from lightserv.main.utils import (logged_in, table_sorter,
	 log_http_requests, logged_in_as_admin,
	 logged_in_as_dash_admin, get_lightsheet_storage)
from lightserv.main.forms import SpockConnectionTesterForm, FeedbackForm
from lightserv.main.tables import RequestTable, AdminTable
from lightserv.processing.tasks import spock_job_status_checker
import datajoint as dj
import pandas as pd
import numpy as np

import os
import socket
import logging
import paramiko
from datetime import datetime, timedelta
import calendar

# bokeh plotting

from bokeh.plotting import figure, output_file, show
from bokeh.embed import components
from bokeh.resources import INLINE
from bokeh.layouts import column, row, layout

from bokeh.models import (ColumnDataSource, DatetimeTickFormatter, 
	FactorRange, Legend, LabelSet, HoverTool,Select, Slider,CategoricalTicker)
from bokeh.models.callbacks import CustomJS
from bokeh.models.tickers import MonthsTicker
from bokeh.transform import dodge
from bokeh.palettes import Category20c,Category10
from bokeh.transform import cumsum


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')

''' Make the file handler to deal with logging to file '''
file_handler = logging.FileHandler('logs/main_routes.log')
file_handler.setFormatter(formatter)

stream_handler = logging.StreamHandler() # level already set at debug from logger.setLevel() above

stream_handler.setFormatter(formatter)

logger.addHandler(stream_handler)
logger.addHandler(file_handler)

main = Blueprint('main',__name__)

@main.route("/") 
@main.route("/welcome")
@logged_in
@log_http_requests
def welcome(): 
	current_user = session['user']
	logger.info(f"{current_user} accessed welcome page")
	return render_template('main/welcome.html',)

@main.route("/gallery")
@logged_in
@log_http_requests
def gallery(): 
	current_user = session['user']
	logger.info(f"{current_user} accessed gallery page")
	return render_template('main/gallery.html',)

@main.route("/FAQ")
@logged_in
@log_http_requests
def FAQ(): 
	current_user = session['user']
	logger.info(f"{current_user} accessed FAQ")
	return render_template('main/FAQ.html')

@main.route("/publications")
@logged_in
@log_http_requests
def publications(): 
	current_user = session['user']
	logger.info(f"{current_user} accessed publications page")
	return render_template('main/publications.html',)
	
@main.route("/spock_connection_test",methods=['GET','POST'])
@logged_in
@log_http_requests
def spock_connection_test(): 
	form = SpockConnectionTesterForm()
	if request.method == 'POST':
		hostname = 'spock.pni.princeton.edu'
		current_user = session['user']	
		port = 22
		client = paramiko.SSHClient()
		client.load_system_host_keys()
		client.set_missing_host_key_policy(paramiko.AutoAddPolicy)
		try:
			client.connect(hostname, port=port, username=current_user, allow_agent=False,look_for_keys=True)
			flash("Successfully connected to spock.","success")
		except:
			flash("Connection unsuccessful. Please refer to the FAQ and try again.","danger")
		finally:
			client.close()

	return render_template('main/spock_connection_test.html',form=form)

@main.route('/login', methods=['GET', 'POST'])
def login():
	next_url = request.args.get("next")
	logger.info("Logging you in first!")
	user_agent = request.user_agent
	logger.debug(user_agent)
	browser_name = user_agent.browser # e.g. chrome
	browser_version = user_agent.version # e.g. '78.0.3904.108'
	platform = user_agent.platform # e.g. linux
	
	if browser_name.lower() != 'chrome':
		logger.info(f"User is using browser {browser_name}")
		flash(f"Warning: parts of this web portal were not completely tested on your browser: {browser_name}. "
		 "Firefox users will experience some known issues. We recommend switching to Google Chrome for a better experience.",'danger')
	hostname = socket.gethostname()
	if hostname == 'docker_lightserv':
		username = request.headers['X-Remote-User']
	else:
		username = 'testuser' # pragma: no cover - used to exclude this line from testing

	session['user'] = username
	''' If user not already in User() table, then add them '''
	all_usernames = db_lightsheet.User().fetch('username') 
	if username not in all_usernames:
		email = username + '@princeton.edu'
		user_dict = {'username':username,'princeton_email':email}
		db_lightsheet.User().insert1(user_dict)
		logger.info(f"Added {username} to User table in database")
	logstr = f'{username} logged in via "login()" route in lightserv.main.routes'
	insert_dict = {'browser_name':browser_name,'browser_version':browser_version,
				   'event':logstr,'platform':platform}
	db_admin.UserActionLog().insert1(insert_dict)
	
	return redirect(next_url)

@main.route("/pre_handoff_instructions")
@logged_in
@log_http_requests
def pre_handoff(): 
	current_user = session['user']
	logger.info(f"{current_user} accessed pre_handoff route")
	return render_template('main/pre_handoff.html')

@main.route("/feedback_form/<username>/<request_name>",methods=['GET','POST'])
@logged_in
@log_http_requests
def feedback(username,request_name): 
	current_user = session['user']
	logger.info(f"{current_user} accessed feedback route")
	request_contents = db_lightsheet.Request() & {'username':username,'request_name':request_name}
	if len(request_contents) == 0:
		flash("No request with those parameters exists","danger")
		abort(404)
	# if current_user != username:
	# 	flash("You do not have permission to view the feedback form","danger")
	# 	logger.info(f"{current_user} accessed feedback form for {username}/{request_name} -"
	# 		         "they do not have permission and are being redirected")
	# 	return redirect(url_for('main.welcome'))
	feedback_table_contents = db_admin.RequestFeedback() & f'username="{username}"' & \
		f'request_name="{request_name}"'
	# if len(feedback_table_contents) > 0:
	# 	flash("Feedback already received for this request. Thank you.","warning")
	# 	logger.info(f"Feedback form for {username}/{request_name} "
	# 		         "already submitted.")
	# 	return redirect(url_for('main.welcome'))

	
	form = FeedbackForm()
	table = RequestTable(request_contents)

	if request.method == 'POST':
		logger.debug("POST request")
		if form.validate_on_submit():
			logger.debug("Form validated")
			feedback_insert_dict = {}
			feedback_insert_dict['username'] = username
			feedback_insert_dict['request_name'] = request_name
			feedback_insert_dict['clearing_rating'] = form.clearing_rating.data
			feedback_insert_dict['clearing_notes'] = form.clearing_notes.data
			feedback_insert_dict['imaging_rating'] = form.imaging_rating.data
			feedback_insert_dict['imaging_notes'] = form.imaging_notes.data
			feedback_insert_dict['processing_rating'] = form.processing_rating.data
			feedback_insert_dict['processing_notes'] = form.processing_notes.data
			feedback_insert_dict['other_notes'] = form.other_notes.data
			db_admin.RequestFeedback().insert1(feedback_insert_dict,skip_duplicates=True)
			flash("Feedback received. Thank you.","success")
			return redirect(url_for("main.welcome"))
		else:
			logger.debug("Form NOT validated") # pragma: no cover - used to exclude this line from testing
			logger.debug(form.errors) # pragma: no cover - used to exclude this line from testing
	return render_template('main/feedback_form.html',
		form=form,table=table)

@main.route("/admin") 
@logged_in_as_admin
@log_http_requests
def admin(): 
	""" Show last 20 entries to the user action log in an
	html table """
	current_user = session['user']
	user_action_contents = db_admin.UserActionLog() 
	""" First get last 20 """
	result=user_action_contents.fetch(limit=20,order_by='timestamp DESC',as_dict=True) 
	""" Then reverse order so they are in chronological order """
	# df_chron = df.iloc[::-1]
	admin_table = AdminTable(result[::-1])
	logger.info(f"{current_user} accessed admin page")
	return render_template('main/admin.html',admin_table=admin_table)

@main.route("/admin/dash") 
@logged_in_as_dash_admin
@log_http_requests
def dash(): 
	""" Show Core Facility Dashboard """
	current_user = session['user']
	logger.debug(f"{current_user} accessed dash route")
	
	### CLEARING
	clearing_batch_contents = db_lightsheet.Request.ClearingBatch()
	request_contents = db_lightsheet.Request()
	sample_contents = db_lightsheet.Request.Sample()
	requests_samples_joined = request_contents * sample_contents    
	combined_contents = (clearing_batch_contents * request_contents).proj(
		'number_in_batch','expected_handoff_date',
		'clearing_protocol','species',
		'clearer','clearing_progress','clearing_protocol','antibody1','antibody2',
		datetime_submitted='TIMESTAMP(date_submitted,time_submitted)')
	''' First get all entities that are currently being cleared '''
	contents_being_cleared = combined_contents & 'clearing_progress="in progress"'
	contents_ready_to_clear = combined_contents & 'clearing_progress="incomplete"' 
	contents_already_cleared = (combined_contents & 'clearing_progress="complete"')
	x_clearing = {
		'Ready': len(contents_ready_to_clear),
		'In progress': len(contents_being_cleared),
		'Cleared': len(contents_already_cleared),
	}
	data_clearing = pd.Series(x_clearing).reset_index(name='value').rename(columns={'index':'status'})
	empty_mask = data_clearing.value == 0
	data_clearing.loc[empty_mask,'value'] = 0.001 # a hack to get tooltip to show up even for zero entries
	data_clearing['angle'] = data_clearing['value']/data_clearing['value'].sum() * 2*np.pi
	data_clearing['color'] = Category10[len(x_clearing)]

	plot_clearing = figure(sizing_mode='scale_width',title="Clearing batches", toolbar_location=None,
			   tools="hover", tooltips="@status: @value", x_range=(-0.5, 1.0))

	plot_clearing.wedge(x=0, y=1, radius=0.4,
			start_angle=cumsum('angle', include_zero=True), end_angle=cumsum('angle'),
			line_color="white", fill_color='color', legend_field='status', source=data_clearing)

	plot_clearing.axis.axis_label=None
	plot_clearing.axis.visible=False
	plot_clearing.legend.label_text_font_size='16pt'
	plot_clearing.grid.grid_line_color = None
	plot_clearing.title.align = 'center'
	plot_clearing.title.text_font_size = "24px"
	script_clearing, div_clearing = components(plot_clearing)

	### IMAGING

	imaging_batch_contents = db_lightsheet.Request.ImagingBatch()
	imaging_resolution_contents = db_lightsheet.Request.ImagingResolutionRequest()

	imaging_request_contents = (clearing_batch_contents * sample_contents * \
		request_contents * imaging_batch_contents).\
			proj('clearer','clearing_progress',
			'imaging_request_date_submitted','imaging_request_time_submitted',
			'imaging_progress','imager','species','number_in_imaging_batch',
			datetime_submitted='TIMESTAMP(imaging_request_date_submitted,imaging_request_time_submitted)',)
	''' Figure out how many imaging requests used only Lavision or only Smartspim '''
	aggr_imaging_resolution_table = dj.U('username','request_name',
								  'sample_name','imaging_request_number').aggr(
		imaging_resolution_contents,
		all_samples_lavision='SUM(IF(microscope="lavision",1,0))=count(*)',
		all_samples_smartspim='SUM(IF(microscope="smartspim",1,0))=count(*)')
	joined_table = imaging_request_contents*aggr_imaging_resolution_table
	combined_imaging_contents = dj.U('username','request_name',
		'clearing_batch_number',
		'imaging_batch_number','imaging_request_number').aggr(
		joined_table,
		clearer='MIN(clearer)',
		clearing_progress='MIN(clearing_progress)',
		imaging_progress='MIN(imaging_progress)',
		all_samples_cleared='SUM(IF(clearing_progress="complete",1,0))=count(*)')

	''' First get all entities that are currently being imaged '''
	
	contents_being_imaged = combined_imaging_contents & 'all_samples_cleared=1' & \
		'imaging_progress="in progress"'

	''' Next get all entities that are ready to be imaged '''
	contents_ready_to_image = combined_imaging_contents & 'all_samples_cleared=1' & \
	 'imaging_progress="incomplete"'
	''' Now get all entities on deck (currently being cleared) '''
	contents_on_deck = combined_imaging_contents & 'clearing_progress!="complete"' & 'imaging_progress!="complete"'
	''' Finally get all entities that have already been imaged '''
	contents_already_imaged = (combined_imaging_contents & 'imaging_progress="complete"')

	x_imaging = {
		'Ready': len(contents_ready_to_image),
		'In progress': len(contents_being_imaged),
		'Imaged': len(contents_already_imaged),
	}
	data_imaging = pd.Series(x_imaging).reset_index(name='value').rename(columns={'index':'status'})
	empty_mask = data_imaging.value == 0
	data_imaging.loc[empty_mask,'value'] = 0.001 # a hack to get tooltip to show up even for zero entries
	data_imaging['angle'] = data_imaging['value']/data_imaging['value'].sum() * 2*np.pi
	data_imaging['color'] = Category10[len(x_imaging)]

	plot_imaging = figure(sizing_mode='scale_width',title="Imaging batches", toolbar_location=None,
			   tools="hover", tooltips="@status: @value", x_range=(-0.5, 1.0))

	plot_imaging.wedge(x=0, y=1, radius=0.4,
			start_angle=cumsum('angle', include_zero=True), end_angle=cumsum('angle'),
			line_color="white", fill_color='color', legend_field='status', source=data_imaging)

	plot_imaging.axis.axis_label=None
	plot_imaging.axis.visible=False
	plot_imaging.legend.label_text_font_size='16pt'

	plot_imaging.grid.grid_line_color = None
	plot_imaging.title.align = 'center'
	plot_imaging.title.text_font_size = "24px"
	script_imaging, div_imaging = components(plot_imaging)

	### Microscope usage

	# Look up number of requests in each of the last 6 months 
	imaging_requests = db_lightsheet.Request.ImagingRequest()
	imaging_resolution_requests_joined = request_contents * imaging_resolution_contents * imaging_requests
	now = datetime.now()
	firstday_month = (now - timedelta(days=now.day-1)).date()
	thisyear = firstday_month.year
	thismonth = firstday_month.month
	samples_this_month = requests_samples_joined & f'YEAR(date_submitted)={thisyear}' & \
		f'MONTH(date_submitted)={thismonth}'
	imaging_resolution_requests_this_month = imaging_resolution_requests_joined & \
		f'YEAR(imaging_performed_date)={thisyear}' & \
		f'MONTH(imaging_performed_date)={thismonth}'
	imaging_resolution_requests_this_month_lavision = imaging_resolution_requests_this_month & \
		'image_resolution in ("1.1x","1.3x","4x","2x")'
	imaging_resolution_requests_this_month_smartspim = imaging_resolution_requests_this_month & \
		'image_resolution in ("3.6x","15x")'
	n_samples_this_month = len(samples_this_month)
	n_uses_lavision = len(imaging_resolution_requests_this_month_lavision)
	n_uses_smartspim = len(imaging_resolution_requests_this_month_smartspim)
	last_day_of_the_month = calendar.monthrange(year=thisyear,month=thismonth)[-1]
	lastday_month = datetime.strptime(
		f"{thisyear}-{str(thismonth).zfill(2)}-{last_day_of_the_month}","%Y-%m-%d").date()
	
	month_list = [firstday_month]
	samples_count_list = [n_samples_this_month]
	uses_count_list_lavision = [n_uses_lavision]
	uses_count_list_smartspim = [n_uses_smartspim]
	for month_count in range(6):
		lastday_month = firstday_month-timedelta(days=1)
		firstday_month = lastday_month-timedelta(days=(lastday_month.day-1))
		samples_month = requests_samples_joined & f'date_submitted >= "{firstday_month}"' & f'date_submitted <= "{lastday_month}"' 
		imaging_resolution_requests_month = imaging_resolution_requests_joined & f'imaging_performed_date >= "{firstday_month}"' & f'imaging_performed_date <= "{lastday_month}"' 
		imaging_resolution_requests_month_lavision = imaging_resolution_requests_month & \
			'image_resolution in ("1.1x","1.3x","4x","2x")'
		imaging_resolution_requests_month_smartspim = imaging_resolution_requests_month & \
			'image_resolution in ("3.6x","15x")'
		month_list.append(firstday_month)
		samples_count_list.append(len(samples_month))
		uses_count_list_lavision.append(len(imaging_resolution_requests_month_lavision ))
		uses_count_list_smartspim.append(len(imaging_resolution_requests_month_smartspim ))
	
	# Reverse lists so they are in chronological order
	month_list = month_list[::-1]
	samples_count_list = samples_count_list[::-1]
	uses_count_list_lavision = uses_count_list_lavision[::-1]
	uses_count_list_smartspim = uses_count_list_smartspim[::-1]

	data_microscopes=[{
		'date':month_list[ii].strftime('%b %Y'),
		'n_uses_lavision':uses_count_list_lavision[ii],
		'n_uses_smartspim':uses_count_list_smartspim[ii],
		} for ii in range(len(month_list))]
	df_microscopes=pd.DataFrame(data_microscopes)

	data = {'date' : df_microscopes['date'],
			'lavision'   : df_microscopes['n_uses_lavision'],
			'smartspim'   : df_microscopes['n_uses_smartspim']}
	source_microscopes = ColumnDataSource(data=data)
	microscope_usage_plot = figure(sizing_mode='scale_width',x_range=df_microscopes['date'],
	 title="Microscope usage in recent months",
		   toolbar_location=None)

	microscope_usage_plot.title.align = 'center'
	microscope_usage_plot.title.text_font_size = "24px"
	microscope_usage_plot.xaxis.group_text_font_size = "18px"
	microscope_usage_plot.xaxis.major_label_text_font_size = "12pt"
	microscope_usage_plot.xaxis.major_label_orientation = np.pi/4

	lavision_usage = microscope_usage_plot.vbar(
		x=dodge('date', -0.1, range=microscope_usage_plot.x_range),
		 top='lavision', width=0.2, source=source_microscopes,
		   color="#c9d9d3",name='lavision')

	smartspim_usage = microscope_usage_plot.vbar(
		x=dodge('date',  0.1, range=microscope_usage_plot.x_range),
		 top='smartspim', width=0.2, source=source_microscopes,
		   color="#e84d60",name='smartspim')
	
	hover_lavision = HoverTool(tooltips=[("LaVision","@lavision")],names=['lavision'])
	hover_smartspim = HoverTool(tooltips=[("SmartSPIM","@smartspim")],names=['smartspim'])
	microscope_usage_plot.add_tools(hover_lavision)
	microscope_usage_plot.add_tools(hover_smartspim)
	legend = Legend(items=[
	("Lavision"   , [lavision_usage]),
	("SmartSPIM" , [smartspim_usage]),
	], location="center")

	microscope_usage_plot.add_layout(legend, 'right')
	microscope_usage_plot.title.text_font_size = "24px"
	microscope_usage_plot.xaxis.axis_label_text_font_size = "18px"
	microscope_usage_plot.yaxis.axis_label_text_font_size = "18px"
	microscope_usage_plot.xaxis.axis_label = "Date"
	microscope_usage_plot.yaxis.axis_label = "Number of brains"

	script_microscope, div_microscope = components(microscope_usage_plot)


	### LightSheetData Usage Plot over time
	storage_time_dict = db_spockadmin.BucketStorage().fetch(as_dict=True)

	df_storage_time = pd.DataFrame(storage_time_dict)
	logger.debug(df_storage_time)
	# df_storage_time['date'] = df_storage_time['timestamp'].dt.strftime('%Y-%m-%d')
	df_storage_time['date'] = df_storage_time['timestamp']
	df_storage_time['used_tb'] = df_storage_time['size_tb'] - df_storage_time['avail_tb']
	storage_time_categories = ['Used','Available']
	colors = ["#718dbf", "#e84d60"]
	data_storage_time = {
	'date':df_storage_time['date'],
	'Used':df_storage_time['used_tb'],
	'Available':df_storage_time['avail_tb']}
	source_storage_time = ColumnDataSource(data=data_storage_time)
	# storage_time_plot = figure(x_range=data_storage_time['date'],
	# 	plot_height=450,plot_width=600, title="LightSheetData Usage History",
	# 	   toolbar_location=None, tools="hover",tooltips="$name @date: @$name{1.1} TB")
	# storage_time_plot = figure(
	# 	plot_height=450,plot_width=600, title="LightSheetData Usage History",
	# 	   toolbar_location=None, tools="",x_axis_type="datetime")
	# storage_time_plot = figure(
	# 	plot_height=450,plot_width=600, title="LightSheetData Usage History",
	# 	   toolbar_location=None, tools="",
	# 	   x_axis_type="datetime")
	storage_time_plot = figure(sizing_mode="scale_width",
		title="LightSheetData Usage History",
		   toolbar_location=None, tools="",
		   x_axis_type="datetime")
	
	storage_time_plot.title.align = 'center'
	storage_time_plot.title.text_font_size = "24px"
	# storage_time_plot.xaxis.group_text_font_size = "18px"
	storage_time_plot.xaxis.major_label_text_font_size = "12pt"
	storage_time_plot.xaxis.major_label_orientation = np.pi/3
	
	vbar_stack = storage_time_plot.vbar_stack(storage_time_categories, x='date',
		width=timedelta(days=1), color=colors, source=data_storage_time)
	
	legend = Legend(items=[
		("Used"   , [vbar_stack[0]]),
		("Available" , [vbar_stack[1]]),
		], location="center")
	
	storage_time_plot.add_layout(legend, 'right')
	storage_time_plot.y_range.start = 0
	storage_time_plot.x_range.range_padding = 0.1
	storage_time_plot.xgrid.grid_line_color = None
	storage_time_plot.axis.minor_tick_line_color = None
	storage_time_plot.outline_line_color = None
	storage_time_plot.title.text_font_size = "24px"
	storage_time_plot.xaxis.axis_label_text_font_size = "18px"
	storage_time_plot.yaxis.axis_label_text_font_size = "18px"
	storage_time_plot.xaxis.axis_label = "Date"
	storage_time_plot.yaxis.axis_label = "Storage Space (TB)"
	
	for vbar in vbar_stack[0:1]:
		name = vbar.name
		hover = HoverTool(
		    tooltips=[
		        ( 'Date',   '@date{%F}'            ),
		        ( 'Used',  '@Used{%0.2f} TB' ),
		        ( 'Available',  '@Available{%0.2f} TB' ),
		    ],

		    formatters={'@date': 'datetime',
		    			'@Used' : 'printf',
		    			'@Available' : 'printf',},

		    # display a tooltip whenever the cursor is vertically in line with a glyph
		    mode='vline',
		    renderers=[vbar],
			)
		storage_time_plot.add_tools(hover)


	storage_time_plot.xaxis.formatter=DatetimeTickFormatter(
        hours=["%d %B %Y"],
        days=["%d %B %Y"],
        months=["%d %B %Y"],
        years=["%d %B %Y"],
    )

	script_storage_time, div_storage_time = components(storage_time_plot)
	# my_layout = layout([plot_clearing])
	return render_template(
		'main/dash.html',
		script_clearing=script_clearing,
		div_clearing=div_clearing,
		script_imaging=script_imaging,
		div_imaging=div_imaging,
		script_microscope=script_microscope,
		div_microscope=div_microscope,
		script_storage_time=script_storage_time,
		div_storage_time=div_storage_time,
		js_resources=INLINE.render_js(),
		css_resources=INLINE.render_css(),
	).encode(encoding='UTF-8')

@main.route("/test_cel")
def test_cel(): 
	from . import tasks as maintasks
	
	future_time = datetime.utcnow() + timedelta(seconds=1)
	print("sending hello task")
	maintasks.hello.apply_async(eta=future_time) 
	print("sent hello task")
	return "sent task"

@main.route("/test_bucket_storage")
def test_bucket_storage(): 
	from . import tasks as maintasks
	output = maintasks.check_lightsheetdata_storage.run() 
	return output

@main.route("/test_job_status_checker")
def test_job_status_checker():
	# spock_dbtable_str = 'SmartspimStitchingSpockJob'
	# lightsheet_dbtable_str = 'Request.SmartspimStitchedChannel'
	# lightsheet_column_name = 'smartspim_stitching_spock_jobid'
	# max_step_index=3
	spock_dbtable_str = 'SmartspimDependentStitchingSpockJob'
	lightsheet_dbtable_str = 'Request.SmartspimStitchedChannel'
	lightsheet_column_name = 'smartspim_stitching_spock_jobid'
	max_step_index=2

	# spock_dbtable_str='SmartspimPystripeSpockJob'
	# lightsheet_dbtable_str='Request.SmartspimPystripeChannel'
	# lightsheet_column_name='smartspim_pystripe_spock_jobid'
	# max_step_index=0
	return spock_job_status_checker.run(spock_dbtable_str,
		lightsheet_dbtable_str,
		lightsheet_column_name,
		max_step_index)