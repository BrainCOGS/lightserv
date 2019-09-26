from flask import (render_template, url_for, flash,
				   redirect, request, abort, Blueprint,session,
				   Markup)
# from flask_login import current_user, login_required
# from lightserv import db
# from lightserv.models import Experiment
from lightserv.clearing.forms import (iDiscoPlusImmunoForm, iDiscoAbbreviatedForm,
									  uDiscoForm, iDiscoPlusForm, iDiscoEduForm )
from lightserv.tables import ClearingTable
from lightserv import db
from .utils import determine_clearing_form
# import cloudvolume
import numpy as np
import datajoint as dj

clearing = Blueprint('clearing',__name__)

@clearing.route("/clearing/<experiment_id>",methods=['GET','POST'])
def update_clearing(experiment_id):
	exp_contents = db.Experiment() & f'experiment_id="{experiment_id}"'
	clearing_table = ClearingTable(exp_contents)
	# clearing_contents = db.Clearing() & f'experiment_id="{experiment_id}"'
	# if len(clearing_contents) == 0:
	# 	return render_template('new_clearing.html',form=form)
	# clearing_table = ClearingTable(clearing_contents)
	clearing_protocol = exp_contents.fetch1('clearing_protocol')
	form = determine_clearing_form(clearing_protocol)
	''' If clearing entry exists for this exp in db already, 
	then populate with what we have '''
	# if len(clearing_contents) > 0:
	# 	form.notes.data = clearing_contents.fetch1('clearing_notes')

	return render_template('clearing.html',form=form,clearing_table=clearing_table,clearing_protocol=clearing_protocol,experiment_id=experiment_id)


@clearing.route("/clearing/idiscoplus_entry/<experiment_id>",methods=['GET','POST'])
def make_iDISCOplus_entry(experiment_id): 
	from wtforms.fields.html5 import DateField
	exp_contents = db.Experiment() & f'experiment_id="{experiment_id}"'
	assert exp_contents, f"experiment_id={experiment_id} does not exist.\
						   It must exist before the clearing for this experiment can be done"
	clearing_table = ClearingTable(exp_contents)
	clearing_protocol = exp_contents.fetch1('clearing_protocol')
	form = determine_clearing_form(clearing_protocol,existing_form=request.form)

	''' Check to see if there is an entry in the db yet. If not create one with all NULL values.
	They will get updated as the user fills out the form '''
	clearing_contents = db.IdiscoPlusClearing() & f'experiment_id="{experiment_id}"'
	if not clearing_contents:
		experiment_username = exp_contents.fetch1('username')
		insert_dict = {'experiment_id':experiment_id,
						'username':experiment_username,'clearer':session['user']}
		db.IdiscoPlusClearing().insert1(insert_dict)
		print("Created clearing database entry")

	''' Handle user's post requests '''
	if request.method == 'POST':
		submit_keys = [x for x in form._fields.keys() if 'submit' in x]
		for key in submit_keys:
			if form[key].data:
				if key == 'submit': # The final submit button
					print("Submitting entire form")
				else: 
					''' Update the row '''
					column_name = key.rstrip('_submit')
					clearing_entry_dict = clearing_contents.fetch1() # returns as a dict
					clearing_entry_dict[column_name]=form[column_name].data
					clearing_contents.delete_quick()
					db.IdiscoPlusClearing().insert1(clearing_entry_dict)
					print(f"updated row for value: {column_name}")


	return render_template('clearing/idiscoplus.html',form=form,clearing_table=clearing_table,experiment_id=experiment_id)
