from flask import Blueprint, redirect, render_template, url_for, flash, request, session
from functools import partial

import os
from datetime import datetime
from lightserv.microscope.forms import (NewSwapLogEntryForm, UpdateSwapLogEntryForm,
                                        StatusMonitorSelectForm, LightSheetStatusForm)
from lightserv import db
from lightserv.tables import MicroscopeCalibrationTable
from lightserv.main.utils import table_sorter,logged_in
from lightserv.microscope.utils import microscope_form_picker
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

@microscope.route('/microscope/status_monitor_picker', methods=['GET','POST'])
@logged_in
def status_monitor_picker():
    selectform = StatusMonitorSelectForm()
    microscope = 'light sheet microscope' # default
    microscope_form = LightSheetStatusForm() # default

    if selectform.validate_on_submit():
        microscope = selectform.microscope.data
        return redirect(url_for('microscope.status_monitor',microscope=microscope))
    return render_template('microscope/status_monitor_picker.html',selectform=selectform,
        microscope_form=microscope_form,microscope=microscope)

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
            username = session['user']
            logger.debug(f'{username} trying to make a microscope swap entry')
            old_objective = form.old_objective.data
            new_objective = form.new_objective.data
            swapper = form.swapper.data
            calibration = form.calibration.data
            notes = form.notes.data
            insert_dict = dict(date=date,username=username,old_objective=old_objective,
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
        username = session['user']
        old_objective = form.old_objective.data
        new_objective = form.new_objective.data
        swapper = form.swapper.data
        calibration = form.calibration.data
        notes = form.notes.data

        update_insert_dict=dict(entrynum=entrynum,date=date,username=username,old_objective=old_objective,
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