from flask import render_template, request, redirect, Blueprint, session, url_for, flash, Markup
# from lightserv.models import Experiment
from lightserv import db
from lightserv.tables import ExpTable
import pandas as pd
from . import utils
from functools import partial

import numpy as np
import graphviz 

from lightserv.ontology.forms import OntologySubmitForm

# from lightserv.experiments.routes import experiments

ontology = Blueprint('ontology',__name__)

@ontology.route("/interactive_ontology",methods=['POST','GET'])
def interactive_ontology():
	nodename = request.args.get('input_nodename',None) # The node name which was clicked whose children you want to display
	contract = request.args.get('contract',False) 
	form = OntologySubmitForm()
	if form.validate_on_submit():
		G = utils.my_graph
		print(G.body)
		return redirect(url_for('main.home'))
	if contract:
		G = utils.contract_graph(input_nodename=nodename)
	else:
		G = utils.expand_graph(input_nodename=nodename)

	G.attr(rankdir='LR')
	G_output = G.pipe().decode("utf-8")
	G_output = Markup(G_output)

	return render_template('interactive_graph.html', graph_output=G_output, form=form)
