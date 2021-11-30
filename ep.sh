#!/bin/sh

[ -z "$WORKER_PROCESSES" ] && WORKER_PROCESSES="1"
uwsgi --plugins http,python3 --http 0.0.0.0:5000 --master --wsgi-file convert_app.py --callable app --processes $WORKER_PROCESSES --post-buffering 50000 --http-timeout 120 --http-keepalive --so-keepalive
