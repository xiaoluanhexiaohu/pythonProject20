from datetime import date, time, timedelta

from django.core.management.base import BaseCommand

from core.models import Campus, Venue, SportEvent, Meet, Notification


class Command(BaseCommand):
    help = "初始化演示数据"

    def handle(self, *args, **options):
        main_campus, _ = Campus.objects.get_or_create(
            name="主校区",
            defaults={
                "location": "上海市中心校区",
                "latitude": 31.2304,
                "longitude": 121.4737,
                "description": "默认演示校区",
            },
        )

        west_campus, _ = Campus.objects.get_or_create(
            name="西校区",
            defaults={
                "location": "上海市西部校区",
                "latitude": 31.2240,
                "longitude": 121.4300,
                "description": "第二演示校区",
            },
        )

        Venue.objects.get_or_create(
            campus=main_campus,
            name="田径场",
            defaults={
                "venue_type": "户外田径",
                "capacity": 300,
                "has_lighting": True,
            },
        )

        Venue.objects.get_or_create(
            campus=main_campus,
            name="体育馆",
            defaults={
                "venue_type": "综合馆",
                "capacity": 500,
                "indoor": True,
            },
        )

        Venue.objects.get_or_create(
            campus=west_campus,
            name="篮球场A",
            defaults={
                "venue_type": "篮球",
                "capacity": 80,
                "has_lighting": True,
            },
        )

        Venue.objects.get_or_create(
            campus=west_campus,
            name="羽毛球馆",
            defaults={
                "venue_type": "羽毛球",
                "capacity": 120,
                "indoor": True,
            },
        )

        running, _ = SportEvent.objects.get_or_create(
            name="校园跑",
            defaults={
                "suitable_temp_min": 10,
                "suitable_temp_max": 24,
                "avoid_rain": True,
                "avoid_wind_level": 10,
                "intensity": "medium",
                "calories_per_hour": 500,
            },
        )

        basketball, _ = SportEvent.objects.get_or_create(
            name="篮球",
            defaults={
                "suitable_temp_min": 12,
                "suitable_temp_max": 30,
                "avoid_rain": True,
                "avoid_wind_level": 12,
                "intensity": "high",
                "calories_per_hour": 650,
            },
        )

        badminton, _ = SportEvent.objects.get_or_create(
            name="羽毛球",
            defaults={
                "suitable_temp_min": 10,
                "suitable_temp_max": 30,
                "avoid_rain": False,
                "avoid_wind_level": 20,
                "intensity": "medium",
                "calories_per_hour": 420,
            },
        )

        tomorrow = date.today() + timedelta(days=1)

        Meet.objects.get_or_create(
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

        Meet.objects.get_or_create(
            title="学院篮球友谊赛",
            defaults={
                "campus": west_campus,
                "sport_event": basketball,
                "expected_people": 60,
                "planned_date": tomorrow,
                "planned_start_time": time(16, 0),
                "planned_end_time": time(18, 0),
                "organizer": "学生会",
                "contact": "13900000000",
                "status": "pending",
            },
        )

        Meet.objects.get_or_create(
            title="羽毛球训练营",
            defaults={
                "campus": west_campus,
                "sport_event": badminton,
                "expected_people": 30,
                "planned_date": tomorrow + timedelta(days=1),
                "planned_start_time": time(19, 0),
                "planned_end_time": time(21, 0),
                "organizer": "社团联合会",
                "contact": "13700000000",
                "status": "pending",
            },
        )

        Notification.objects.get_or_create(
            title="系统初始化完成",
            defaults={
                "content": "演示数据已写入，可继续执行 fetch_weather 获取天气。",
                "notification_type": "system",
            },
        )

        self.stdout.write(self.style.SUCCESS("演示数据初始化完成"))