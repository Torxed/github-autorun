import fastapi
import os
import sys
import tempfile
import subprocess
import logging
import pathlib
import json
import hashlib
import hmac
import urllib.request

from .github_models import Ping, PullRequest, GithubJobs, WorkflowJob
from .config import config

app = fastapi.FastAPI()

# .. todo::
#    Clean up the "JSON" logger, to be more robust.
#    But we do want the format to be machine parse:able.

log = logging.getLogger()
log.setLevel(logging.DEBUG)
log_stdout = logging.StreamHandler(sys.stdout)
log_stdout.setLevel(logging.DEBUG)
log_stdout.setFormatter(
	logging.Formatter(json.dumps({
		"human_time" : "%(asctime)s",
		"logger_name": "%(process)d",
		"level": "%(levelname)s",
		"message": "%(message)s"
	}))
)

log.addHandler(log_stdout)

if config.github.secret is None:
	log.warning(f"No secret has been configured, anyone can post to your webhook!")

def verify_signature(payload :bytes, signature :str):
	"""
	Used to validate webhook deliveries:
	 * https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries
	"""
	hash_object = hmac.new(config.github.secret.encode('utf-8'), msg=payload, digestmod=hashlib.sha256)
	expected_signature = "sha256=" + hash_object.hexdigest()

	if hmac.compare_digest(expected_signature, signature):
		return True

	return False

@app.post('/github/')
async def webhook_entry(payload :Ping|PullRequest|WorkflowJob, request :fastapi.Request, response :fastapi.Response):
	# We validate the webhook secret, only if we configured one
	if config.github.secret and verify_signature(await request.body(), request.headers.get('X-Hub-Signature-256')) is not True:
		log.warning(f"Invalid webhook signature, ignoring request (make sure your secret match on the webhook and in TOML config)")

		return fastapi.Response(
			status_code=fastapi.status.HTTP_403_FORBIDDEN
		)

	# Ignore by accepting all non-PR payloads
	if not isinstance(payload, PullRequest):
		return fastapi.Response(
			status_code=202
		)

	# Ignore by accepting PR hooks that are not:
	if payload.action not in ('opened', 'synchronize', 'reopened'):
		return fastapi.Response(
			status_code=202
		)

	# payload.head < PR reference
	# payload.base < Target reference

	# .. todo::
	#    Perhaps we can optimize here, and check if the payload.sender is an outside collaborator
	#    and only perform our checks if that is the case. As there is no way to force all runners to be approved.
	#    Only outside collaborators - unless Workaround 3 is chosen: https://md.archlinux.org/s/aIL4kaCtY#workaround-3

	log.info(f"Verifying that the PR \\\"{payload.pull_request.title}\\\" does not modify .github/workflows")

	with tempfile.TemporaryDirectory() as tempdir:
		# Clone the repo in question
		log.debug(f"git clone {payload.pull_request.base.repo.html_url}@{payload.pull_request.base.ref}")
		subprocess.run(f"git clone -q {payload.pull_request.base.repo.html_url} --branch {payload.pull_request.base.ref} --single-branch {tempdir}/{payload.pull_request.base.repo.name}", capture_output=True, shell=True, cwd=tempdir)

		# Add the PR repo/branch
		log.debug(f"git remote add \\\"pr\\\" {payload.pull_request.head.repo.full_name}@{payload.pull_request.head.ref}")
		subprocess.run(f"git remote add pr {payload.pull_request.head.repo.html_url}", capture_output=True, shell=True, cwd=f"{tempdir}/{payload.pull_request.base.repo.name}")

		# Update all the remotes (repo + pr)
		log.debug(f"git remote update {payload.pull_request.base.repo.full_name}@{payload.pull_request.base.ref} and {payload.pull_request.head.repo.full_name}@{payload.pull_request.head.ref}")
		subprocess.run(f"git remote update", capture_output=True, shell=True, cwd=f"{tempdir}/{payload.pull_request.base.repo.name}")

		# git diff - files
		file_changes = subprocess.run(f"git diff --name-only {payload.pull_request.base.ref} pr/{payload.pull_request.head.ref}", capture_output=True, shell=True, cwd=f"{tempdir}/{payload.pull_request.base.repo.name}").stdout.decode().strip().split('\n')
		log.debug(f"Files modified: {json.dumps(file_changes).replace('"', '\\"')}")

		# Check if any file lives in .github/workflows
		for filename in file_changes:
			if filename == '': continue

			try:
				pathlib.Path(filename).relative_to(pathlib.Path('.github/workflows'))
				# Not allowed to modify .github/workflow/* files
				log.debug(f"Blocking runners in PR from executing, as they have modified .github/workflows")

				return fastapi.Response(
					status_code=fastapi.status.HTTP_403_FORBIDDEN
				)
			except ValueError:
				# This is good, it means the filename was not a relative path of .github/workflows/
				continue


		log.info(f"PR did not modify workflows in .github/workflows - approving all runners associated with the PR")
		
		headers = {
			"Accept": "application/vnd.github+json",
			"Authorization": f"Bearer {config.github.access_token}",
			"X-GitHub-Api-Version": "2022-11-28"
		}

		# List all runners associated with the PR head sha sum
		request = urllib.request.Request(
			f'https://api.github.com/repos/{payload.pull_request.base.repo.full_name}/actions/runs?' \
			+ f'event=pull_request' \
			+ f'&status=action_required' \
			+ f'&head_sha={payload.pull_request.head.sha}',
			method="GET",
			headers=headers
		)

		# Queue them, and if anything stands out, abort!
		jobs_to_start = {}
		with urllib.request.urlopen(request) as response:
			info = response.info()
			if info.get_content_subtype() == 'json':
				jobs = GithubJobs(**json.loads(response.read().decode(info.get_content_charset('utf-8'))))
				for job in jobs.workflow_runs:
					if job.head_commit.id != payload.pull_request.head.sha:
						log.warning(f"Job {job.head_commit.id} does not match pull requests {payload.pull_request.head.sha}")

						# Something's fishy, and we're out of chips!
						return fastapi.Response(
							status_code=fastapi.status.HTTP_403_FORBIDDEN
						)

					log.info(f"Quing '{job.name}' for start")
					jobs_to_start[job.id] = job

		# All should be good here,
		# lets approve the individual runners (I don't think there's a batch approval?)
		for id_number, job in jobs_to_start.items():
			request = urllib.request.Request(
				f'https://api.github.com/repos/{payload.pull_request.base.repo.full_name}/actions/runs/{id_number}/approve',
				method="POST",
				headers=headers
			)

			with urllib.request.urlopen(request) as response:
				info = response.info()
				log.info(f"Started '{job.name}' for start")

	# If everything went according to plan, then we
	# return '202 Accepted' to the webhook caller (has little effect, but is good practice)
	return fastapi.Response(
		status_code=202
	)