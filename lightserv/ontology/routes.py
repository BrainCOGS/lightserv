from flask import render_template, request, redirect, Blueprint, session, url_for, flash, Markup
# from lightserv.models import Experiment
from lightserv import db
from lightserv.tables import ExpTable
import pandas as pd
from . import utils
from functools import partial

import numpy as np
import graphviz 
# from lightserv.experiments.routes import experiments

ontology = Blueprint('ontology',__name__)

@ontology.route("/test_graph_alt")
def test_graph_alt():
	G = graphviz.Digraph(format='svg')
	G.edge('Hello','World')
	G_output = G.pipe().decode("utf-8")
	G_output = Markup(G_output)

	return render_template('test_graph_alt.html', graph_output=G_output)

@ontology.route("/test_graph_link")
def test_graph_link():
	G = graphviz.Digraph(format='svg')
	A = G.node('Hello',href='http://www.google.com')
	# A = G.node('Hello', label='''<a href="www.google.com">Does this work</a>''')
	B = G.node('World')
	G.edge('Hello','World')
	print(G)
	G_output = G.pipe().decode("utf-8")
	G_output = Markup(G_output)

	return render_template('test_graph_alt.html', graph_output=G_output)

@ontology.route("/test_ontology_int")
def test_ontology_int():
	# G = graphviz.Digraph(format='svg')
	nodename = request.args.get('nodename') # The node name which was clicked whose children you want to display
	G = utils.expand_graph(input_nodename=nodename)
	# G = graphviz.Digraph(format='svg')
	# G.node('root')
	# A = G.node('root',href='http://www.google.com')
	# # A = G.node('Hello', label='''<a href="www.google.com">Does this work</a>''')
	# B = G.node('World')
	# G.edge('Hello','World')
	# print(G)
	G.attr(rankdir='LR')
	G_output = G.pipe().decode("utf-8")
	G_output = Markup(G_output)

	return render_template('test_graph_alt.html', graph_output=G_output)
