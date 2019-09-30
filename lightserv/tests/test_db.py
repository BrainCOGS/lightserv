def test_tables_exist(test_client,test_schema):
	user_contents = test_schema.User()
	exp_contents = test_schema.Experiment()
	assert len(user_contents) == 11
	assert len(exp_contents) == 32

