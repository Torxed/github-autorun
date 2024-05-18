import os
import sys
import json
import pathlib
import asyncio
import logging
from typing import Any, IO, Mapping, Optional, TYPE_CHECKING, Union
from hypercorn.config import Config
from hypercorn.asyncio import serve
from hypercorn.logging import AccessLogAtoms

"""
This is the `python -m autorun` entrypoint.
We'll use hypercorn to start the API.
"""

def _create_logger(
	name: str,
	target: Union[logging.Logger, str, None],
	level: Optional[str],
	sys_default: IO,
	*,
	propagate: bool = True,
) -> Optional[logging.Logger]:
	"""
	Carbon copy of python-libs/hypercorn/logging.py -> _create_logger()
	With the slight modification to the logging.Formatter() to use a JSON
	format instead (which is not perfect - as it can cause issues with quotations)
	"""
	if isinstance(target, logging.Logger):
		return target

	if target:
		logger = logging.getLogger(name)
		logger.handlers = [
			logging.StreamHandler(sys_default) if target == "-" else logging.FileHandler(target)  # type: ignore # noqa: E501
		]
		logger.propagate = propagate
		formatter = logging.Formatter(json.dumps({
			"human_time" : "%(asctime)s",
			"logger_name": "%(process)d",
			"level": "%(levelname)s",
			"message": "%(message)s"
		}))
		logger.handlers[0].setFormatter(formatter)
		if level is not None:
			logger.setLevel(logging.getLevelName(level.upper()))
		return logger
	else:
		return None

class Logger:
	"""
	Carbon copy of python-libs/hypercorn/logging.py -> Logger
	It's here so that it will use our _create_logger() instead
	"""
	def __init__(self, config: "Config") -> None:
		self.access_log_format = config.access_log_format

		self.access_logger = _create_logger(
			"hypercorn.access",
			config.accesslog,
			config.loglevel,
			sys.stdout,
			propagate=False,
		)
		self.error_logger = _create_logger(
			"hypercorn.error", config.errorlog, config.loglevel, sys.stderr
		)

		if config.logconfig is not None:
			if config.logconfig.startswith("json:"):
				with open(config.logconfig[5:]) as file_:
					dictConfig(json.load(file_))
			elif config.logconfig.startswith("toml:"):
				with open(config.logconfig[5:], "rb") as file_:
					dictConfig(tomllib.load(file_))
			else:
				log_config = {
					"__file__": config.logconfig,
					"here": os.path.dirname(config.logconfig),
				}
				fileConfig(config.logconfig, defaults=log_config, disable_existing_loggers=False)
		else:
			if config.logconfig_dict is not None:
				dictConfig(config.logconfig_dict)

	async def access(
		self, request: "WWWScope", response: "ResponseSummary", request_time: float
	) -> None:
		if self.access_logger is not None:
			self.access_logger.info(
				self.access_log_format, self.atoms(request, response, request_time)
			)

	async def critical(self, message: str, *args: Any, **kwargs: Any) -> None:
		if self.error_logger is not None:
			self.error_logger.critical(message, *args, **kwargs)

	async def error(self, message: str, *args: Any, **kwargs: Any) -> None:
		if self.error_logger is not None:
			self.error_logger.error(message, *args, **kwargs)

	async def warning(self, message: str, *args: Any, **kwargs: Any) -> None:
		if self.error_logger is not None:
			self.error_logger.warning(message, *args, **kwargs)

	async def info(self, message: str, *args: Any, **kwargs: Any) -> None:
		if self.error_logger is not None:
			self.error_logger.info(message, *args, **kwargs)

	async def debug(self, message: str, *args: Any, **kwargs: Any) -> None:
		if self.error_logger is not None:
			self.error_logger.debug(message, *args, **kwargs)

	async def exception(self, message: str, *args: Any, **kwargs: Any) -> None:
		if self.error_logger is not None:
			self.error_logger.exception(message, *args, **kwargs)

	async def log(self, level: int, message: str, *args: Any, **kwargs: Any) -> None:
		if self.error_logger is not None:
			self.error_logger.log(level, message, *args, **kwargs)

	def atoms(
		self, request: "WWWScope", response: Optional["ResponseSummary"], request_time: float
	) -> Mapping[str, str]:
		"""Create and return an access log atoms dictionary.

		This can be overidden and customised if desired. It should
		return a mapping between an access log format key and a value.
		"""
		return AccessLogAtoms(request, response, request_time)

	def __getattr__(self, name: str) -> Any:
		return getattr(self.error_logger, name)

if __name__ == "__main__":
	from autorun import app, config

	logging.getLogger("hypercorn.error").setLevel(logging.DEBUG)
	logging.getLogger("hypercorn.access").setLevel(logging.DEBUG)

	corn_conf = Config()
	corn_conf.bind = f"{config.api.address}:{config.api.port}"
	corn_conf.certfile = config.api.fullchain
	corn_conf.keyfile = config.api.privkey
	corn_conf.loglevel = "DEBUG"
	corn_conf.use_reloader = False
	corn_conf.accesslog = '-'
	corn_conf.logger_class = Logger
	# Slight variation to the default format: https://pgjones.gitlab.io/hypercorn/how_to_guides/logging.html#configuring-access-logs
	# As we need to account for our 'json formatter' not dealing with quotations.
	corn_conf.access_log_format = '%(h)s %(l)s %(l)s %(t)s \\"%(r)s\\" %(s)s %(b)s \\"%(f)s\\" \\"%(a)s\\"'
	corn_conf.errorlog = '-'

	asyncio.run(serve(app, corn_conf))