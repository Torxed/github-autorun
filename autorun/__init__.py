import fastapi
import os
import sys
import tempfile
import subprocess
import logging
import pathlib
import json
import asyncio
import hashlib
import hmac
import urllib.request
from hypercorn.config import Config
from hypercorn.asyncio import serve

from .github_models import Ping, PullRequest, GithubJobs, WorkflowJob
from .config import config
from .hypercorn_logger import Logger

__version__ = "0.0.1"

app = fastapi.FastAPI()

# .. todo::
#    Clean up the "JSON" logger, to be more robust.
#    But we do want the format to be machine parse:able.

log = logging.getLogger()
log.setLevel(config.api.log_level)
log_stdout = logging.StreamHandler(sys.stdout)
log_stdout.setLevel(config.api.log_level)
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

def run_as_a_module():
	logging.getLogger("hypercorn.error").setLevel(config.api.log_level)
	logging.getLogger("hypercorn.access").setLevel(config.api.log_level)

	class EndpointFilter(logging.Filter):
		def filter(self, record: logging.LogRecord) -> bool:
			return record.getMessage().find("GET /healthcheck ") == -1

	# Filter out /healthcheck to not spam access log too much
	logging.getLogger("hypercorn.access").addFilter(EndpointFilter())

	corn_conf = Config()
	corn_conf.bind = f"{config.api.address}:{config.api.port}"
	if config.api.fullchain:
		corn_conf.certfile = config.api.fullchain
	if config.api.privkey:
		corn_conf.keyfile = config.api.privkey
	corn_conf.loglevel = config.api.log_level
	corn_conf.use_reloader = False
	corn_conf.accesslog = '-'
	corn_conf.logger_class = Logger
	# Slight variation to the default format: https://pgjones.gitlab.io/hypercorn/how_to_guides/logging.html#configuring-access-logs
	# As we need to account for our 'json formatter' not dealing with quotations.
	corn_conf.access_log_format = '%(h)s %(l)s %(l)s %(t)s \\\\"%(r)s\\\\" %(s)s %(b)s \\\\"%(f)s\\\\" \\\\"%(a)s\\\\"'
	corn_conf.errorlog = '-'

	asyncio.run(serve(app, corn_conf))

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

def list_pr_jobs(headers, payload):
	# List all runners associated with the PR head sha sum
	request = urllib.request.Request(
		f'https://api.github.com/repos/{payload.pull_request.base.repo.full_name}/actions/runs?' \
		+ f'event=pull_request' \
		#+ f'&status=action_required' \
		+ f'&head_sha={payload.pull_request.head.sha}',
		method="GET",
		headers=headers
	)

	# Iterate any job related to the PR
	with urllib.request.urlopen(request) as response:
		info = response.info()
		if info.get_content_subtype() == 'json':
			data = json.loads(response.read().decode(info.get_content_charset('utf-8')))
			jobs = GithubJobs(**data)
			for job in jobs.workflow_runs:
				if job.head_commit.id != payload.pull_request.head.sha:
					log.warning(f"Job {job.head_commit.id} does not match pull requests {payload.pull_request.head.sha}")

					# Something's fishy, and we're out of chips!
					return fastapi.Response(
						status_code=fastapi.status.HTTP_403_FORBIDDEN
					)

				log.debug(f"Found job '{job.name}' related to Pull Requests {', '.join(['#'+str(pr.number) for pr in job.pull_requests])} called '{job.display_title}'")
				yield job


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

	# Used to call the GitHub API during queries
	headers = {
		"Accept": "application/vnd.github+json",
		"Authorization": f"Bearer {config.github.access_token}",
		"X-GitHub-Api-Version": "2022-11-28"
	}

	# payload.head < PR reference
	# payload.base < Target reference

	# .. todo::
	#    Perhaps we can optimize here, and check if the payload.sender is an outside collaborator
	#    and only perform our checks if that is the case. As there is no way to force all runners to be approved.
	#    Only outside collaborators - unless Workaround 3 is chosen: https://md.archlinux.org/s/aIL4kaCtY#workaround-3

	log.info(f"Verifying that the PR #{payload.pull_request.number} \\\"{payload.pull_request.title}\\\" does not modify any proected paths defined in the config.")

	with tempfile.TemporaryDirectory() as tempdir:
		# Clone the repo in question
		log.debug(f"git clone {payload.pull_request.base.repo.html_url}@{payload.pull_request.base.ref}")
		subprocess.run(f"git clone -q --branch \"{payload.pull_request.base.ref}\" --single-branch -- \"{payload.pull_request.base.repo.html_url}\" \"{tempdir}/{payload.pull_request.base.repo.name}\"", capture_output=True, shell=True, cwd=tempdir)

		# Add the PR repo/branch
		log.debug(f"git remote add \\\"pr\\\" {payload.pull_request.head.repo.full_name}@{payload.pull_request.head.ref}")
		subprocess.run(f"git remote add pr -- \"{payload.pull_request.head.repo.html_url}\"", capture_output=True, shell=True, cwd=f"{tempdir}/{payload.pull_request.base.repo.name}")

		# Update all the remotes (repo + pr)
		log.debug(f"git remote update {payload.pull_request.base.repo.full_name}@{payload.pull_request.base.ref} and {payload.pull_request.head.repo.full_name}@{payload.pull_request.head.ref}")
		subprocess.run(f"git remote update", capture_output=True, shell=True, cwd=f"{tempdir}/{payload.pull_request.base.repo.name}")

		# git diff - files
		file_changes = subprocess.run(f"git diff --name-only -- \"{payload.pull_request.base.ref}\" \"pr/{payload.pull_request.head.ref}\"", capture_output=True, shell=True, cwd=f"{tempdir}/{payload.pull_request.base.repo.name}").stdout.decode().strip().split('\n')
		log.debug(f"Files modified: {json.dumps(file_changes).replace('"', '\\"')}")

		# Check if any file lives in .github/workflows
		if config.github.protected:
			cancel_runners = False
			for filename in file_changes:
				if filename == '': continue

				for regex in config.github.protected:
					if regex.search(filename) is not None:
						cancel_runners = True
						break

				if cancel_runners:
					break

			if cancel_runners:
				log.warning(f"Cancelling runners in PR from executing, as they have modified proected file: {filename}")

				for job in list_pr_jobs(headers, payload):
					if job.status != 'completed':
						log.info(f"Cancelling job '{job.name}'")
						request = urllib.request.Request(
							f'https://api.github.com/repos/{payload.pull_request.base.repo.full_name}/actions/runs/{job.id}/cancel',
							method="POST",
							headers=headers
						)

						with urllib.request.urlopen(request) as response:
							info = response.info()
							log.info(f"Canceled job '{job.name}'")

					# Deleting jobs, will allow PR's to be merged as there will be
					# no incomplete jobs blocking the merger. If that's what we want, uncomment this:

					# request = urllib.request.Request(
					# 	f'https://api.github.com/repos/{payload.pull_request.base.repo.full_name}/actions/runs/{job.id}',
					# 	method="DELETE",
					# 	headers=headers
					# )

					# with urllib.request.urlopen(request) as response:
					# 	info = response.info()
					# 	log.info(f"Deleted job '{job.name}'")

				return fastapi.Response(
					status_code=fastapi.status.HTTP_403_FORBIDDEN
				)

			log.info(f"PR did not modify any configured protected paths")
		else:
			log.warning(f"No paths are defined as proected in the configuration.")

		# All should be good here,
		# lets approve the individual runners (I don't think there's a batch approval?)
		for job in list_pr_jobs(headers, payload):
			if job.status != 'completed':
				request = urllib.request.Request(
					f'https://api.github.com/repos/{payload.pull_request.base.repo.full_name}/actions/runs/{job.id}/approve',
					method="POST",
					headers=headers
				)

				with urllib.request.urlopen(request) as response:
					info = response.info()
					log.info(f"Started job '{job.name}'")

	# If everything went according to plan, then we
	# return '202 Accepted' to the webhook caller (has little effect, but is good practice)
	return fastapi.Response(
		status_code=202
	)