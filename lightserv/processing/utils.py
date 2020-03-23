problematic_codes = ("FAILED","BOOT_FAIL","CANCELLED","DEADLINE","OUT_OF_MEMORY","REVOKED")

def determine_status_code(status_codes):
	""" Given a list of status codes 
	from a sacct query on a jobid (could be an array job),
	return the status code of the group. 
	This is somewhat subjective and the rules I have defined are:
	if all statuses are the same then the status is the status that is shared,
	if any have a code that is problematic (see "problematic_codes"), then we return "FAILED"
	if none have problematic codes but there are multiple going, then return "RUNNING"
	"""
	if len(status_codes) > 1:
		if all([status_codes[jj]==status_codes[0] for jj in range(len(status_codes))]):
			# If all are the same then just report whatever that code is
			status=status_codes[0]
		elif any([status_codes[jj] in problematic_codes for jj in range(len(status_codes))]):
			# Check if some have problematic codes 
			status="FAILED"
		else:
			# If none have failed but there are multiple then they must be running
			status="RUNNING"
	else:
		status = status_codes[0]
	if 'CANCELLED' in status: 
		# in case status is "CANCELLED by {UID}"
		status = 'CANCELLED'
	return status