from datetime import datetime


WEATHER_CODE_MAP = {
    0: "晴朗",
    1: "大体晴",
    2: "多云",
    3: "阴天",
    45: "有雾",
    48: "冻雾",
    51: "小毛雨",
    53: "毛雨",
    55: "大毛雨",
    61: "小雨",
    63: "中雨",
    65: "大雨",
    71: "小雪",
    73: "中雪",
    75: "大雪",
    80: "阵雨",
    81: "中等阵雨",
    82: "强阵雨",
    95: "雷暴",
}


def weather_text(code: int) -> str:
    return WEATHER_CODE_MAP.get(code, f"未知天气({code})")


def calculate_sport_score(weather, sport_event, indoor=False):
    score = 100.0

    if weather.temperature < sport_event.suitable_temp_min:
        score -= (sport_event.suitable_temp_min - weather.temperature) * 3

    if weather.temperature > sport_event.suitable_temp_max:
        score -= (weather.temperature - sport_event.suitable_temp_max) * 3

    if sport_event.avoid_rain and weather.precipitation > 0.2 and not indoor:
        score -= min(weather.precipitation * 10, 35)

    if weather.wind_speed > sport_event.avoid_wind_level and not indoor:
        score -= min((weather.wind_speed - sport_event.avoid_wind_level) * 4, 25)

    if weather.humidity > 90:
        score -= 8

    if sport_event.intensity == "high" and weather.apparent_temperature >= 32:
        score -= 20
    elif sport_event.intensity == "medium" and weather.apparent_temperature >= 34:
        score -= 15

    return max(round(score, 2), 0)


def risk_level(weather):
    if weather.weather_code == 95 or weather.precipitation >= 10 or weather.wind_speed >= 16:
        return "高"
    if weather.precipitation >= 2 or weather.wind_speed >= 10:
        return "中"
    return "低"


def format_hour(dt_obj: datetime):
    return dt_obj.strftime("%m-%d %H:%M")