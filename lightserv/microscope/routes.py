from flask import Blueprint, redirect, render_template, url_for, flash

import os
from datetime import datetime
from lightserv.microscope.forms import NewSwapLogEntryForm
from lightserv import db

microscope = Blueprint('microscope',__name__)

@microscope.route('/microscope/new_swap_entry', methods=['GET','POST'])
def new_swap_entry():
    form = NewSwapLogEntryForm()

    if form.validate_on_submit():
        # enter form data into database
        date = datetime.strptime(form.date.data,'%Y-%m-%d').strftime('%Y-%m-%d')
        old_objective = form.old_objective.data
        new_objective = form.new_objective.data
        swapper = form.swapper.data
        calibration = form.calibration.data
        notes = form.notes.data
        insert_dict = dict(date=date,old_objective=old_objective,
            new_objective=new_objective,swapper=swapper,calibration=calibration,notes=notes)
        db.Microscope().insert1(insert_dict)
        flash("Successfully added new entry to swap log","success")
        return redirect(url_for('main.home'))
    return render_template('new_swap_log_entry.html',form=form)