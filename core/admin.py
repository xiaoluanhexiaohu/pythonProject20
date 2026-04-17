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
