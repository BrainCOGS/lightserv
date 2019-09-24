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
