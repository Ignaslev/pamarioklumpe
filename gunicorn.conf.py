"""Pamario app defaults; Gunicorn automatically loads this from its working directory.

If systemd specifies another --config or --timeout, set the equivalent there.
Only a single receipt is processed per request; the browser advances the queue.
"""
import os

timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))
