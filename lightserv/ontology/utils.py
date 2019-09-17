import pkg_resources
import json

from flask import url_for
import numpy as np
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

my_graph = graphviz.Digraph(name=' ',format='svg',strict=True) # strict means you cant have more than 1 edge between nodes. name is set so to " " so that nothing shows up on hover 

my_graph.attr('node',shape='box')

table_border = 0
contract_cell_border=1
tooltip = ' ' # makes it so that nothing appears when mouse hovers over node
root_body_str = '''\troot [label=<<TABLE BORDER="{0}">\
<TR><TD id="root" href="/interactive_ontology?input_nodename=root">root</TD>\
<TD BORDER="{1}" href="/interactive_ontology?input_nodename=root&amp;contract=True">-</TD>\
</TR></TABLE>> tooltip="{2}"]'''.format(table_border,contract_cell_border,tooltip)
# print(root_body_str)

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
        href_expand = '/interactive_ontology?input_nodename=root'
        href_contract = '/interactive_ontology?input_nodename=root&amp;contract=True'
        graph.node('root',label='''<<TABLE BORDER="{0}"><TR><TD id="root" href="{1}">root</TD>\
<TD BORDER="{2}" href="{3}">-</TD></TR></TABLE>>'''\
            .format(table_border,href_expand,contract_cell_border,href_contract),tooltip=tooltip)
    if name == input_nodename:
        for child in children: # child is a dict
            child_name = child.get('name')
            child_anchor_name = '_'.join(child_name.split(' '))
            href_expand = '/interactive_ontology?input_nodename={0}'.format(child_name)
            href_contract = '/interactive_ontology?input_nodename={}&amp;contract=True'.format(child_name)
            graph.node(child_name,label='''<<TABLE BORDER="{0}"><TR><TD id="{1}" href="{2}">{3}</TD>\
<TD BORDER="{4}" href="{5}">-</TD></TR></TABLE>>'''\
                       .format(table_border,child_anchor_name,href_expand,child_name,contract_cell_border,href_contract),tooltip=tooltip)
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
            child_anchor_name = '_'.join(child_name.split(' '))

            child_label = f'"{child_name}"' if len(child_name.split())>1 else child_name
            edge_str = f'\t{name_label} -> {child_label}' 
#             print(edge_st/r)
            child_body_str = '\t{0} [label=<<TABLE BORDER="{1}"><TR><TD id="{2}" href="/interactive_ontology?input_nodename={3}">{3}</TD>\
<TD BORDER="{4}" href="/interactive_ontology?input_nodename={3}&amp;contract=True">-</TD></TR></TABLE>> tooltip="{5}"]'.\
format(child_label,table_border,child_anchor_name,child_name,contract_cell_border,tooltip)

            if edge_str in graph.body:
                del graph.body[graph.body.index(edge_str)]
                del graph.body[graph.body.index(child_body_str)]
                contract_graph(child,graph,input_nodename=child_name)
    for child in children:
        contract_graph(child,graph,input_nodename=input_nodename)
    return graph

def make_ID_reassignment_dict(ontology_dict,graph,output_dict):
    """ 
    ---PURPOSE---
    Loop through an ontology dictionary and return a dictionary 
    whose keys are parent ids at the highest level in the graph and values are a list
    of descendent ids of each of these parents. 
    ---INPUT---
    ontology_dict        The dictionary containing the entire ontology dictionary
    graph                The graph whose structure you want to capture
    output_dict          The dictionary which will store the parent to descendents links
    """
    
    ID = ontology_dict.get('id')
    children = ontology_dict.get('children')

    for child in children:
        child_ID = child.get('id')
        child_name = child.get('name')
        child_label = f'"{child_name}"' if len(child_name.split())>1 else child_name
        # child_str = f'\t{child_label}' 
        child_body_str = '\t{0} [label=<<TABLE BORDER="{1}"><TR><TD href="/interactive_ontology?input_nodename={2}">{2}</TD>\
<TD BORDER="{3}" href="/interactive_ontology?input_nodename={2}&amp;contract=True">-</TD></TR></TABLE>> tooltip="{4}"]'.\
format(child_label,table_border,child_name,contract_cell_border,tooltip)
        
        if child_body_str in graph.body:
            global current_parent
            current_parent = child_ID
        else:
            if current_parent not in output_dict.keys():
                output_dict[current_parent]=[]
            output_dict[current_parent].append(child_ID)
            
        make_ID_reassignment_dict(child,graph,output_dict)
    return

def make_tuple_input(ID_reassignment_dict,chunk_size):
    '''
    ---PURPOSE---
    Take the reassignment dictionary
    and convert it to a list of lists of tuples [(input_val1,target_val1),(input_val2,target_val2),...]
    to feed to id_reassignment_parallel, which takes a list of tuples as input
    ---INPUT---
    id_reassignment_dict     A reassignment dictionary, e.g. {0:[1,2,3,4],5:[6,7,8,9]}
    chunk_size               Determines how many reassignments to 
                             perform in a single call to id_reassignment_parallel     
    '''
    # First make flattened list of tuples, then chunk it later
    flattened_list_of_tuples = []
    for key in ID_reassignment_dict.keys():
        for val in ID_reassignment_dict[key]:
            flattened_list_of_tuples.append((key,val))
    chunked_list_of_tuples = [flattened_list_of_tuples[i:i+chunk_size] \
                              for i in range(0,len(flattened_list_of_tuples),chunk_size) ]
    return chunked_list_of_tuples