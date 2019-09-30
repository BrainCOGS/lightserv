from flask import render_template, request, redirect, Blueprint, session, url_for, flash, Markup
# from lightserv.models import Experiment
from lightserv import db
from lightserv.tables import ExpTable
import pandas as pd
from . import utils
from functools import partial


import numpy as np
import graphviz 
import tifffile as tif
from multiprocessing import Pool #  Process pool
from multiprocessing import sharedctypes

from lightserv.ontology.forms import OntologySubmitForm

# from lightserv.experiments.routes import experiments

annotation_file = '/jukebox/LightSheetTransfer/atlas/allen_atlas/annotation_2017_25um_sagittal_forDVscans_16bit.tif'
# annotation_file = '/Users/athair/graphviz/annotation_2017_25um_sagittal_forDVscans_16bit.tif'

ontology = Blueprint('ontology',__name__)

@ontology.route("/interactive_ontology",methods=['POST','GET'])
def interactive_ontology():
	nodename = request.args.get('input_nodename',None) # The node name which was clicked whose children you want to display
	contract = request.args.get('contract',False) 
	if contract:
		G = utils.contract_graph(input_nodename=nodename)
	else:
		G = utils.expand_graph(input_nodename=nodename)

	G.attr(rankdir='LR')
	G_output = G.pipe().decode("utf-8")
	G_output = Markup(G_output)
	if nodename:
		section = 'a_{}'.format('_'.join(nodename.split(' ')))
	else:
		section = None
	print(section)
	form = OntologySubmitForm()
	if form.validate_on_submit():
		G = utils.my_graph
		reassignment_dict = {}
		utils.make_ID_reassignment_dict(ontology_dict=utils.ontology_dict,graph=G,output_dict=reassignment_dict)
		chunked_list_of_tuples = utils.make_tuple_input(ID_reassignment_dict=reassignment_dict,chunk_size=5)
		global X
		X = tif.imread(annotation_file)
		print("read in annotation volume")
		result = np.ctypeslib.as_ctypes(X)
		global shared_array
		shared_array = sharedctypes.RawArray(result._type_, result)
		with Pool() as p:
		    res = p.map(ID_reassignment_parallel,chunked_list_of_tuples)
		    result = np.ctypeslib.as_array(shared_array)


	return render_template('ontology/interactive_graph.html', graph_output=G_output, form=form,section=section)

def ID_reassignment_parallel(list_of_tuples):
    '''
    ---PURPOSE---
    Convert integer values in image from one value to another.
    Updates img in place
    ---INPUT---
    list_of_tuples, like: [(input_val_1,target_val_1),(input_val_2,target_val_2),...], where:
        input_val        The value of the int you want to convert 
        target_val       The value you want input_val to be converted to
    '''
    tmp = np.ctypeslib.as_array(shared_array)
    for tup in list_of_tuples:
        target_val,input_val = tup
        mask = (X == input_val)
        tmp[mask] = target_val