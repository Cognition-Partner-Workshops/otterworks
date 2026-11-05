import os

bind = "0.0.0.0:%s" % os.environ.get("PORT", "8080")
workers = int(os.environ.get("WEB_CONCURRENCY", "2"))
worker_tmp_dir = "/tmp"
accesslog = "-"
errorlog = "-"
control_socket_disable = True
