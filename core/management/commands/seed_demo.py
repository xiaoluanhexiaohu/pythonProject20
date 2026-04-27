from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import (
    ActivityRegistration,
    Campus,
    Meet,
    Notification,
    SportEvent,
    UserProfile,
    Venue,
    VenueFeedback,
    WeatherFeedback,
    WeatherRecord,
)


class Command(BaseCommand):
    help = "初始化演示数据"

    def handle(self, *args, **options):
        user_model = get_user_model()

        admin_user, _ = user_model.objects.get_or_create(username="admin_demo", defaults={"is_staff": True, "is_superuser": True})
        if not admin_user.check_password("admin123456"):
            admin_user.set_password("admin123456")
            admin_user.save(update_fields=["password"])
        UserProfile.objects.update_or_create(
            user=admin_user,
            defaults={"role": UserProfile.ROLE_ADMIN, "display_name": "系统管理员"},
        )

        teacher_user, _ = user_model.objects.get_or_create(username="teacher_demo")
        if not teacher_user.check_password("teacher123456"):
            teacher_user.set_password("teacher123456")
            teacher_user.save(update_fields=["password"])
        UserProfile.objects.update_or_create(
            user=teacher_user,
            defaults={
                "role": UserProfile.ROLE_TEACHER,
                "display_name": "演示教师",
                "can_manage_meets": True,
                "can_manage_registrations": True,
                "can_manage_feedback": True,
                "can_generate_suggestions": True,
                "can_generate_schedule": True,
                "can_view_statistics": True,
                "can_send_notifications": True,
                "can_view_weather": True,
            },
        )

        student_user, _ = user_model.objects.get_or_create(username="student_demo")
        if not student_user.check_password("student123456"):
            student_user.set_password("student123456")
            student_user.save(update_fields=["password"])
        UserProfile.objects.update_or_create(
            user=student_user,
            defaults={
                "role": UserProfile.ROLE_STUDENT,
                "display_name": "演示学生",
                "can_view_weather": True,
                "can_view_alerts": True,
                "can_view_suggestions": True,
                "can_view_schedule": True,
                "can_register_activity": True,
                "can_submit_feedback": True,
                "can_view_own_notifications": True,
            },
        )

        main_campus, _ = Campus.objects.get_or_create(name="主校区", defaults={"location": "上海市中心校区", "latitude": 31.2304, "longitude": 121.4737, "description": "默认演示校区"})
        west_campus, _ = Campus.objects.get_or_create(name="西校区", defaults={"location": "上海市西部校区", "latitude": 31.2240, "longitude": 121.4300, "description": "第二演示校区"})

        Venue.objects.get_or_create(campus=main_campus, name="田径场", defaults={"venue_type": "户外田径", "capacity": 300, "has_lighting": True})
        Venue.objects.get_or_create(campus=main_campus, name="体育馆", defaults={"venue_type": "综合馆", "capacity": 500, "indoor": True})
        Venue.objects.get_or_create(campus=west_campus, name="篮球场A", defaults={"venue_type": "篮球", "capacity": 80, "has_lighting": True})

        running, _ = SportEvent.objects.get_or_create(name="校园跑", defaults={"suitable_temp_min": 10, "suitable_temp_max": 24, "avoid_rain": True, "avoid_wind_level": 10, "intensity": "medium", "calories_per_hour": 500})
        tomorrow = date.today() + timedelta(days=1)
        running_meet, _ = Meet.objects.get_or_create(
            title="春季校园跑活动",
            defaults={
                "campus": main_campus,
                "sport_event": running,
                "expected_people": 120,
                "planned_date": tomorrow,
                "planned_start_time": time(7, 0),
                "planned_end_time": time(8, 30),
                "organizer": "体育部",
                "contact": "13800000000",
                "status": "pending",
            },
        )

        ActivityRegistration.objects.update_or_create(
            student=student_user,
            meet=running_meet,
            defaults={"status": "pending", "apply_reason": "演示报名记录"},
        )

        Notification.objects.get_or_create(
            title="新的活动报名待审核",
            content=f"学生 {student_user.username} 提交了《{running_meet.title}》的报名申请。",
            defaults={"notification_type": "registration", "target_role": "teacher", "source_module": "activity_registration"},
        )
        Notification.objects.get_or_create(
            title="活动报名已提交",
            content=f"你已提交《{running_meet.title}》的报名申请，请等待教师审核。",
            defaults={"notification_type": "registration", "recipient": student_user, "target_role": "student", "source_module": "activity_registration"},
        )

        demo_venue = Venue.objects.filter(campus=main_campus).first()
        if demo_venue:
            VenueFeedback.objects.update_or_create(student=student_user, venue=demo_venue, content="场地整体不错，建议补充更多夜间照明。", defaults={"status": "pending"})

        weather_record = WeatherRecord.objects.filter(campus=main_campus).order_by("forecast_time").first()
        if not weather_record:
            weather_record = WeatherRecord.objects.create(campus=main_campus, forecast_time=timezone.now() + timedelta(hours=1), temperature=23, apparent_temperature=24, humidity=55, precipitation=0, wind_speed=3, weather_code=1, is_day=True)

        WeatherFeedback.objects.update_or_create(student=student_user, campus=main_campus, content="今天体感偏热，建议增加防暑提醒。", defaults={"weather_record": weather_record, "status": "pending"})
        self.stdout.write(self.style.SUCCESS("演示数据初始化完成"))
