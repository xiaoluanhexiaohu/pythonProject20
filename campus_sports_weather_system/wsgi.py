import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "campus_sports_weather_system.settings")
application = get_wsgi_application()