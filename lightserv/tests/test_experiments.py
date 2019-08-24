from flask import url_for, session
import secrets

def test_exps_show_up_on_main_page(test_client,test_schema,test_login):
	""" Check that the test post is rendered on the home page """
	response = test_client.get(url_for('main.home'), follow_redirects=True)

	assert b'Your Light Sheet Experiments' in response.data and b'mcherry' in response.data

def test_submit_good_experiment(test_client,test_schema,test_login):
	""" Ensure that submitting the experiment form correctly works """
	# Submit a new experiment. The following line issues a post request to the experiments.new_exp route, which will create the database entry
	response = test_client.post(
		url_for('experiments.new_exp'),data=dict(
			title="Demo Experiment",
			description="This is a demo experiment",
			species="rat",clearing_protocol="uDISCO",fluorophores="An experimental fluorophore",
			primary_antibody="None",secondary_antibody="None",
			image_resolution="1.3x",cell_detection=True,registration=True,
			probe_detection=True,injection_detection=False,
			username=session['user']
			),
			follow_redirects=True
		)	
		 
# 	# Now check that the test post was entered into the database and appears on the home page (the redirect)
	assert b'Your Light Sheet Experiments' in response.data and b'demo experiment' 

def test_submit_bad_experiments(test_client,test_schema,test_login):
	""" Ensure that submitting the experiment form incorrectly does not work """
	# Submit a new experiment. The following line issues a post request to the experiments.new_exp route, which will create the database entry
	response1 = test_client.post(
		url_for('experiments.new_exp'),data=dict(
			title="Bad Experiment",
			description="This is a bad experiment that should not work because Image resolution is enum and I give it an empty string",
			species="rat",clearing_protocol="uDISCO",fluorophores="An experimental fluorophore",
			primary_antibody="None",secondary_antibody="None",
			image_resolution="",cell_detection=True,registration=True,
			probe_detection=True,injection_detection=False,
			username=session['user']
			),
			follow_redirects=True
		)

	response2 = test_client.post(
		url_for('experiments.new_exp'),data=dict(
			title="Bad Experiment2",
			description="\
			This is a bad experiment that should not work because when clearing_protocol=iDISCO+, \
			there needs to be a primary antibody provided",
			species="rat",clearing_protocol="iDISCO+",fluorophores="An experimental fluorophore",
			primary_antibody="",secondary_antibody="None",
			image_resolution="",cell_detection=True,registration=True,
			probe_detection=True,injection_detection=False,
			username=session['user']
			),
			follow_redirects=True
		)	
	# Now check that the post just goes back to the new experiment form
	# If it were to succeed, it would go to the home page and 'Your Datasets' would be displayed
	assert b'Your Light Sheet Experiments' not in response1.data
	assert b'Your Light Sheet Experiments' not in response2.data