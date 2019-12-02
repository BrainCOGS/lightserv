from flask import (Blueprint, redirect, render_template,
                     url_for, flash, request, session,jsonify)
from functools import partial
import datajoint as dj
import os
from datetime import datetime
from lightserv.microscope.forms import (NewSwapLogEntryForm, UpdateSwapLogEntryForm,
                                        StatusMonitorSelectForm,MicroscopeActionSelectForm,
                                        DataEntrySelectForm)
from lightserv import db_lightsheet, db_microscope
from lightserv.microscope.tables import MicroscopeCalibrationTable
from lightserv.main.utils import table_sorter,logged_in
from lightserv.microscope.utils import (microscope_form_picker,
      data_entry_form_picker, data_entry_dbtable_picker)
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
        elif action == 'microscope_maintenance':
            return redirect(url_for('microscope.status_monitor_picker'))
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
        print("submitted form")
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
    microscope_form.status.choices = [('good','good'),('bad','bad'),('replace','replace')]
    return render_template('microscope/status_monitor.html',
        microscope_form=microscope_form,microscope=microscope)

@microscope.route('/microscope/new_swap_entry', methods=['GET','POST'])
@logged_in
def objective_swap_log_entry():
    form = NewSwapLogEntryForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            # enter form data into database
            date = form.date.data
            current_user = session['user']
            logger.debug(f'{current_user} trying to make a microscope swap entry')
            old_objective = form.old_objective.data
            new_objective = form.new_objective.data
            swapper = form.swapper.data
            calibration = form.calibration.data
            notes = form.notes.data
            insert_dict = dict(date=date,username=current_user,old_objective=old_objective,
                new_objective=new_objective,swapper=swapper,calibration=calibration,notes=notes)

            db.Microscope().insert1(insert_dict)
            flash("Successfully added new entry to swap log","success")
            return redirect(url_for('microscope.swap_calibrate_log'))
        else:
            logger.debug(form.date.errors)
    return render_template('microscope/new_swap_log_entry.html',form=form,)

@microscope.route('/microscope/swap_calibrate_log', methods=['GET'])
@logged_in
def swap_calibrate_log():
    microscope_contents = db.Microscope()
    sort = request.args.get('sort','entrynum') # first is the variable name, second is default value
    reverse = (request.args.get('direction', 'asc') == 'desc')
    # print("Reverse:",reverse)
    sorted_results = sorted(microscope_contents.fetch(as_dict=True),
        key=partial(table_sorter,sort_key=sort),reverse=reverse) # partial allows you to pass in a parameter to the function    
    swap_calibrate_table = MicroscopeCalibrationTable(sorted_results,sort_by=sort,sort_reverse=reverse)
    return render_template('microscope/objective_swap_log.html',microscope_contents=microscope_contents,table=swap_calibrate_table)

@microscope.route('/microscope/<int:entrynum>/update_swap_entry', methods=['GET','POST'])
@logged_in
def update_entry(entrynum):
    form = UpdateSwapLogEntryForm() 
    microscope_contents = db.Microscope & f'entrynum = {entrynum}'

    if form.validate_on_submit():
        date = form.date.data
        current_user = session['user']
        old_objective = form.old_objective.data
        new_objective = form.new_objective.data
        swapper = form.swapper.data
        calibration = form.calibration.data
        notes = form.notes.data

        update_insert_dict=dict(entrynum=entrynum,date=date,username=current_user,old_objective=old_objective,
            new_objective=new_objective,swapper=swapper,calibration=calibration,notes=notes)
        print(update_insert_dict)
        microscope_contents.delete_quick()
        db.Microscope().insert1(update_insert_dict)
        flash(f"Successfully updated entry in swap log","success")
        return redirect(url_for('microscope.swap_calibrate_log'))

    date,old_objective,new_objective,swapper,calibration,notes = \
            microscope_contents.fetch1('date','old_objective','new_objective','swapper','calibration','notes')
    form.date.data = date
    form.old_objective.data = old_objective
    form.new_objective.data = new_objective
    form.swapper.data = swapper
    form.calibration.data = calibration
    form.notes.data = notes
    return render_template('microscope/update_swap_log_entry.html',form=form,entrynum=entrynum)

@microscope.route("/microscope/<int:entrynum>/delete", methods=['POST'])
@logged_in
def delete_entry(entrynum):
    assert session['user'] in ['ahoag','zmd']
    microscope_contents = db.Microscope() & f'entrynum={entrynum}'
    
    microscope_contents.delete_quick() # does not query user for confirmation like delete() does - that is handled in the form.
    flash('Your entry has been deleted!', 'success')
    return redirect(url_for('microscope.swap_calibrate_log'))