from django.core.management.base import BaseCommand
from core.services import WeatherService


class Command(BaseCommand):
    help = "拉取全部校区天气数据"

    def handle(self, *args, **options):
        count = WeatherService.refresh_all_campus_weather()
        self.stdout.write(self.style.SUCCESS(f"已更新 {count} 个校区天气数据"))