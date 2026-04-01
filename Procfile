web: gunicorn api.wsgi:application --log-file -
worker: celery -A api worker --loglevel=info
