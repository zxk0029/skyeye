import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'skyeye.settings')

application = get_asgi_application()

# uvicorn skyeye.asgi:application --host 0.0.0.0 --port 8000 --reload