from django.contrib import admin

from .models import (
    ActivityRegistration,
    Campus,
    FinalSchedule,
    Meet,
    Notification,
    NotificationRead,
    OperationLog,
    SportEvent,
    Suggestion,
    UserProfile,
    Venue,
    VenueFeedback,
    WeatherAlert,
    WeatherFeedback,
    WeatherRecord,
)

admin.site.register(Campus)
admin.site.register(Venue)
admin.site.register(SportEvent)
admin.site.register(Meet)
admin.site.register(WeatherRecord)
admin.site.register(WeatherAlert)
admin.site.register(Suggestion)
admin.site.register(FinalSchedule)
admin.site.register(OperationLog)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user", "role", "display_name", "can_view_weather", "can_view_alerts", "can_view_suggestions",
        "can_view_schedule", "can_register_activity", "can_submit_feedback", "can_view_own_notifications",
        "can_manage_meets", "can_manage_registrations", "can_manage_feedback", "can_generate_suggestions",
        "can_generate_schedule", "can_view_statistics", "can_send_notifications",
    )
    list_filter = ("role",)
    search_fields = ("user__username", "display_name")


@admin.register(ActivityRegistration)
class ActivityRegistrationAdmin(admin.ModelAdmin):
    list_display = ("student", "meet", "status", "reviewed_by", "reviewed_at", "created_at")
    list_filter = ("status",)
    search_fields = ("student__username", "meet__title")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "notification_type", "recipient", "target_role", "source_module", "created_by", "created_at")
    list_filter = ("notification_type", "target_role", "source_module")
    search_fields = ("title", "content")


@admin.register(NotificationRead)
class NotificationReadAdmin(admin.ModelAdmin):
    list_display = ("user", "notification", "is_read", "created_at")
    list_filter = ("is_read",)


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
