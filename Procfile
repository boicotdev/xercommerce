web: gunicorn api.wsgi:application --log-file -
web: gunicorn api.wsgi:worker: celery -A api worker --loglevel=info
