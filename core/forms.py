from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from .models import (
    Campus,
    Venue,
    SportEvent,
    Meet,
    VenueFeedback,
    WeatherFeedback,
    UserProfile,
    ActivityRegistration,
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
    planned_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text="原计划时间可选；不填写则由系统自动选择最佳时间。",
    )
    planned_start_time = forms.TimeField(required=False, widget=forms.TimeInput(attrs={"type": "time"}))
    planned_end_time = forms.TimeField(required=False, widget=forms.TimeInput(attrs={"type": "time"}))

    class Meta:
        model = Meet
        fields = [
            "title",
            "campus",
            "venue",
            "sport_event",
            "expected_people",
            "activity_duration_minutes",
            "planned_date",
            "planned_start_time",
            "planned_end_time",
            "organizer",
            "contact",
            "note",
            "status",
        ]
        help_texts = {
            "activity_duration_minutes": "必填，单位分钟，必须大于 0。",
            "planned_date": "原计划时间可选；不填写则由系统自动选择最佳时间。",
        }

    def clean_activity_duration_minutes(self):
        value = self.cleaned_data.get("activity_duration_minutes")
        if value is None or value <= 0:
            raise forms.ValidationError("活动总时长必须大于 0。")
        return value

    def clean(self):
        cleaned_data = super().clean()
        planned_date = cleaned_data.get("planned_date")
        start_time = cleaned_data.get("planned_start_time")
        end_time = cleaned_data.get("planned_end_time")

        if start_time and not planned_date:
            self.add_error("planned_date", "填写原计划开始时间时，必须同时填写原计划日期。")
        if end_time and not start_time:
            self.add_error("planned_start_time", "填写原计划结束时间时，必须同时填写原计划开始时间。")
        if start_time and end_time and end_time <= start_time:
            self.add_error("planned_end_time", "原计划结束时间必须晚于原计划开始时间。")
        return cleaned_data


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=False, label="邮箱")
    display_name = forms.CharField(required=False, max_length=100, label="显示名称")

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("username", "email", "display_name", "password1", "password2")


class UserEditForm(forms.Form):
    ROLE_CHOICES = [
        (UserProfile.ROLE_STUDENT, "学生"),
        (UserProfile.ROLE_TEACHER, "教师"),
    ]

    display_name = forms.CharField(required=False, label="显示名称", max_length=100)
    role = forms.ChoiceField(choices=ROLE_CHOICES, label="角色")
    is_active = forms.BooleanField(required=False, label="是否启用")

    can_view_weather = forms.BooleanField(required=False, label="学生-查看天气")
    can_view_alerts = forms.BooleanField(required=False, label="学生-查看预警")
    can_view_suggestions = forms.BooleanField(required=False, label="学生-查看智能建议")
    can_view_schedule = forms.BooleanField(required=False, label="学生-查看排程")
    can_register_activity = forms.BooleanField(required=False, label="学生-活动报名")
    can_submit_feedback = forms.BooleanField(required=False, label="学生-提交反馈")
    can_view_own_notifications = forms.BooleanField(required=False, label="学生-查看个人通知")

    can_manage_meets = forms.BooleanField(required=False, label="教师-活动管理")
    can_manage_registrations = forms.BooleanField(required=False, label="教师-报名审核")
    can_manage_feedback = forms.BooleanField(required=False, label="教师-反馈处理")
    can_generate_suggestions = forms.BooleanField(required=False, label="教师-生成智能建议")
    can_generate_schedule = forms.BooleanField(required=False, label="教师-生成智能排程")
    can_view_statistics = forms.BooleanField(required=False, label="教师-查看统计分析")
    can_send_notifications = forms.BooleanField(required=False, label="教师-发布通知")


class RegistrationRejectForm(forms.ModelForm):
    class Meta:
        model = ActivityRegistration
        fields = ["review_reason"]
        labels = {"review_reason": "审核意见"}
        widgets = {
            "review_reason": forms.Textarea(attrs={"rows": 4, "placeholder": "请输入不通过原因（可选）"}),
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
