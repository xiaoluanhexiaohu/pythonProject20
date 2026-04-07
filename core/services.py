from datetime import datetime
from typing import Dict, List, Tuple

import requests
from django.conf import settings
from django.utils import timezone

from .models import Campus, Notification, SportEvent, Suggestion, WeatherAlert, WeatherRecord
from .utils import calculate_sport_score


class WeatherService:
    """天气服务：支持多供应商实时天气拉取，并生成预警和智能建议。"""

    @staticmethod
    def fetch_and_store_for_campus(campus: Campus):
        """兼容原有逻辑：默认走 Open-Meteo。"""
        return WeatherService.fetch_and_store_for_campus_with_provider(campus, provider="open_meteo")

    @staticmethod
    def fetch_and_store_for_campus_with_provider(campus: Campus, provider: str = "qweather") -> Dict:
        provider = provider.lower()
        if provider == "qweather":
            records = WeatherService._fetch_with_qweather(campus)
        elif provider == "amap":
            records = WeatherService._fetch_with_amap(campus)
        elif provider == "open_meteo":
            records = WeatherService._fetch_with_open_meteo(campus)
        else:
            raise ValueError(f"不支持的天气供应商: {provider}")

        WeatherService._refresh_alerts_for_campus(campus)
        created_suggestions = WeatherService._refresh_suggestions_for_campus(campus)
        active_alert_count = WeatherAlert.objects.filter(campus=campus, active=True).count()

        Notification.objects.create(
            title=f"天气刷新完成：{campus.name}",
            content=(
                f"来源={provider}，写入 {len(records)} 条天气记录，"
                f"激活预警 {active_alert_count} 条，生成建议 {created_suggestions} 条。"
            ),
            notification_type="weather",
        )

        return {
            "campus": campus.name,
            "provider": provider,
            "records": len(records),
            "alerts": active_alert_count,
            "suggestions": created_suggestions,
        }

    @staticmethod
    def refresh_all_campus_weather(provider: str = "open_meteo"):
        count = 0
        for campus in Campus.objects.all():
            WeatherService.fetch_and_store_for_campus_with_provider(campus, provider=provider)
            count += 1
        return count

    @staticmethod
    def _fetch_with_open_meteo(campus: Campus) -> List[WeatherRecord]:
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

        response = requests.get(settings.OPENMETEO_BASE_URL, params=params, timeout=20)
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
        for idx, raw_time in enumerate(times):
            created_records.append(
                WeatherRecord.objects.create(
                    campus=campus,
                    forecast_time=datetime.fromisoformat(raw_time),
                    temperature=temperatures[idx] if idx < len(temperatures) else 0,
                    apparent_temperature=apparent_temperatures[idx] if idx < len(apparent_temperatures) else 0,
                    humidity=humidities[idx] if idx < len(humidities) else 0,
                    precipitation=precipitations[idx] if idx < len(precipitations) else 0,
                    wind_speed=wind_speeds[idx] if idx < len(wind_speeds) else 0,
                    weather_code=weather_codes[idx] if idx < len(weather_codes) else 0,
                    is_day=bool(is_day_list[idx]) if idx < len(is_day_list) else True,
                )
            )

        return created_records

    @staticmethod
    def _fetch_with_qweather(campus: Campus) -> List[WeatherRecord]:
        key = getattr(settings, "QWEATHER_API_KEY", "")
        host = getattr(settings, "QWEATHER_BASE_URL", "https://devapi.qweather.com")
        if not key:
            raise ValueError("未配置 QWeather API Key（QWEATHER_API_KEY）")

        geo_resp = requests.get(
            f"{host}/geo/v2/city/lookup",
            params={"location": campus.location or campus.name, "key": key},
            timeout=20,
        )
        geo_resp.raise_for_status()
        geo_data = geo_resp.json()
        if geo_data.get("code") != "200" or not geo_data.get("location"):
            raise ValueError(f"QWeather 地理解析失败: {geo_data}")

        location_id = geo_data["location"][0]["id"]

        now_resp = requests.get(
            f"{host}/v7/weather/now",
            params={"location": location_id, "key": key},
            timeout=20,
        )
        now_resp.raise_for_status()
        now_data = now_resp.json()
        if now_data.get("code") != "200" or not now_data.get("now"):
            raise ValueError(f"QWeather 实时天气失败: {now_data}")

        now = now_data["now"]
        record = WeatherRecord.objects.create(
            campus=campus,
            forecast_time=timezone.localtime(),
            temperature=float(now.get("temp", 0)),
            apparent_temperature=float(now.get("feelsLike", 0)),
            humidity=float(now.get("humidity", 0)),
            precipitation=float(now.get("precip", 0)),
            wind_speed=float(now.get("windSpeed", 0)),
            weather_code=int(now.get("icon", 0)),
            is_day=(now.get("isDay", "1") == "1"),
        )

        return [record]

    @staticmethod
    def _fetch_with_amap(campus: Campus) -> List[WeatherRecord]:
        key = getattr(settings, "AMAP_API_KEY", "")
        host = getattr(settings, "AMAP_BASE_URL", "https://restapi.amap.com")
        if not key:
            raise ValueError("未配置高德 API Key（AMAP_API_KEY）")

        geo_resp = requests.get(
            f"{host}/v3/geocode/geo",
            params={"key": key, "address": campus.location or campus.name},
            timeout=20,
        )
        geo_resp.raise_for_status()
        geo_data = geo_resp.json()
        if geo_data.get("status") != "1" or not geo_data.get("geocodes"):
            raise ValueError(f"高德地理编码失败: {geo_data}")

        adcode = geo_data["geocodes"][0].get("adcode")
        if not adcode:
            raise ValueError("高德返回 adcode 为空")

        weather_resp = requests.get(
            f"{host}/v3/weather/weatherInfo",
            params={"key": key, "city": adcode, "extensions": "base"},
            timeout=20,
        )
        weather_resp.raise_for_status()
        weather_data = weather_resp.json()
        if weather_data.get("status") != "1" or not weather_data.get("lives"):
            raise ValueError(f"高德实时天气失败: {weather_data}")

        live = weather_data["lives"][0]
        record = WeatherRecord.objects.create(
            campus=campus,
            forecast_time=timezone.localtime(),
            temperature=float(live.get("temperature", 0)),
            apparent_temperature=float(live.get("temperature_float", live.get("temperature", 0))),
            humidity=float(live.get("humidity", 0)),
            precipitation=0,
            wind_speed=float(live.get("windpower", 0) or 0),
            weather_code=WeatherService._amap_weather_to_code(live.get("weather", "")),
            is_day=True,
        )

        return [record]

    @staticmethod
    def _amap_weather_to_code(weather_text: str) -> int:
        mapping = {
            "晴": 0,
            "多云": 2,
            "阴": 3,
            "小雨": 61,
            "中雨": 63,
            "大雨": 65,
            "雷阵雨": 95,
            "阵雨": 80,
            "小雪": 71,
            "中雪": 73,
            "大雪": 75,
        }
        for key, code in mapping.items():
            if key in weather_text:
                return code
        return 0

    @staticmethod
    def _refresh_alerts_for_campus(campus: Campus):
        WeatherAlert.objects.filter(campus=campus).update(active=False)
        alerts: List[Tuple[str, str, str]] = []

        for record in WeatherRecord.objects.filter(campus=campus).order_by("forecast_time")[:48]:
            if record.weather_code == 95:
                alerts.append(("danger", "雷暴预警", f"{campus.name} 检测到雷暴风险，请暂停户外活动。"))
            elif record.precipitation >= 10:
                alerts.append(("warning", "暴雨预警", f"{campus.name} 降雨量较大，建议调整活动安排。"))
            elif record.wind_speed >= 16:
                alerts.append(("warning", "大风预警", f"{campus.name} 风速较高，户外活动注意安全。"))
            elif record.apparent_temperature >= 35:
                alerts.append(("warning", "高温预警", f"{campus.name} 体感温度偏高，请注意防暑降温。"))

        for level, title, message in alerts[:20]:
            WeatherAlert.objects.create(campus=campus, level=level, title=title, message=message, active=True)
            Notification.objects.create(title=title, content=message, notification_type="weather")

    @staticmethod
    def _refresh_suggestions_for_campus(campus: Campus) -> int:
        Suggestion.objects.filter(campus=campus).delete()

        records = WeatherRecord.objects.filter(campus=campus).order_by("forecast_time")[:72]
        events = SportEvent.objects.all()
        total = 0

        for event in events:
            for record in records:
                score = calculate_sport_score(record, event)
                if score < 60:
                    continue
                Suggestion.objects.create(
                    campus=campus,
                    sport_event=event,
                    suggest_date=record.forecast_time.date(),
                    suggest_time=record.forecast_time.time().replace(second=0, microsecond=0),
                    score=score,
                    weather_summary=f"温度 {record.temperature}℃ / 湿度 {record.humidity}%",
                    reason=f"当前天气适合 {event.name}，综合评分 {score}",
                )
                total += 1

        return total
