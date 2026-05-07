from django.urls import path

from . import views

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("register/", views.register, name="register"),
    path("logout/", views.logout_view, name="logout"),
    path("", views.dashboard, name="dashboard"),

    path("users/", views.user_manage, name="user_manage"),
    path("users/<int:user_id>/edit/", views.user_edit, name="user_edit"),

    path("campuses/", views.campus_list, name="campus_list"),
    path("campuses/create/", views.campus_create, name="campus_create"),
    path("campuses/<int:campus_id>/edit/", views.campus_edit, name="campus_edit"),
    path("campuses/<int:campus_id>/delete/", views.campus_delete, name="campus_delete"),

    path("venues/", views.venue_list, name="venue_list"),
    path("venues/create/", views.venue_create, name="venue_create"),
    path("venues/<int:venue_id>/edit/", views.venue_edit, name="venue_edit"),
    path("venues/<int:venue_id>/delete/", views.venue_delete, name="venue_delete"),

    path("events/", views.event_list, name="event_list"),
    path("events/create/", views.event_create, name="event_create"),
    path("events/<int:event_id>/edit/", views.event_edit, name="event_edit"),
    path("events/<int:event_id>/delete/", views.event_delete, name="event_delete"),

    path("meets/", views.meet_list, name="meet_list"),
    path("meets/create/", views.meet_create, name="meet_create"),
    path("meets/<int:meet_id>/edit/", views.meet_edit, name="meet_edit"),
    path("meets/<int:meet_id>/delete/", views.meet_delete, name="meet_delete"),
    path("meets/<int:meet_id>/register/", views.register_meet, name="register_meet"),
    path("meets/<int:meet_id>/cancel-registration/", views.cancel_registration, name="cancel_registration"),
    path("my-registrations/", views.my_registrations, name="my_registrations"),
    path("registrations/manage/", views.registration_manage, name="registration_manage"),
    path("meets/<int:meet_id>/registrations/", views.meet_registration_manage, name="meet_registration_manage"),
    path("registrations/<int:registration_id>/approve/", views.approve_registration, name="approve_registration"),
    path("registrations/<int:registration_id>/reject/", views.reject_registration, name="reject_registration"),

    path("weather/", views.weather_center, name="weather_center"),
    path("weather/refresh/", views.refresh_weather, name="refresh_weather"),
    path("alerts/", views.alert_center, name="alert_center"),
    path("feedbacks/venue/create/", views.submit_venue_feedback, name="submit_venue_feedback"),
    path("feedbacks/venue/create/<int:venue_id>/", views.submit_venue_feedback, name="submit_venue_feedback_for_venue"),
    path("feedbacks/weather/create/", views.submit_weather_feedback, name="submit_weather_feedback"),
    path("my-feedbacks/", views.my_feedbacks, name="my_feedbacks"),
    path("feedbacks/manage/", views.feedback_manage, name="feedback_manage"),
    path("feedbacks/venue/<int:feedback_id>/process/", views.process_venue_feedback, name="process_venue_feedback"),
    path("feedbacks/weather/<int:feedback_id>/process/", views.process_weather_feedback, name="process_weather_feedback"),

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
