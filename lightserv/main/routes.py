from flask import render_template, request, redirect, Blueprint, session, url_for
# from lightserv.models import Experiment
from lightserv import db
from lightserv.tables import ExpTable
import pandas as pd
from . import utils
from functools import partial
# from lightserv.experiments.routes import experiments

main = Blueprint('main',__name__)
@main.route("/")
@main.route("/home")
def home():
    if 'user' in session:
        # Get table of experiments by current user
        username = session['user']
        print(username)
        exp_contents = db.Experiment() & f'username="{username}"'
        # print(exp_contents)
        sort = request.args.get('sort', 'experiment_id') # first is the variable name, second is default value
        reverse = (request.args.get('direction', 'asc') == 'desc')

        sorted_results = sorted(exp_contents.fetch(as_dict=True),
            key=partial(utils.table_sorter,sort_key=sort),reverse=reverse)
        # sorted_results = sorted(exp_contents.fetch(as_dict=True),
        #     key=lambda dic:dic[sort].lower(),reverse=reverse)

        table = ExpTable(sorted_results,sort_by=sort,
                          sort_reverse=reverse)

    else:
        return redirect(url_for('users.login'))
    return render_template('home.html',exp_table=table,)


@main.route('/demosort')
def demosort():
    sort = request.args.get('sort', 'id')
    reverse = (request.args.get('direction', 'asc') == 'desc')
    table = SortableTable(Item.get_sorted_by(sort, reverse),
                          sort_by=sort,
                          sort_reverse=reverse)
    return table.__html__()

class Item(object):
    """ a little fake database """
    def __init__(self, id, name, description):
        self.id = id
        self.name = name
        self.description = description

    @classmethod
    def get_elements(cls):
        return [
            Item(1, 'Z', 'zzzzz'),
            Item(2, 'K', 'aaaaa'),
            Item(3, 'B', 'bbbbb')]

    @classmethod
    def get_sorted_by(cls, sort, reverse=False):
        return sorted(
            cls.get_elements(),
            key=lambda x: getattr(x, sort),
            reverse=reverse)

    @classmethod
    def get_element_by_id(cls, id):
        return [i for i in cls.get_elements() if i.id == id][0]
        
# @main.route("/home")
# def home():
#   if current_user.is_authenticated:
#       page = request.args.get('page',default=1,type=int)
#       experiments = Experiment.query.order_by(
#           Experiment.date_run.desc()).filter_by(
#           author=current_user).paginate(page=page,per_page=5)
#   else:
#       return redirect('login')
#   return render_template('home.html',experiments=experiments)

