from datetime import datetime

import requests
from django.conf import settings

from .models import Campus, WeatherRecord, WeatherAlert, Notification


class WeatherService:
    @staticmethod
    def fetch_and_store_for_campus(campus: Campus):
        params = {
            "latitude": campus.latitude,
            "longitude": campus.longitude,
            "hourly": [
                "temperature_2m",
                "apparent_temperature",
                "relative_humidity_2m",
                "precipitation",
                "wind_speed_10m",
                "weather_code",
                "is_day",
            ],
            "forecast_days": 7,
            "timezone": "Asia/Shanghai",
        }

        response = requests.get(
            settings.OPENMETEO_BASE_URL,
            params=params,
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()

        hourly = data.get("hourly", {})
        times = hourly.get("time", [])
        temperatures = hourly.get("temperature_2m", [])
        apparent_temperatures = hourly.get("apparent_temperature", [])
        humidities = hourly.get("relative_humidity_2m", [])
        precipitations = hourly.get("precipitation", [])
        wind_speeds = hourly.get("wind_speed_10m", [])
        weather_codes = hourly.get("weather_code", [])
        is_day_list = hourly.get("is_day", [])

        WeatherRecord.objects.filter(campus=campus).delete()

        created_records = []
        alert_candidates = []

        for idx, raw_time in enumerate(times):
            forecast_time = datetime.fromisoformat(raw_time)

            record = WeatherRecord.objects.create(
                campus=campus,
                forecast_time=forecast_time,
                temperature=temperatures[idx] if idx < len(temperatures) else 0,
                apparent_temperature=apparent_temperatures[idx] if idx < len(apparent_temperatures) else 0,
                humidity=humidities[idx] if idx < len(humidities) else 0,
                precipitation=precipitations[idx] if idx < len(precipitations) else 0,
                wind_speed=wind_speeds[idx] if idx < len(wind_speeds) else 0,
                weather_code=weather_codes[idx] if idx < len(weather_codes) else 0,
                is_day=bool(is_day_list[idx]) if idx < len(is_day_list) else True,
            )
            created_records.append(record)

            if record.weather_code == 95:
                alert_candidates.append((
                    "danger",
                    "雷暴预警",
                    f"{campus.name} {forecast_time:%m-%d %H:%M} 预计有雷暴天气。"
                ))
            elif record.precipitation >= 10:
                alert_candidates.append((
                    "warning",
                    "强降雨预警",
                    f"{campus.name} {forecast_time:%m-%d %H:%M} 预计有较强降雨。"
                ))
            elif record.apparent_temperature >= 35:
                alert_candidates.append((
                    "warning",
                    "高温预警",
                    f"{campus.name} {forecast_time:%m-%d %H:%M} 体感温度较高，请注意防暑。"
                ))

        WeatherAlert.objects.filter(campus=campus).update(active=False)

        for level, title, message in alert_candidates[:20]:
            WeatherAlert.objects.create(
                campus=campus,
                level=level,
                title=title,
                message=message,
                active=True,
            )

        Notification.objects.create(
            title=f"天气数据已更新：{campus.name}",
            content=f"已同步未来7天天气数据，共 {len(created_records)} 条记录。",
            notification_type="weather",
        )

        return created_records

    @staticmethod
    def refresh_all_campus_weather():
        count = 0
        for campus in Campus.objects.all():
            WeatherService.fetch_and_store_for_campus(campus)
            count += 1
        return count