from flask import render_template, request, redirect, Blueprint
from lightserv.models import Experiment
from flask_login import current_user

main = Blueprint('main',__name__)

@main.route("/")
@main.route("/home")
def home():
	if current_user.is_authenticated:
		page = request.args.get('page',default=1,type=int)
		experiments = Experiment.query.order_by(
			Experiment.date_run.desc()).filter_by(
			author=current_user).paginate(page=page,per_page=5)
	else:
		# form = LoginForm()
		return redirect('login')
	return render_template('home.html',experiments=experiments)

@main.route("/about")
def about():
	return render_template('about.html', title='About')