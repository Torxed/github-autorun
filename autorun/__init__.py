import fastapi
import os
import sys
import tempfile
import subprocess
import logging
import pathlib
import json
import urllib.request

from .github_models import Ping, PullRequest, GithubJobs, WorkflowJob

app = fastapi.FastAPI()
github_access_token = "<insert github token>"

log = logging.getLogger()
log.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
handler.setFormatter(logging.Formatter('{"human_time": "%(asctime)s", "logger_name": "%(name)s", "level": "%(levelname)s", "message": "%(message)s"}'))
log.addHandler(handler)

@app.post('/github/')
async def webhook_landing(payload :Ping|PullRequest|WorkflowJob, request :fastapi.Request, response :fastapi.Response):
	if not isinstance(payload, PullRequest):
		# Ignore non-PR payloads
		return fastapi.Response(
			status_code=202
		)

	if payload.action not in ('opened', 'synchronize', 'reopened'):
		# Ignore anything other than PR actions opened and modified (sync) or re-opened
		return fastapi.Response(
			status_code=202
		)


	# payload.head < Submittee
	# payload.base < Origin

	with tempfile.TemporaryDirectory() as tempdir:
		log.info(f"git clone {payload.pull_request.base.repo.html_url}@{payload.pull_request.base.ref}")
		subprocess.run(f"git clone -q {payload.pull_request.base.repo.html_url} --branch {payload.pull_request.base.ref} --single-branch {tempdir}/{payload.pull_request.base.repo.name}", capture_output=True, shell=True, cwd=tempdir)
		log.info(f"git remote add \\\"pr\\\" {payload.pull_request.head.repo.full_name}@{payload.pull_request.head.ref}")
		subprocess.run(f"git remote add pr {payload.pull_request.head.repo.html_url}", capture_output=True, shell=True, cwd=f"{tempdir}/{payload.pull_request.base.repo.name}")
		log.info(f"git remote update {payload.pull_request.base.repo.full_name}@{payload.pull_request.base.ref} and {payload.pull_request.head.repo.full_name}@{payload.pull_request.head.ref}")
		subprocess.run(f"git remote update", capture_output=True, shell=True, cwd=f"{tempdir}/{payload.pull_request.base.repo.name}")

		log.info(f"Checking file differences")
		file_changes = subprocess.run(f"git diff --name-only {payload.pull_request.base.ref} pr/{payload.pull_request.head.ref}", capture_output=True, shell=True, cwd=f"{tempdir}/{payload.pull_request.base.repo.name}").stdout.decode().strip().split('\n')

		for filename in file_changes:
			if filename == '': continue

			try:
				pathlib.Path(filename).relative_to(pathlib.Path('.github/workflows'))
				# Not allowed to modify .github/workflow/* files
				return fastapi.Response(
					status_code=fastapi.status.HTTP_403_FORBIDDEN
				)
			except ValueError:
				# This is good, it means the filename was not a relative path of .github/workflows/
				continue


		log.info(f"Changes does not include a GitHub runner change, proceeding to approve all runners: {json.dumps(file_changes).replace('"', '\\"')}")
		
		headers = {
			"Accept": "application/vnd.github+json",
			"Authorization": f"Bearer {github_access_token}",
			"X-GitHub-Api-Version": "2022-11-28"
		}
		request = urllib.request.Request(
			f'https://api.github.com/repos/{payload.pull_request.base.repo.full_name}/actions/runs?event=pull_request&status=action_required&head_sha={payload.pull_request.head.sha}',
			method="GET",
			headers=headers,
			# data=data
		)

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

		for id_number, job in jobs_to_start.items():
			request = urllib.request.Request(
				f'https://api.github.com/repos/{payload.pull_request.base.repo.full_name}/actions/runs/{id_number}/approve',
				method="POST",
				headers=headers,
				# data=data
			)
			with urllib.request.urlopen(request) as response:
				info = response.info()
				log.info(f"Started '{job.name}' for start")

	# If everything went according to plan, we return 202 Accepted
	return fastapi.Response(
		status_code=202
	)