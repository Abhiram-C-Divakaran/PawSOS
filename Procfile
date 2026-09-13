web: uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port ${PORT:-8000} --workers 2
worker: celery -A app.tasks.celery_app.celery_app --workdir backend worker --loglevel=INFO -Q dispatch,notifications,default
beat: celery -A app.tasks.celery_app.celery_app --workdir backend beat --loglevel=INFO
