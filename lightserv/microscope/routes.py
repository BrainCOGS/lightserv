from flask import (Blueprint, redirect, render_template,
                     url_for, flash, request, session,jsonify)
from functools import partial
import datajoint as dj
import os
from datetime import datetime,date
from lightserv.microscope.forms import (NewSwapLogEntryForm, UpdateSwapLogEntryForm,
    StatusMonitorSelectForm,MicroscopeActionSelectForm,
    DataEntrySelectForm,ComponentMaintenanceSelectForm,
    LaserMaintenanceForm)
from lightserv import db_lightsheet, db_microscope
from lightserv.microscope.tables import MicroscopeCalibrationTable
from lightserv.main.utils import table_sorter,logged_in
from lightserv.microscope.utils import (microscope_form_picker,
      data_entry_form_picker, data_entry_dbtable_picker,
      component_maintenance_form_picker,component_maintenance_dbtable_picker)
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')

''' Make the file handler to deal with logging to file '''
file_handler = logging.FileHandler('logs/microscope_routes.log')
file_handler.setFormatter(formatter)

stream_handler = logging.StreamHandler() # level already set at debug from logger.setLevel() above

stream_handler.setFormatter(formatter)

logger.addHandler(stream_handler)
logger.addHandler(file_handler)

microscope = Blueprint('microscope',__name__)

@microscope.route('/microscope/landing_page', methods=['GET','POST'])
@logged_in
def landing_page():
    form = MicroscopeActionSelectForm()

    if form.validate_on_submit():
        action = form.action.data
        if action == 'enter_data':
            return redirect(url_for('microscope.data_entry_selector'))
        elif action == 'microscope_config':
            return redirect(url_for('microscope.status_monitor_picker'))
        elif action == 'maintenance':
            return redirect(url_for('microscope.component_maintenance_selector'))
    return render_template('microscope/microscope_landing_page.html',form=form)

@microscope.route('/microscope/data_entry_selector', methods=['GET','POST'])
@logged_in
def data_entry_selector():
    form = DataEntrySelectForm()
  
    if form.validate_on_submit():
        data_entry_type = form.data_entry_type.data    
        return redirect(url_for('microscope.data_entry',data_entry_type=data_entry_type))
    return render_template('microscope/microscope_data_entry_selector.html',form=form)

@microscope.route('/microscope/data_entry/<data_entry_type>', methods=['GET','POST'])
@logged_in
def data_entry(data_entry_type):
    form = data_entry_form_picker(data_entry_type)

    if data_entry_type == 'new_channel':
        microscopes = db_microscope.Microscope().fetch('microscope_name')
        form.microscope_name.choices = [(microscope,microscope) for microscope in microscopes]
    if form.validate_on_submit():
        form_fields = [x for x in form._fields.keys() if 'submit' not in x and 'csrf_token' not in x]
        insert_dict = {field:form[field].data for field in form_fields}
        logger.info("form validated")
        db_table = data_entry_dbtable_picker(data_entry_type)
        try:
            db_table().insert1(insert_dict)
            flash(f"Successfully added your entry into the database!",'success')
            return redirect(url_for('microscope.data_entry_selector'))

        except dj.errors.DuplicateError:
            ''' Figure out the primary key(s) and then report to the user 
            that the combination is already taken '''
            primary_key_list = db_table().primary_key
            primary_key_result_str =', '.join(f'{form[key].label.text} = {insert_dict[key]}' \
                for key in primary_key_list)

            flash(f"An entry already exists in the database with {primary_key_result_str}.\
                    Try again.",'danger')
        logger.debug(f"Inserted data into {data_entry_type} form: {insert_dict}")

    return render_template('microscope/data_entry.html',data_entry_type=data_entry_type,form=form)

@microscope.route('/microscope/status_monitor_picker', methods=['GET','POST'])
@logged_in
def status_monitor_picker():
    form = StatusMonitorSelectForm()
    # microscope = 'light sheet microscope' # default
    # microscope_form = LightSheetStatusForm() # default
    
    centers = db_microscope.Center().fetch('center')
    form.center.choices = [(center,center) for center in centers]
    microscopes = db_microscope.Microscope().fetch('microscope_name')
    form.microscope.choices = [(microscope,microscope) for microscope in microscopes]
  
    if form.validate_on_submit():
        microscope = form.microscope.data
        return redirect(url_for('microscope.status_monitor',microscope=microscope))
    return render_template('microscope/status_monitor_picker.html',form=form)

@microscope.route('/_get_microscopes/')
def _get_microscopes():
    """ Helper function to get microscopes from a given imaging center """
    center = request.args.get('center', 'Bezos Center', type=str)
    microscopes = (db_microscope.Microscope & f'center="{center}"').fetch('microscope_name')
    microscopes_4json = [(microscope,microscope) for microscope in microscopes]
    # print(counties_4json)
    return jsonify(microscopes_4json)

@microscope.route('/microscope_center_js')
def microscope_center_js():
    return render_template("js/microscope_facility_picker.js")

@microscope.route('/microscope/status_monitor/<microscope>', methods=['GET','POST'])
@logged_in
def status_monitor(microscope):
    microscope_form = microscope_form_picker(microscope)

    """ Populate all of the select field with the rest of the choices
    from the db """
    # OBJECTIVE
    lens_types = db_microscope.ObjectiveLensType().fetch('lens_type')
    lens_type_choices = [(lens_type,lens_type) for lens_type in lens_types]
    microscope_form.objective_lens_type.choices = lens_type_choices

    # SCANNER
    scanner_types = db_microscope.ScannerType().fetch('scanner_type')
    scanner_type_choices = [(scanner_type,scanner_type) for scanner_type in scanner_types]
    microscope_form.scanner_type.choices = scanner_type_choices     

    ## FILTERS
    filter_models,filter_types = db_microscope.FilterType().fetch('filter_model','filter_type')
    filter_type_model_choices = [('%s, %s' % (filter_models[ii],filter_types[ii]),'%s, %s' % \
        (filter_models[ii],filter_types[ii])) for ii in range(len(filter_models))]
    # CH1_FILTER
    microscope_form.ch1_filter_type_model.choices = filter_type_model_choices
    # CH2_FILTER
    microscope_form.ch2_filter_type_model.choices = filter_type_model_choices
    # NIR_FILTER
    microscope_form.nir_filter_type_model.choices = filter_type_model_choices
    # VISIBLE FILTER
    microscope_form.visible_filter_type_model.choices = filter_type_model_choices

    ## PREAMPS
    preamp_models = db_microscope.PreAmplifierType().fetch('amp_model')
    preamp_model_choices = [(preamp_model,preamp_model) for preamp_model in preamp_models]
    # CH1 PreAmp
    microscope_form.ch1_preamp_model.choices = preamp_model_choices    
    # CH2 PreAmp
    microscope_form.ch2_preamp_model.choices = preamp_model_choices    

    # DICHROICS
    mirror_models = db_microscope.DichroicMirrorType().fetch('mirror_model')
    mirror_model_choices = [(mirror_model,mirror_model) for mirror_model in mirror_models]
    # LASER DICHROIC
    microscope_form.laser_dichroic_mirror_model.choices = mirror_model_choices
    # EMISSION DICHROIC
    microscope_form.emission_dichroic_mirror_model.choices = mirror_model_choices
 
    # Detectors (PMTs)
    pmt_serial_numbers = db_microscope.Pmt().fetch('pmt_serial')
    pmt_serial_number_choices = [(pmt_serial,pmt_serial) for pmt_serial in pmt_serial_numbers]
    # CH1 Detector
    microscope_form.ch1_detector_serial_number.choices = pmt_serial_number_choices
    # CH2 Detector
    microscope_form.ch2_detector_serial_number.choices = pmt_serial_number_choices
    # DAQ
    daq_names = db_microscope.DaqSystemType().fetch('daq_name')
    daq_name_choices = [(daq_name,daq_name) for daq_name in daq_names]
    microscope_form.daq_name.choices = daq_name_choices
  
    # SOFTWARE
    acq_software_names = db_microscope.AcquisitionSoftware().fetch('acq_software')
    acq_software_name_choices = [(acq_software_name,acq_software_name) for acq_software_name in acq_software_names]
    microscope_form.acq_software_name.choices = acq_software_name_choices
   
    # LASER
    laser_serials = db_microscope.Laser().fetch('laser_serial')
    laser_serial_choices = [(laser_serial,laser_serial) for laser_serial in laser_serials]
    microscope_form.laser_serial.choices = laser_serial_choices

    if request.method == 'POST':
        logger.debug("POST request")
        if microscope_form.validate_on_submit():
            logger.debug("Form validated!")
            ''' Update the database with the current status of components '''
            today = date.today().strftime('%Y-%m-%d')
            # Objective status
            objective_lens_type = microscope_form.objective_lens_type.data
            objective_config_date = today
            objective_status_insert_dict = dict(
                microscope_name=microscope,
                objective_config_date = objective_config_date,
                lens_type=objective_lens_type)
            logger.debug(objective_status_insert_dict)
            db_microscope.ObjectiveStatus().insert1(
                objective_status_insert_dict,skip_duplicates=True)
            
            # Laser status
            laser_serial = microscope_form.laser_serial.data
            laser_change_date = today
            laser_status_insert_dict = dict(
                microscope_name=microscope,
                laser_serial=laser_serial,
                laser_change_date=laser_change_date
                )
            db_microscope.LaserStatus().insert1(
                laser_status_insert_dict,skip_duplicates=True)
            # Scanner status
            scanner_type = microscope_form.scanner_type.data
            scanner_config_date = today
            scanner_status_insert_dict = dict(
                microscope_name=microscope,
                scanner_type=scanner_type,
                scanner_config_date=scanner_config_date
                )
            db_microscope.ScannerStatus().insert1(
                scanner_status_insert_dict,skip_duplicates=True)

            # Magnification telescope
            magnification = microscope_form.magnification_telescope.data
            magnification_insert_dict = dict(
                microscope_name=microscope,
                magnification=magnification,
                change_date=today)
            db_microscope.MagnificationTelescopeStatus().insert1(
                magnification_insert_dict,skip_duplicates=True)

            # CH1 Filter status
            # ch1_filter = microscope_form.ch1_filter_type.data
            # laser_change_date = today
            # laser_status_insert_dict = dict(
            #     microscope_name=microscope,
            #     laser_serial=laser_serial,
            #     laser_change_date=laser_change_date
            #     )
            # db_microscope.LaserStatus().insert1(
            #     laser_status_insert_dict,skip_duplicates=True)
            flash("Configuration saved","success")
        else:
            flash("There were errrors in the input. See below for details","danger")
            logger.debug("Not validated!")
            logger.debug(microscope_form.errors)

    ''' Now set the values in the form to ones stored last in the database '''

    # LASER
    try:
        last_laser_serial = \
            (db_microscope.LaserStatus() & f'microscope_name="{microscope}"').fetch(
            'laser_serial',
            order_by='laser_change_date')[-1]
        logger.debug("Laser: {}".format(last_laser_serial))
        microscope_form.laser_serial.data = last_laser_serial
    except:
        logger.debug("did not update laser serial")
        pass
    
    # OBJECTIVE
    
    # fetch the most recent saved value in the db, if there is one
    try:
        # logger.debug(db_microscope.ObjectiveStatus.Objective())
        last_objective_lens_type = \
            (db_microscope.ObjectiveStatus() & f'microscope_name="{microscope}"').fetch(
                'lens_type',order_by='objective_config_date')[-1]
        logger.debug('Objective: {}'.format(last_objective_lens_type))
        microscope_form.objective_lens_type.data = last_objective_lens_type
    except:
        logger.debug("did not update objective lens")
        pass

    # MAGNIFICATION TELESCOPE
    try:
        last_magnification = \
            (db_microscope.MagnificationTelescopeStatus() & f'microscope_name="{microscope}"').fetch(
                'magnification',order_by='change_date')[-1]
        logger.debug('Magnification: {}'.format(last_magnification))
        microscope_form.magnification_telescope.data = last_magnification
    except:
        logger.debug("did not update magnification")
        pass
    return render_template('microscope/status_monitor.html',
        microscope_form=microscope_form,microscope=microscope)

@microscope.route('/microscope/component_maintenance_selector/', methods=['GET','POST'])
@logged_in
def component_maintenance_selector():
    form = ComponentMaintenanceSelectForm()
  
    if form.validate_on_submit():
        component = form.component.data    
        return redirect(url_for('microscope.component_maintenance',component=component))
    return render_template('microscope/component_maintenance_selector.html',form=form)

@microscope.route('/microscope/component_maintenance/<component>', methods=['GET','POST'])
@logged_in
def component_maintenance(component):
    form = component_maintenance_form_picker(component)

    if component == 'laser':
        laser_serials = db_microscope.Laser().fetch('laser_serial')
        laser_serial_choices = [(laser_serial,laser_serial) for laser_serial in laser_serials]
        form.laser_serial.choices = laser_serial_choices
    if form.validate_on_submit():
        form_fields = [x for x in form._fields.keys() if 'submit' not in x and 'csrf_token' not in x]
        insert_dict = {field:form[field].data for field in form_fields}
        logger.info("form validated")
        db_table = component_maintenance_dbtable_picker(component)
        try:
            db_table().insert1(insert_dict)
            flash(f"Successfully added your entry into the database!",'success')
            return redirect(url_for('microscope.data_entry_selector'))

        except dj.errors.DuplicateError:
            ''' Figure out the primary key(s) and then report to the user 
            that the combination is already taken '''
            primary_key_list = db_table().primary_key
            primary_key_result_str =', '.join(f'{form[key].label.text} = {insert_dict[key]}' \
                for key in primary_key_list)

            flash(f"An entry already exists in the database with {primary_key_result_str}.\
                    Try again.",'danger')

    return render_template('microscope/component_maintenance.html',component=component,form=form)

# @microscope.route('/microscope/new_swap_entry', methods=['GET','POST'])
# @logged_in
# def objective_swap_log_entry():
#     form = NewSwapLogEntryForm()
#     if request.method == 'POST':
#         if form.validate_on_submit():
#             # enter form data into database
#             date = form.date.data
#             current_user = session['user']
#             logger.debug(f'{current_user} trying to make a microscope swap entry')
#             old_objective = form.old_objective.data
#             new_objective = form.new_objective.data
#             swapper = form.swapper.data
#             calibration = form.calibration.data
#             notes = form.notes.data
#             insert_dict = dict(date=date,username=current_user,old_objective=old_objective,
#                 new_objective=new_objective,swapper=swapper,calibration=calibration,notes=notes)

#             db.Microscope().insert1(insert_dict)
#             flash("Successfully added new entry to swap log","success")
#             return redirect(url_for('microscope.swap_calibrate_log'))
#         else:
#             logger.debug(form.date.errors)
#     return render_template('microscope/new_swap_log_entry.html',form=form,)

# @microscope.route('/microscope/swap_calibrate_log', methods=['GET'])
# @logged_in
# def swap_calibrate_log():
#     microscope_contents = db.Microscope()
#     sort = request.args.get('sort','entrynum') # first is the variable name, second is default value
#     reverse = (request.args.get('direction', 'asc') == 'desc')
#     # print("Reverse:",reverse)
#     sorted_results = sorted(microscope_contents.fetch(as_dict=True),
#         key=partial(table_sorter,sort_key=sort),reverse=reverse) # partial allows you to pass in a parameter to the function    
#     swap_calibrate_table = MicroscopeCalibrationTable(sorted_results,sort_by=sort,sort_reverse=reverse)
#     return render_template('microscope/objective_swap_log.html',microscope_contents=microscope_contents,table=swap_calibrate_table)

# @microscope.route('/microscope/<int:entrynum>/update_swap_entry', methods=['GET','POST'])
# @logged_in
# def update_entry(entrynum):
#     form = UpdateSwapLogEntryForm() 
#     microscope_contents = db.Microscope & f'entrynum = {entrynum}'

#     if form.validate_on_submit():
#         date = form.date.data
#         current_user = session['user']
#         old_objective = form.old_objective.data
#         new_objective = form.new_objective.data
#         swapper = form.swapper.data
#         calibration = form.calibration.data
#         notes = form.notes.data

#         update_insert_dict=dict(entrynum=entrynum,date=date,username=current_user,old_objective=old_objective,
#             new_objective=new_objective,swapper=swapper,calibration=calibration,notes=notes)
#         print(update_insert_dict)
#         microscope_contents.delete_quick()
#         db.Microscope().insert1(update_insert_dict)
#         flash(f"Successfully updated entry in swap log","success")
#         return redirect(url_for('microscope.swap_calibrate_log'))

#     date,old_objective,new_objective,swapper,calibration,notes = \
#             microscope_contents.fetch1('date','old_objective','new_objective','swapper','calibration','notes')
#     form.date.data = date
#     form.old_objective.data = old_objective
#     form.new_objective.data = new_objective
#     form.swapper.data = swapper
#     form.calibration.data = calibration
#     form.notes.data = notes
#     return render_template('microscope/update_swap_log_entry.html',form=form,entrynum=entrynum)

# @microscope.route("/microscope/<int:entrynum>/delete", methods=['POST'])
# @logged_in
# def delete_entry(entrynum):
#     assert session['user'] in ['ahoag','zmd']
#     microscope_contents = db.Microscope() & f'entrynum={entrynum}'
    
#     microscope_contents.delete_quick() # does not query user for confirmation like delete() does - that is handled in the form.
#     flash('Your entry has been deleted!', 'success')
#     return redirect(url_for('microscope.swap_calibrate_log'))