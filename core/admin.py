from django.contrib import admin
from .models import (
    Campus,
    Venue,
    SportEvent,
    Meet,
    WeatherRecord,
    WeatherAlert,
    Suggestion,
    FinalSchedule,
    Notification,
    UserProfile,
    OperationLog,
    ActivityRegistration,
    VenueFeedback,
    WeatherFeedback,
)

admin.site.register(Campus)
admin.site.register(Venue)
admin.site.register(SportEvent)
admin.site.register(Meet)
admin.site.register(WeatherRecord)
admin.site.register(WeatherAlert)
admin.site.register(Suggestion)
admin.site.register(FinalSchedule)
admin.site.register(Notification)
admin.site.register(UserProfile)
admin.site.register(OperationLog)


@admin.register(ActivityRegistration)
class ActivityRegistrationAdmin(admin.ModelAdmin):
    list_display = ("student", "meet", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("student__username", "meet__title")


@admin.register(VenueFeedback)
class VenueFeedbackAdmin(admin.ModelAdmin):
    list_display = ("student", "venue", "status", "created_at")
    list_filter = ("status", "venue__campus")
    search_fields = ("student__username", "venue__name", "content")


@admin.register(WeatherFeedback)
class WeatherFeedbackAdmin(admin.ModelAdmin):
    list_display = ("student", "campus", "status", "created_at")
    list_filter = ("status", "campus")
    search_fields = ("student__username", "campus__name", "content")
