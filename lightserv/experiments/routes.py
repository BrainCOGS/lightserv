from flask import (render_template, url_for, flash,
				   redirect, request, abort, Blueprint,session,
				   Markup)
# from flask_login import current_user, login_required
# from lightserv import db
# from lightserv.models import Experiment
from lightserv.experiments.forms import ExpForm, UpdateNotesForm
from lightserv.tables import ExpTable
from lightserv import db

import secrets

import neuroglancer
# import cloudvolume
import numpy as np

neuroglancer.set_static_content_source(url='https://neuromancer-seung-import.appspot.com')

experiments = Blueprint('experiments',__name__)

@experiments.route("/exp/new",methods=['GET','POST'])
def new_exp():
	if 'user' not in session:
		return redirect('users.login')
	form = ExpForm()
	if form.validate_on_submit():
		''' Create a new entry in the Experiment table based on form input.
		'''
		# dataset_hex=secrets.token_hex(5)
		exp_dict = dict(title=form.title.data,
		 description=form.description.data,species=form.species.data,clearing_protocol=form.clearing_protocol.data,
		 fluorophores=form.fluorophores.data,primary_antibody=form.primary_antibody.data,
		 secondary_antibody=form.secondary_antibody.data,image_resolution=form.image_resolution.data,
		 cell_detection=form.cell_detection.data,registration=form.registration.data,
		 probe_detection=form.probe_detection.data,injection_detection=form.injection_detection.data,
		 username=session['user']) 
		db.Experiment().insert1(exp_dict)
		# db.session.add(exp)
		# db.session.commit()
		exp_id = db.Experiment().fetch("KEY")[-1]['experiment_id'] # gets the most recently added key
		# print(url_for(experiments.exp))
		flash(Markup(f'Your experiment has started!\nCheck your new experiment page: <a href="{url_for("experiments.exp",experiment_id=exp_id)}" class="alert-link" target="_blank">here</a> for your data when it becomes available.'),'success')
		# flash(f'Your experiment has started!\nCheck your new experiment page (Experiment_ID={exp_id}) for your data when it becomes available.','success')
		return redirect(url_for('main.home'))

	return render_template('create_exp.html', title='new_experiment',
		form=form,legend='New Request')	

@experiments.route("/exp/<int:experiment_id>/delete", methods=['POST'])
def delete_exp(experiment_id):
	# post = Post.query.get_or_404(post_id)
	exp_contents = db.Experiment() & f'experiment_id="{experiment_id}"'

	if exp_contents.fetch1('username') != session['user']:
		abort(403)

	exp_contents.delete_quick() # does not query user for confirmation like delete() does - that is handled in the form.
	flash('Your experiment has been deleted!', 'success')
	return redirect(url_for('main.home'))

@experiments.route("/exp/<int:experiment_id>",)
def exp(experiment_id):
	# exp = Experiment.query.filter_by(dataset_hex=dataset_hex).first() # give me the dataset with this hex string
	exp_contents = db.Experiment() & f'experiment_id="{experiment_id}"'
	exp_table = ExpTable(exp_contents)

	try:
		if exp_contents.fetch1('username') != session['user']:
			flash('You do not have permission to see dataset: {}'.format(experiment_id),'danger')
			return redirect(url_for('main.home'))
	except:
		flash(f'Page does not exist for Dataset: "{experiment_id}"','danger')
		return redirect(url_for('main.home'))
	return render_template('exp.html',exp_contents=exp_contents,exp_table=exp_table)

@experiments.route("/exp/<int:experiment_id>/notes", methods=['GET','POST'])
def update_notes(experiment_id):
	# exp_contents = db.Experiment() & f'experiment_id="{experiment_id}"'
	if 'user' not in session:
		return redirect('users.login')
	form = UpdateNotesForm()
	exp_contents = db.Experiment() & f'experiment_id="{experiment_id}"'
	exp_table = ExpTable(exp_contents)

	if form.validate_on_submit():
		''' Enter the entered notes into this experiment's notes column'''
		''' To update entry, need to first delete the entry and then add it 
		again with the additional data '''

		update_insert_dict = exp_contents.fetch1()
		update_insert_dict['notes']=form.notes.data
		exp_contents.delete_quick()

		db.Experiment().insert1(update_insert_dict)
		flash(f"Your notes have been updated",'success')
		# flash(Markup(f'Your experiment has started!\nCheck your new experiment page: <a href="{url_for("experiments.exp",experiment_id=exp_id)}" class="alert-link" target="_blank">here</a> for your data when it becomes available.'),'success')
		return redirect(url_for('experiments.exp',experiment_id=experiment_id))
	elif request.method == 'GET':
		current_notes = exp_contents.fetch1('notes')
		form.notes.data = current_notes
	return render_template('update_notes.html',form=form,exp_table=exp_table)

@experiments.route("/exp/<int:experiment_id>/rawdata_link",)
def exp_rawdata(experiment_id):
	# exp = Experiment.query.filter_by(dataset_hex=dataset_hex).first() # give me the dataset with this hex string
	# Generate the neuroglancer viewer string and display it to the screen 
	try: 
		vol = cloudvolume.CloudVolume('file:///home/ahoag/ngdemo/demo_bucket/demo_dataset/190715_an31_devcno_03082019_1d3x_488_017na_1hfds_z10um_100msec_16-55-48/')
		# vol = cloudvolume.CloudVolume('file:///home/ahoag/ngdemo/demo_bucket/demo_dataset/demo_layer_singletif/')
		image_data = np.transpose(vol[:][...,0],(2,1,0)) # can take a few seconds
		viewer = neuroglancer.Viewer()
		# This volume handle can be used to notify the viewer that the data has changed.
		volume = neuroglancer.LocalVolume(
				 data=image_data, # need it in z,y,x order, strangely
				 voxel_size=[40000,40000,40000],
				 voxel_offset = [0, 0, 1], # x,y,z in nm not voxels
				 volume_type='image'
				 )
		with viewer.txn() as s:
			s.layers['image'] = neuroglancer.ImageLayer(source=volume,
			shader = '''
void main() {
float v = toNormalized(getDataValue(0)) * 20.0;
emitRGBA(vec4(v, 0.0, 0.0, v));
		}
		''')
	
	except:
		flash('Something went wrong making viewer','danger')
		return redirect(url_for('experiments.exp',experiment_id=experiment_id))
	return render_template('datalink.html',viewer=viewer)
