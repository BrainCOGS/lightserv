from flask import url_for
import secrets
import tempfile
import webbrowser
import pickle
import pandas as pd
import pkg_resources
from datetime import datetime
from numpy import random

data_dir = pkg_resources.resource_filename('lightserv','data')
udisco_test_pkl_file = data_dir + '/udisco_test_data.pkl'

# def test_bad_clearing_protocol_entry(test_client,test_schema,test_login):
# 	""" Check that a bad clearing protocol redirects to new experiment form """
# 	response = test_client.get(url_for('clearing.clearing_entry',
# 		clearing_protocol='made_up_clearing_protocol',experiment_id=1)
# 		, follow_redirects=True)
# 	# with tempfile.NamedTemporaryFile('wb', delete=False,suffix='.html') as f:
# 	# 	url = 'file://' + f.name 
# 	# 	f.write(response.data)
# 	# print(url)
# 	# webbrowser.open(url)
# 	assert b'Instructions' in response.data and b'Clearing Setup' in response.data

# def test_bad_experiment_entry(test_client,test_schema,test_login):
# 	""" Check that a bad experiment_id redirects to new experiment form """
# 	response = test_client.get(url_for('clearing.clearing_entry',
# 		clearing_protocol='uDISCO',experiment_id=1000)
# 		, follow_redirects=True)

# 	assert b'Instructions' in response.data and b'Clearing Setup' in response.data

# def test_get_iDISCOplus_entry_page(test_client,test_schema,test_login):
# 	""" Check that a good clearing_protocol and experiment_id combo
# 	 renders to the correct clearing entry form """
# 	response = test_client.get(url_for('clearing.clearing_entry',
# 		clearing_protocol='iDISCO+_immuno',experiment_id=2)
# 		, follow_redirects=True)
# 	assert b'iDISCO+_immuno' in response.data and b'Entry log for experiment_id=2' in response.data

# def test_get_iDISCOabbreviated_entry_page(test_client,test_schema,test_login):
# 	""" Check that a good clearing_protocol and experiment_id combo
# 	 renders to the correct clearing entry form """
# 	response = test_client.get(url_for('clearing.clearing_entry',
# 		clearing_protocol='iDISCO abbreviated clearing',experiment_id=3)
# 		, follow_redirects=True)
# 	assert b'iDISCO abbreviated clearing' in response.data and b'Entry log for experiment_id=3' in response.data

# def test_get_iDISCOabbreviatedrat_entry_page(test_client,test_schema,test_login):
# 	""" Check that a good clearing_protocol and experiment_id combo
# 	 renders to the correct clearing entry form """
# 	response = test_client.get(url_for('clearing.clearing_entry',
# 		clearing_protocol='iDISCO abbreviated clearing (rat)',experiment_id=11)
# 		, follow_redirects=True)
# 	assert b'iDISCO abbreviated clearing (rat)' in response.data and b'Entry log for experiment_id=11' in response.data

# def test_get_uDISCO_entry_page(test_client,test_schema,test_login):
# 	""" Check that a good clearing_protocol and experiment_id combo
# 	 renders to the correct clearing entry form """
# 	response = test_client.get(url_for('clearing.clearing_entry',
# 		clearing_protocol='uDISCO',experiment_id=1)
# 		, follow_redirects=True)
# 	assert b'uDISCO' in response.data and b'Entry log for experiment_id=1' in response.data

# def test_post_uDISCO_entry(test_client,test_schema,test_login):
# 	""" Simulates a few repeated post requests when filling out the uDISCO clearing form """
# 	with open(udisco_test_pkl_file,'rb') as pkl_file:
# 		udisco_data = pickle.load(pkl_file) # loads it as an ndarray where the dtype attrib has column names
# 	columns = udisco_data.dtype.names	
# 	vals = udisco_data[0]
# 	post_data_dict = {columns[ii]:vals[ii] for ii in range(len(columns))}
# 	''' First post request '''
# 	key1 = 'time_dehydr_butanol_70percent'
# 	val1 = post_data_dict[key1].strftime('%Y-%m-%dT%H:%M')
# 	submit_key1 = key1 + '_submit'
# 	response1 = test_client.post(url_for('clearing.clearing_entry',
# 		clearing_protocol='uDISCO',experiment_id=1),data={key1:val1,submit_key1:1}
# 		, follow_redirects=True)
# 	''' Second post request '''
# 	key2 = 'exp_notes'
# 	val2 = post_data_dict[key2]
# 	submit_key2 = key2 + '_submit'
# 	response1 = test_client.post(url_for('clearing.clearing_entry',
# 		clearing_protocol='uDISCO',experiment_id=1),data={key2:val2,submit_key2:1}
# 		, follow_redirects=True)
# 	clearing_contents = test_schema.UdiscoClearing() & 'experiment_id=1'
# 	assert clearing_contents.fetch1(key1).strftime('%Y-%m-%dT%H:%M') == val1
# 	assert clearing_contents.fetch1(key2) == val2
