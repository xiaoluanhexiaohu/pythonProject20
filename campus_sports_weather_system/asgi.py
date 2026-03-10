import os
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "campus_sports_weather_system.settings")
application = get_asgi_application()