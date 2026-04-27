from django import forms
from .models import (
    Campus,
    Venue,
    SportEvent,
    Meet,
    VenueFeedback,
    WeatherFeedback,
)


class CampusForm(forms.ModelForm):
    class Meta:
        model = Campus
        fields = ["name", "location", "latitude", "longitude", "description"]


class VenueForm(forms.ModelForm):
    class Meta:
        model = Venue
        fields = ["campus", "name", "venue_type", "capacity", "status", "indoor", "has_lighting", "description"]


class SportEventForm(forms.ModelForm):
    class Meta:
        model = SportEvent
        fields = [
            "name",
            "suitable_temp_min",
            "suitable_temp_max",
            "avoid_rain",
            "avoid_wind_level",
            "intensity",
            "calories_per_hour",
            "description",
        ]


class MeetForm(forms.ModelForm):
    class Meta:
        model = Meet
        fields = [
            "title",
            "campus",
            "venue",
            "sport_event",
            "expected_people",
            "planned_date",
            "planned_start_time",
            "planned_end_time",
            "organizer",
            "contact",
            "note",
            "status",
        ]
        widgets = {
            "planned_date": forms.DateInput(attrs={"type": "date"}),
            "planned_start_time": forms.TimeInput(attrs={"type": "time"}),
            "planned_end_time": forms.TimeInput(attrs={"type": "time"}),
        }


class VenueFeedbackForm(forms.ModelForm):
    class Meta:
        model = VenueFeedback
        fields = ["venue", "content"]


class WeatherFeedbackForm(forms.ModelForm):
    class Meta:
        model = WeatherFeedback
        fields = ["campus", "weather_record", "content"]


class VenueFeedbackReplyForm(forms.ModelForm):
    class Meta:
        model = VenueFeedback
        fields = ["status", "reply"]


class WeatherFeedbackReplyForm(forms.ModelForm):
    class Meta:
        model = WeatherFeedback
        fields = ["status", "reply"]
