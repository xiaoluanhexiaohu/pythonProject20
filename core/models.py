from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        abstract = True


class Campus(TimeStampedModel):
    name = models.CharField(max_length=100, unique=True, verbose_name="校区名称")
    location = models.CharField(max_length=255, blank=True, verbose_name="位置")
    latitude = models.FloatField(default=31.2304, verbose_name="纬度")
    longitude = models.FloatField(default=121.4737, verbose_name="经度")
    description = models.TextField(blank=True, verbose_name="描述")

    class Meta:
        verbose_name = "校区"
        verbose_name_plural = "校区"
        ordering = ["id"]

    def __str__(self):
        return self.name


class Venue(TimeStampedModel):
    VENUE_STATUS_CHOICES = [
        ("available", "可用"),
        ("maintenance", "维护中"),
        ("closed", "关闭"),
    ]

    campus = models.ForeignKey(
        Campus,
        on_delete=models.CASCADE,
        related_name="venues",
        verbose_name="所属校区"
    )
    name = models.CharField(max_length=100, verbose_name="场地名称")
    venue_type = models.CharField(max_length=100, verbose_name="场地类型")
    capacity = models.PositiveIntegerField(default=50, verbose_name="容量")
    status = models.CharField(
        max_length=20,
        choices=VENUE_STATUS_CHOICES,
        default="available",
        verbose_name="状态"
    )
    indoor = models.BooleanField(default=False, verbose_name="是否室内")
    has_lighting = models.BooleanField(default=False, verbose_name="是否有照明")
    description = models.TextField(blank=True, verbose_name="描述")

    class Meta:
        verbose_name = "场地"
        verbose_name_plural = "场地"
        ordering = ["campus_id", "id"]

    def __str__(self):
        return f"{self.campus.name}-{self.name}"


class SportEvent(TimeStampedModel):
    intensity_choices = [
        ("low", "低强度"),
        ("medium", "中强度"),
        ("high", "高强度"),
    ]

    name = models.CharField(max_length=100, unique=True, verbose_name="项目名称")
    suitable_temp_min = models.IntegerField(default=12, verbose_name="适宜最低温")
    suitable_temp_max = models.IntegerField(default=28, verbose_name="适宜最高温")
    avoid_rain = models.BooleanField(default=True, verbose_name="是否避雨")
    avoid_wind_level = models.FloatField(default=8.0, verbose_name="最大适宜风速")
    intensity = models.CharField(
        max_length=20,
        choices=intensity_choices,
        default="medium",
        verbose_name="强度"
    )
    calories_per_hour = models.PositiveIntegerField(default=300, verbose_name="每小时热量消耗")
    description = models.TextField(blank=True, verbose_name="描述")

    class Meta:
        verbose_name = "运动项目"
        verbose_name_plural = "运动项目"
        ordering = ["id"]

    def __str__(self):
        return self.name


class Meet(TimeStampedModel):
    STATUS_CHOICES = [
        ("pending", "待安排"),
        ("scheduled", "已排程"),
        ("completed", "已完成"),
        ("cancelled", "已取消"),
    ]

    title = models.CharField(max_length=200, verbose_name="活动名称")
    campus = models.ForeignKey(Campus, on_delete=models.CASCADE, related_name="meets", verbose_name="校区")
    venue = models.ForeignKey(
        Venue,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="meets",
        verbose_name="场地"
    )
    sport_event = models.ForeignKey(
        SportEvent,
        on_delete=models.CASCADE,
        related_name="meets",
        verbose_name="运动项目"
    )
    expected_people = models.PositiveIntegerField(default=20, verbose_name="预计人数")
    planned_date = models.DateField(verbose_name="计划日期")
    planned_start_time = models.TimeField(verbose_name="计划开始时间")
    planned_end_time = models.TimeField(verbose_name="计划结束时间")
    organizer = models.CharField(max_length=100, blank=True, verbose_name="组织者")
    contact = models.CharField(max_length=50, blank=True, verbose_name="联系方式")
    note = models.TextField(blank=True, verbose_name="备注")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", verbose_name="状态")

    class Meta:
        verbose_name = "活动/比赛"
        verbose_name_plural = "活动/比赛"
        ordering = ["-planned_date", "planned_start_time"]

    def __str__(self):
        return self.title


class WeatherRecord(TimeStampedModel):
    campus = models.ForeignKey(
        Campus,
        on_delete=models.CASCADE,
        related_name="weather_records",
        verbose_name="校区"
    )
    forecast_time = models.DateTimeField(verbose_name="预报时间")
    temperature = models.FloatField(default=0, verbose_name="温度")
    apparent_temperature = models.FloatField(default=0, verbose_name="体感温度")
    humidity = models.FloatField(default=0, verbose_name="湿度")
    precipitation = models.FloatField(default=0, verbose_name="降水")
    wind_speed = models.FloatField(default=0, verbose_name="风速")
    weather_code = models.IntegerField(default=0, verbose_name="天气编码")
    is_day = models.BooleanField(default=True, verbose_name="是否白天")

    class Meta:
        verbose_name = "天气记录"
        verbose_name_plural = "天气记录"
        ordering = ["forecast_time"]
        unique_together = ("campus", "forecast_time")

    def __str__(self):
        return f"{self.campus.name}-{self.forecast_time:%Y-%m-%d %H:%M}"


class WeatherAlert(TimeStampedModel):
    ALERT_LEVEL_CHOICES = [
        ("info", "提示"),
        ("warning", "警告"),
        ("danger", "危险"),
    ]

    campus = models.ForeignKey(
        Campus,
        on_delete=models.CASCADE,
        related_name="alerts",
        verbose_name="校区"
    )
    title = models.CharField(max_length=200, verbose_name="预警标题")
    level = models.CharField(
        max_length=20,
        choices=ALERT_LEVEL_CHOICES,
        default="info",
        verbose_name="预警级别"
    )
    message = models.TextField(verbose_name="预警内容")
    alert_time = models.DateTimeField(default=timezone.now, verbose_name="预警时间")
    active = models.BooleanField(default=True, verbose_name="是否有效")

    class Meta:
        verbose_name = "天气预警"
        verbose_name_plural = "天气预警"
        ordering = ["-alert_time"]

    def __str__(self):
        return self.title


class Suggestion(TimeStampedModel):
    campus = models.ForeignKey(
        Campus,
        on_delete=models.CASCADE,
        related_name="suggestions",
        verbose_name="校区"
    )
    sport_event = models.ForeignKey(
        SportEvent,
        on_delete=models.CASCADE,
        related_name="suggestions",
        verbose_name="运动项目"
    )
    suggest_date = models.DateField(verbose_name="推荐日期")
    suggest_time = models.TimeField(verbose_name="推荐时间")
    score = models.FloatField(default=0, verbose_name="推荐分数")
    weather_summary = models.CharField(max_length=255, blank=True, verbose_name="天气概述")
    reason = models.TextField(blank=True, verbose_name="推荐原因")

    class Meta:
        verbose_name = "智能建议"
        verbose_name_plural = "智能建议"
        ordering = ["-score", "suggest_date", "suggest_time"]

    def __str__(self):
        return f"{self.campus.name}-{self.sport_event.name}-{self.suggest_date} {self.suggest_time}"


class FinalSchedule(TimeStampedModel):
    meet = models.OneToOneField(
        Meet,
        on_delete=models.CASCADE,
        related_name="final_schedule",
        verbose_name="活动"
    )
    campus = models.ForeignKey(Campus, on_delete=models.CASCADE, related_name="final_schedules", verbose_name="校区")
    venue = models.ForeignKey(Venue, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="场地")
    scheduled_date = models.DateField(verbose_name="排程日期")
    scheduled_start_time = models.TimeField(verbose_name="开始时间")
    scheduled_end_time = models.TimeField(verbose_name="结束时间")
    weather_risk = models.CharField(max_length=50, default="低", verbose_name="天气风险")
    notes = models.TextField(blank=True, verbose_name="说明")

    class Meta:
        verbose_name = "最终排程"
        verbose_name_plural = "最终排程"
        ordering = ["-scheduled_date", "scheduled_start_time"]

    def __str__(self):
        return f"{self.meet.title}-{self.scheduled_date}"


class Notification(TimeStampedModel):
    TYPE_CHOICES = [
        ("system", "系统"),
        ("weather", "天气"),
        ("schedule", "排程"),
    ]

    title = models.CharField(max_length=200, verbose_name="标题")
    content = models.TextField(verbose_name="内容")
    notification_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default="system",
        verbose_name="通知类型"
    )
    is_read = models.BooleanField(default=False, verbose_name="是否已读")

    class Meta:
        verbose_name = "系统通知"
        verbose_name_plural = "系统通知"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class UserProfile(TimeStampedModel):
    ROLE_ADMIN = "admin"
    ROLE_TEACHER = "teacher"
    ROLE_STUDENT = "student"
    ROLE_CHOICES = [
        (ROLE_ADMIN, "管理员"),
        (ROLE_TEACHER, "教师"),
        (ROLE_STUDENT, "学生"),
    ]

    user = models.OneToOneField(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name="profile",
        verbose_name="用户",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_STUDENT, verbose_name="角色")
    display_name = models.CharField(max_length=100, blank=True, verbose_name="显示名称")

    class Meta:
        verbose_name = "用户角色"
        verbose_name_plural = "用户角色"

    def __str__(self):
        return f"{self.user.username}({self.get_role_display()})"


class OperationLog(TimeStampedModel):
    user = models.ForeignKey(
        get_user_model(),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="operation_logs",
        verbose_name="操作用户",
    )
    role = models.CharField(max_length=20, blank=True, verbose_name="角色")
    action = models.CharField(max_length=120, blank=True, verbose_name="操作名称")
    method = models.CharField(max_length=10, verbose_name="请求方法")
    path = models.CharField(max_length=255, verbose_name="请求路径")
    status_code = models.PositiveIntegerField(default=200, verbose_name="状态码")
    ip_address = models.CharField(max_length=64, blank=True, verbose_name="IP地址")
    detail = models.TextField(blank=True, verbose_name="详情")

    class Meta:
        verbose_name = "操作日志"
        verbose_name_plural = "操作日志"
        ordering = ["-created_at"]

    def __str__(self):
        actor = self.user.username if self.user else "匿名用户"
        return f"{actor} {self.method} {self.path}"


@receiver(post_save, sender=get_user_model())
def ensure_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance, display_name=instance.get_full_name() or instance.username)
    elif not hasattr(instance, "profile"):
        UserProfile.objects.create(user=instance, display_name=instance.get_full_name() or instance.username)
