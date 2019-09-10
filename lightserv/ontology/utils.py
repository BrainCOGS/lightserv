import pkg_resources
import json

from flask import url_for

import graphviz

DATA_PATH = pkg_resources.resource_filename('lightserv', 'data') # package name first then subdirectory next

test_ontology_file = DATA_PATH + '/test_ontology.json'
with open(test_ontology_file) as json_file:
    test_ontology_dict = json.load(json_file)

ontology_file = DATA_PATH + '/allen_ontology.json'
with open(ontology_file) as json_file:
    ontology_dict = json.load(json_file)

my_test_graph = graphviz.Digraph(format='svg',strict=True)
my_test_graph.attr('node',shape='box')

my_graph = graphviz.Digraph(format='svg',strict=True) # strict means you cant have more than 1 edge between nodes
my_graph.attr('node',shape='box')

table_border = 0
contract_cell_border=1
root_body_str = f'\troot [label=<<TABLE BORDER="{0}">\
<TR>\
<TD href="/interactive_ontology?input_nodename=root">root</TD>\
<TD BORDER="{1}" href="/interactive_ontology?input_nodename=root&amp;contract=True">-</TD>\
</TR></TABLE>>]'.format(table_border,contract_cell_border)

def expand_graph(dic=ontology_dict,graph=my_graph,input_nodename='root'):
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
    if input_nodename == None and root_body_str not in graph.body: # second check is so that I don't keep remaking the root node
#         print("here")
        href_expand = '/interactive_ontology?input_nodename=root'
        href_contract = '/interactive_ontology?input_nodename=root&amp;contract=True'
        graph.node('root',label='''<<TABLE BORDER="{0}"><TR><TD href="{1}">root</TD>\
<TD BORDER="{2}" href="{3}">-</TD></TR></TABLE>>'''\
            .format(table_border,href_expand,contract_cell_border,href_contract))
    if name == input_nodename:
        for child in children: # child is a dict
            child_name = child.get('name')
            href_expand = '/interactive_ontology?input_nodename={}'.format(child_name)
            href_contract = '/interactive_ontology?input_nodename={}&amp;contract=True'.format(child_name)
            graph.node(child_name,label='''<<TABLE BORDER="{0}"><TR><TD href="{1}">{2}</TD>\
<TD BORDER="{3}" href="{4}">-</TD></TR></TABLE>>'''\
                       .format(table_border,href_expand,child_name,contract_cell_border,href_contract))
            graph.edge(name,child_name)
        return graph
     
    for child in children:
        expand_graph(child,graph,input_nodename=input_nodename)
    return graph

def contract_graph(dic=ontology_dict,graph=my_graph,input_nodename='root'):
    """ 
    ---PURPOSE---
    Take an existing graph and remove all descendents
    of an input_nodename. Recursive function.
    ---INPUT---
    dic             Dictionary representing the entire ontology graph (with "rank" key included)
    graph           The graphviz graph object that will be updated.
                    graph may be a subgraph of the entire graph as long as 
                    input_nodename is a node name in it
    input_nodename  The name of the node whose descendents you want to remove
    """
    name = dic.get('name')
    name_label = f'"{name}"' if len(name.split())>1 else name
    children = dic.get('children')
    if name == input_nodename:
        for child in children: # child is a dict
            child_name = child.get('name')
            child_label = f'"{child_name}"' if len(child_name.split())>1 else child_name
            edge_str = f'\t{name_label} -> {child_label}' 
#             print(edge_st/r)
            child_body_str = '\t{0} [label=<<TABLE BORDER="{1}"><TR><TD href="/interactive_ontology?input_nodename={2}">{2}</TD>\
<TD BORDER="{3}" href="/interactive_ontology?input_nodename={2}&amp;contract=True">-</TD></TR></TABLE>>]'.format(child_label,table_border,child_name,contract_cell_border)

            if edge_str in graph.body:
                del graph.body[graph.body.index(edge_str)]
                del graph.body[graph.body.index(child_body_str)]
                contract_graph(child,graph,input_nodename=child_name)
    for child in children:
        contract_graph(child,graph,input_nodename=input_nodename)
    return graph

# def contract_graph(dic=ontology_dict,graph=my_graph,input_nodename='root'):
#     """ 
#     ---PURPOSE---
#     Take an existing graph and remove all descendents
#     of an input_nodename. Recursive function.
#     ---INPUT---
#     dic             Dictionary representing the entire ontology graph (with "rank" key included)
#     graph           The graphviz graph object that will be updated.
#                     graph may be a subgraph of the entire graph as long as 
#                     input_nodename is a node name in it
#     input_nodename  The name of the node whose descendents you want to remove
#     """
#     name = dic.get('name')
#     name_label = f'"{name}"' if len(name.split())>1 else name
#     children = dic.get('children')
#     if name == input_nodename:
#         for child in children: # child is a dict
#             child_name = child.get('name')
#             child_label = f'"{child_name}"' if len(child_name.split())>1 else child_name

#             edge_str = f'\t{name_label} -> {child_label}' 
# #             print(edge_st/r)
#             # delete edges to children and children themselves
#             child_str = f'''\t{child_label}'
#             '''<<TABLE><TR><TD href="{}">root</TD><TD href="{}">-</TD></TR></TABLE>>'''
#             del graph.body[graph.body.index(edge_str)]
#             del graph.body[graph.body.index(child_str)]
#             # print("deleted %s" % child_str)
#             # print("deleting %s" % edge_str)
#             contract_graph(child,graph,input_nodename=child_name)
#     for child in children:
#         contract_graph(child,graph,input_nodename=input_nodename)
#     return graph