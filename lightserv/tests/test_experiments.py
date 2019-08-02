from flask import url_for
import secrets

def test_exps_show_up_on_main_page(test_client,init_database,login_response):
	""" Check that the test post is rendered on the home page """
	response = test_client.get(url_for('main.home'), follow_redirects=True)
	assert b'Test Experiment' in response.data

def test_submit_good_experiment(test_client,init_database,login_response):
	""" Ensure that submitting the experiment form correctly works """
	# Submit a new experiment. The following line issues a post request to the experiments.new_exp route, which will create the database entry
	response = test_client.post(
		url_for('experiments.new_exp'),data=dict(
			dataset_hex=secrets.token_hex(5),title="Second Experiment",
			description="This is my second experiment",species="rat",
			clearing_protocol="uDISCO",fluorophores="None",
			primary_antibody="None",secondary_antibody="None",
			image_resolution=1.3,cell_detection=True,registration=True,
			probe_detection=True,injection_detection=False),
			follow_redirects=True
		)	
	# Now check that the test post was entered into the database
	assert b'Second Experiment' in response.data and b'Your Datasets' in response.data

def test_submit_bad_experiment(test_client,init_database,login_response):
	""" Ensure that submitting the experiment form incorrectly does not work """
	# Submit a new experiment. The following line issues a post request to the experiments.new_exp route, which will create the database entry
	response = test_client.post(
		url_for('experiments.new_exp'),data=dict(
			dataset_hex='abc',title="Bad Experiment",
			description="This is a faulty experiment",species="rat",
			clearing_protocol="uDISCO",fluorophores="None",
			primary_antibody="None",secondary_antibody="None",
			image_resolution=1.3,cell_detection=True,registration=True,
			probe_detection=True,injection_detection=False),
			follow_redirects=True, 
		)	
	# Now check that the post just goes back to the new experiment form
	# If it were to succeed, it would go to the home page and 'Your Datasets' would be displayed
	assert b'Your Datasets' not in response.data