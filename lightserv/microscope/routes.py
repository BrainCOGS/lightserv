from flask import Blueprint, redirect, render_template, url_for, flash, request, session
from functools import partial

import os
from datetime import datetime
from lightserv.microscope.forms import NewSwapLogEntryForm, UpdateSwapLogEntryForm
from lightserv import db
from lightserv.tables import MicroscopeCalibrationTable
from lightserv.main.utils import table_sorter

microscope = Blueprint('microscope',__name__)

@microscope.route('/microscope/new_swap_entry', methods=['GET','POST'])
def objective_swap_log_entry():
    form = NewSwapLogEntryForm()
    if form.validate_on_submit():
        # enter form data into database
        date = datetime.strptime(form.date.data,'%Y-%m-%d').strftime('%Y-%m-%d')
        username = session['user']
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
    return render_template('microscope/new_swap_log_entry.html',form=form,)

@microscope.route('/microscope/swap_calibrate_log', methods=['GET'])
def swap_calibrate_log():
    microscope_contents = db.Microscope()
    sort = request.args.get('sort','date') # first is the variable name, second is default value
    reverse = (request.args.get('direction', 'asc') == 'desc')
    sorted_results = sorted(microscope_contents.fetch(as_dict=True),
        key=partial(table_sorter,sort_key=sort),reverse=reverse) # partial allows you to pass in a parameter to the function    
    swap_calibrate_table = MicroscopeCalibrationTable(microscope_contents,sort_by=sort,sort_reverse=reverse)
    return render_template('microscope/objective_swap_log.html',table=swap_calibrate_table)


@microscope.route('/microscope/<int:entrynum>/update_swap_entry', methods=['GET','POST'])
def update_entry(entrynum):
    form = UpdateSwapLogEntryForm() 
    microscope_contents = db.Microscope & f'entrynum = {entrynum}'


    if form.validate_on_submit():
        date = datetime.strptime(form.date.data,'%Y-%m-%d').strftime('%Y-%m-%d')
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
def delete_entry(entrynum):
    assert session['user'] in ['ahoag','zmd']
    microscope_contents = db.Microscope() & f'entrynum={entrynum}'
    
    microscope_contents.delete_quick() # does not query user for confirmation like delete() does - that is handled in the form.
    flash('Your entry has been deleted!', 'success')
    return redirect(url_for('microscope.swap_calibrate_log'))