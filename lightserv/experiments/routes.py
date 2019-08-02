from flask import (render_template, url_for, flash,
				   redirect, request, abort, Blueprint)
from flask_login import current_user, login_required
from lightserv import db
from lightserv.models import Experiment
from lightserv.experiments.forms import ExpForm

import secrets

experiments = Blueprint('experiments',__name__)

@experiments.route("/exp/new",methods=['GET','POST'])
@login_required
def new_exp():
	form = ExpForm()
	if form.validate_on_submit():
		''' Create a new entry in the Experiment table.
		First create a dataset hex 
		'''
		dataset_hex=secrets.token_hex(5)
		exp = Experiment(dataset_hex=dataset_hex,title=form.title.data,
		 description=form.description.data,species=form.species.data,clearing_protocol=form.clearing_protocol.data,
		 fluorophores=form.fluorophores.data,primary_antibody=form.primary_antibody.data,
		 secondary_antibody=form.secondary_antibody.data,image_resolution=form.image_resolution.data,
		 cell_detection=form.cell_detection.data,registration=form.registration.data,
		 probe_detection=form.probe_detection.data,injection_detection=form.injection_detection.data,
		 author=current_user) # uses the author backref
		db.session.add(exp)
		db.session.commit()
		flash('Your data set is being processed!\nYou will receive an email when it is finished','success')
		return redirect(url_for('main.home'))

	return render_template('create_exp.html', title='new_experiment',
		form=form,legend='New Request')	

@experiments.route("/exp/<string:dataset_hex>",)
def exp(dataset_hex):
	exp = Experiment.query.filter_by(dataset_hex=dataset_hex).first() # give me the dataset with this hex string
	try:
		if exp.author != current_user:
			flash('You do not have permission to see dataset: {}'.format(dataset_hex),'danger')
			return redirect(url_for('main.home'))
	except:
		flash('Page does not exist for Dataset: {}'.format(dataset_hex[0:50]),'danger')
		return redirect(url_for('main.home'))
	return render_template('exp.html',title=exp.title,exp=exp)
