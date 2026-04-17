from django.urls import path
from . import views

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("", views.dashboard, name="dashboard"),

    path("campuses/", views.campus_list, name="campus_list"),
    path("campuses/create/", views.campus_create, name="campus_create"),

    path("venues/", views.venue_list, name="venue_list"),
    path("venues/create/", views.venue_create, name="venue_create"),

    path("events/", views.event_list, name="event_list"),
    path("events/create/", views.event_create, name="event_create"),

    path("meets/", views.meet_list, name="meet_list"),
    path("meets/create/", views.meet_create, name="meet_create"),

    path("weather/", views.weather_center, name="weather_center"),
    path("weather/refresh/", views.refresh_weather, name="refresh_weather"),
    path("alerts/", views.alert_center, name="alert_center"),

    path("api/v1/weather/refresh/<int:campus_id>/", views.api_refresh_weather_v1, name="api_refresh_weather_v1"),
    path("api/v2/weather/refresh/<int:campus_id>/", views.api_refresh_weather_v2, name="api_refresh_weather_v2"),

    path("suggestions/", views.suggestion_list, name="suggestion_list"),
    path("suggestions/generate/", views.generate_suggestions, name="generate_suggestions"),

    path("schedules/", views.schedule_list, name="schedule_list"),
    path("schedules/export/", views.export_schedule_csv, name="export_schedule_csv"),
    path("schedules/generate/<int:meet_id>/", views.generate_schedule, name="generate_schedule"),

    path("analytics/", views.analytics, name="analytics"),
    path("notifications/", views.notification_list, name="notification_list"),
    path("operation-logs/", views.operation_log_list, name="operation_log_list"),
]
