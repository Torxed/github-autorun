import os
import pathlib
import asyncio
import logging
from hypercorn.config import Config
from hypercorn.asyncio import serve

if __name__ == "__main__":
	from autorun import app

	logging.getLogger("hypercorn.error").setLevel(logging.DEBUG)
	logging.getLogger("hypercorn.access").setLevel(logging.DEBUG)

	corn_conf = Config()
	corn_conf.bind = f"172.22.0.80:1337"
	corn_conf.certfile = os.environ.get('API_TLS_CERT', pathlib.Path('./fullchain.pem').expanduser().absolute())
	corn_conf.keyfile = os.environ.get('API_TLS_KEY', pathlib.Path('./privkey.pem').expanduser().absolute())
	corn_conf.loglevel = "DEBUG"
	corn_conf.use_reloader = False
	corn_conf.accesslog = '-'
	corn_conf.errorlog = '-'

	asyncio.run(serve(app, corn_conf))