import pkg_resources
import json

from flask import url_for

import graphviz

DATA_PATH = pkg_resources.resource_filename('lightserv', 'data') # package name first then subdirectory next

test_ontology_file = DATA_PATH + '/test_ontology.json'
with open(test_ontology_file) as json_file:
    test_ontology_dict = json.load(json_file)

mygraph = graphviz.Digraph(format='svg')
mygraph.attr('node',shape='box')

def expand_graph(dic=test_ontology_dict,graph=mygraph,input_nodename='root'):
    """ 
    ---PURPOSE---
    Take an existing graph and add to it the children 
    of an input_nodename. Recursive function.
    ---INPUT---
    dic             Dictionary representing the entire ontology graph (with "rank" key included)
    graph           The graphviz graph object that will be updated.
                    graph may be a subgraph of the entire graph as long as 
                    input_nodename is a node name in it
    input_nodename  The name of the node whose children you want to display
    """

    name = dic.get('name')
    children = dic.get('children')
    if input_nodename == None: # default is root
        graph.node('root',href=url_for('ontology.test_ontology_int',nodename='root'))
    if name == input_nodename:
        for child in children: # child is a dict
            child_name = child.get('name')
            # graph.node(name,href=url_for('ontology.test_ontology_int',nodename=name))
            graph.node(child_name,href=url_for('ontology.test_ontology_int',nodename=child_name))
            graph.edge(name,child_name)
        return graph
     
    for child in children:
        expand_graph(child,graph,input_nodename=input_nodename)
    return graph