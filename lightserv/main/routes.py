from flask import render_template, request, redirect, Blueprint, session, url_for
# from lightserv.models import Experiment
from lightserv.schemata import db
from lightserv.tables import ExpTable
from lightserv.experiments.routes import experiments

main = Blueprint('main',__name__)

@main.route("/")
@main.route("/home")
def home():
	if 'user' in session:
		# Get table of experiments by current user
		username = session['user']
		exp_contents = db.Experiment() & f'username="{username}"'
		# print(exp_contents)
		exp_table = ExpTable(exp_contents)
		# page = request.args.get('page',default=1,type=int)
		# experiments = Experiment.query.order_by(
		# 	Experiment.date_run.desc()).filter_by(
		# 	author=current_user).paginate(page=page,per_page=5)
	else:
		return redirect(url_for('users.login'))
	return render_template('home.html',exp_table=exp_table)
# @main.route("/home")
# def home():
# 	if current_user.is_authenticated:
# 		page = request.args.get('page',default=1,type=int)
# 		experiments = Experiment.query.order_by(
# 			Experiment.date_run.desc()).filter_by(
# 			author=current_user).paginate(page=page,per_page=5)
# 	else:
# 		return redirect('login')
# 	return render_template('home.html',experiments=experiments)

