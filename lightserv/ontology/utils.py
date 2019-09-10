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
root_body_str = '\troot [label=<<TABLE><TR><TD href="/interactive_ontology?input_nodename=root">root</TD><TD href="/interactive_ontology?input_nodename=root&amp;contract=True">-</TD></TR></TABLE>>]'


def test_expand_graph(dic=test_ontology_dict,graph=my_test_graph,input_nodename='root'):
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
            # body_str = '\t'
            # graph.node(name,href=url_for('ontology.test_ontology_int',nodename=name))
            graph.node(child_name,href=url_for('ontology.test_ontology_int',nodename=child_name))
            graph.edge(name,child_name)
        return graph
     
    for child in children:
        test_expand_graph(child,graph,input_nodename=input_nodename)
    return graph

# def expand_graph(dic=ontology_dict,graph=my_graph,input_nodename='root'):
#     """ 
#     ---PURPOSE---
#     Take an existing graph and add to it the children 
#     of an input_nodename. Recursive function.
#     ---INPUT---
#     dic             Dictionary representing the entire ontology graph (with "rank" key included)
#     graph           The graphviz graph object that will be updated.
#                     graph may be a subgraph of the entire graph as long as 
#                     input_nodename is a node name in it
#     input_nodename  The name of the node whose children you want to display
#     """
#     name = dic.get('name')
#     children = dic.get('children')
#     if input_nodename == None: # default is root
#         href_expand = url_for('ontology.interactive_ontology',nodename='root')
#         href_contract = url_for('ontology.interactive_ontology',nodename='root',contract=True).replace('&','&amp;')
#         # href_contract = '/interactive_ontology?contract=True&amp;nodename=root'
#         graph.node('root',label='''<<TABLE><TR><TD href="{}">root</TD><TD href="{}">-</TD></TR></TABLE>>'''.format(href_expand,href_contract))
#     if name == input_nodename:
#         for child in children: # child is a dict
#             child_name = child.get('name')
#             # body_str = '\t'
#             # graph.node(name,href=url_for('ontology.interactive_ontology',nodename=name))
#             # graph.node(child_name,href=url_for('ontology.interactive_ontology',nodename=child_name))
#             href_expand = url_for('ontology.interactive_ontology',nodename=child_name)
#             href_contract = url_for('ontology.interactive_ontology',nodename=child_name,contract=True).replace('&','&amp;')
#             # href_contract = url_for('ontology.interactive_ontology',nodename=child_name,contract=True).replace('&','&amp;')

#             # href_contract = 

#             graph.node(child_name,label='''<<TABLE><TR><TD href="{}">{}</TD><TD href="{}">-</TD></TR></TABLE>>'''.format(href_expand,child_name,href_contract))
#             graph.edge(name,child_name)
#         return graph
     
#     for child in children:
#         expand_graph(child,graph,input_nodename=input_nodename)
#     return graph

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
        graph.node('root',label='''<<TABLE><TR><TD href="{}">root</TD><TD href="{}">-</TD></TR></TABLE>>'''.format(href_expand,href_contract))
    if name == input_nodename:
        for child in children: # child is a dict
            child_name = child.get('name')
            href_expand = '/interactive_ontology?input_nodename={}'.format(child_name)
            href_contract = '/interactive_ontology?input_nodename={}&amp;contract=True'.format(child_name)
            graph.node(child_name,label='''<<TABLE><TR><TD href="{0}">{1}</TD><TD href="{2}">-</TD></TR></TABLE>>'''\
                       .format(href_expand,child_name,href_contract))
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
            child_body_str = '\t{0} [label=<<TABLE><TR><TD href="/interactive_ontology?input_nodename={1}">{1}</TD>\
<TD href="/interactive_ontology?input_nodename={1}&amp;contract=True">-</TD></TR></TABLE>>]'.format(child_label,child_name)

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