if __name__ == "__main__":
	# Depends if it's installed, or from source
	try:
		from autorun import run_as_a_module
	except:
		from github_autorun import run_as_a_module

	run_as_a_module()