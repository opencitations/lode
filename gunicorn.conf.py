import os
import sys
import subprocess

# Worker configuration
workers = 5
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 250
timeout = 180
graceful_timeout = 180
bind = "0.0.0.0:8080"

# Memory limits
max_requests = 800
max_requests_jitter = 200

#The number of seconds to wait for requests on a Keep-Alive connection.
keepalive = 20

# Logging
accesslog = None
errorlog = "-"
loglevel = "info"

def post_worker_init(worker):
    """
    Called just after a worker has been initialized.
    """
    print(f"Worker {worker.pid} initialized and ready")