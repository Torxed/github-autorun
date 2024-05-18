# Remove this monster when all supported OS runs Python 3.11 or higher (3.12 is out, 3.13 is in testing currently.
try:
	import tomllib
	toml_mode = 'rb'
except:
	import toml as tomllib
	toml_mode = 'r'
# Leaving for compability for a little longer
import os
import json
import pathlib
import pydantic
import typing
import urllib.request

default_config_path = pathlib.Path(r'/etc/github-autorun/github-autorun.toml')


class GithubConfig(pydantic.BaseModel):
	"""
	The [github] part of the github-autorun.toml config.
	It dictates the access token for the GitHub REST API.
	This is needed for approving runners.
	The repository helps us verify access on config load,
	but also helps us limit PR validation against this repo.
	"""

	access_token :str = os.environ.get('GITHUB_API_TOKEN', None)
	repository :str = os.environ.get('GITHUB_REPO', 'Torxed/github-autorun')
	secret :str|None = os.environ.get('GITHUB_SECRET', None)

	@pydantic.field_validator("repository", mode='before')
	def validate_repo(cls, value):
		# .. todo::
		#    Check that the name is just alnum + slash

		return value

	@pydantic.field_validator("access_token", mode='before')
	def validate_access_token(cls, value):
		if not isinstance(value, str):
			raise ValueError(f"Github access token must be of str type")
		if len(value) != 93:
			raise ValueError(f"Github access token should be 93 char long")
		if not value.startswith('github_'):
			raise ValueError(f"Github access token must start with 'github_'")

		return value

	@pydantic.model_validator(mode='after')
	def validate_config(self):
		headers = {
			"Accept": "application/vnd.github+json",
			"Authorization": f"Bearer {self.access_token}",
			"X-GitHub-Api-Version": "2022-11-28"
		}

		request = urllib.request.Request(
			f'https://api.github.com/repos/{self.repository}',
			method="GET",
			headers=headers
		)
		
		with urllib.request.urlopen(request) as response:
			info = response.info()
			if info.get_content_subtype() == 'json':
				repo_info = json.loads(response.read().decode(info.get_content_charset('utf-8')))
				if repo_info.get('full_name', None) != self.repository:
					raise PermissionError(f"Could not fetch configured repository info: {self.repository}")

		return self

class ApiConfig(pydantic.BaseModel):
	"""
	Controls the hypercorn stuff
	"""

	fullchain :pathlib.Path = os.environ.get('API_TLS_CERT', pathlib.Path('./fullchain.pem').expanduser().absolute())
	privkey :pathlib.Path = os.environ.get('API_TLS_KEY', pathlib.Path('./privkey.pem').expanduser().absolute())
	address :str = os.environ.get('API_BIND_ADDR', "127.0.0.1")
	port :int = int(os.environ.get('API_BIND_PORT', "1337"))
	log_level :str = os.environ.get('API_LOG_LEVEL', "INFO")

	# .. todo::
	#    Improve validators to also take into account if it's PEM format.

	@pydantic.field_validator("fullchain", mode='before')
	def validate_fullchain(cls, value):
		if not isinstance(value, pathlib.Path):
			value = pathlib.Path(value)

		value = value.expanduser().resolve().absolute()
		if value.exists() is False:
			raise PermissionError(f"Could not locate 'fullhcina.pem': {value}")

		return value

	@pydantic.field_validator("privkey", mode='before')
	def validate_privkey(cls, value):
		if not isinstance(value, pathlib.Path):
			value = pathlib.Path(value)

		value = value.expanduser().resolve().absolute()
		if value.exists() is False:
			raise PermissionError(f"Could not locate 'privkey.pem': {value}")

		return value

class Config(pydantic.BaseModel):
	"""
	These are the config headers allowed in the
	TOML configuration file.
	"""

	github :GithubConfig
	api :ApiConfig


if ((conf_file := default_config_path) if default_config_path.exists() else (conf_file := pathlib.Path('./github-autorun.toml').resolve())).exists():
	with conf_file.open(toml_mode) as fh:
		conf_data = tomllib.load(fh)
else:
	raise PermissionError(f"Cannot start github-autorun without a configuration (API token is needed)")

# From here on, we can do :code:`from .config import config` and it will stay initated.
config = Config(**conf_data)