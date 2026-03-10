import csv

from django.contrib import messages
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from .forms import CampusForm, VenueForm, SportEventForm, MeetForm
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
)
from .services import WeatherService
from .utils import calculate_sport_score, risk_level, weather_text


def dashboard(request):
    context = {
        "campus_count": Campus.objects.count(),
        "venue_count": Venue.objects.count(),
        "event_count": SportEvent.objects.count(),
        "meet_count": Meet.objects.count(),
        "schedule_count": FinalSchedule.objects.count(),
        "alert_count": WeatherAlert.objects.filter(active=True).count(),
        "latest_notifications": Notification.objects.all()[:6],
    }
    return render(request, "core/dashboard.html", context)


def campus_list(request):
    return render(request, "core/campus_list.html", {"items": Campus.objects.all()})


def campus_create(request):
    form = CampusForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, "校区创建成功")
        return redirect("campus_list")
    return render(request, "core/campus_form.html", {"form": form, "title": "新增校区"})


def venue_list(request):
    items = Venue.objects.select_related("campus").all()
    return render(request, "core/venue_list.html", {"items": items})


def venue_create(request):
    form = VenueForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, "场地创建成功")
        return redirect("venue_list")
    return render(request, "core/venue_form.html", {"form": form, "title": "新增场地"})


def event_list(request):
    return render(request, "core/event_list.html", {"items": SportEvent.objects.all()})


def event_create(request):
    form = SportEventForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, "运动项目创建成功")
        return redirect("event_list")
    return render(request, "core/event_form.html", {"form": form, "title": "新增运动项目"})


def meet_list(request):
    items = Meet.objects.select_related("campus", "venue", "sport_event").all()
    return render(request, "core/meet_list.html", {"items": items})


def meet_create(request):
    form = MeetForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, "活动创建成功")
        return redirect("meet_list")
    return render(request, "core/meet_form.html", {"form": form, "title": "新增活动"})


def weather_center(request):
    campus_id = request.GET.get("campus")
    campuses = Campus.objects.all()
    current_campus = campuses.first()

    if campus_id:
        current_campus = get_object_or_404(Campus, id=campus_id)

    next_24h = []
    next_7d = []

    if current_campus:
        records = list(
            WeatherRecord.objects.filter(campus=current_campus).order_by("forecast_time")
        )
        next_24h = records[:24]
        next_7d = records[:24 * 7:24]

        for item in next_24h:
            item.weather_name = weather_text(item.weather_code)

        for item in next_7d:
            item.weather_name = weather_text(item.weather_code)

    context = {
        "campuses": campuses,
        "current_campus": current_campus,
        "next_24h": next_24h,
        "next_7d": next_7d,
    }
    return render(request, "core/weather_center.html", context)

def refresh_weather(request):
    count = WeatherService.refresh_all_campus_weather()
    messages.success(request, f"天气更新成功，已同步 {count} 个校区")
    return redirect("weather_center")


def alert_center(request):
    items = WeatherAlert.objects.select_related("campus").filter(active=True)
    return render(request, "core/alert_center.html", {"items": items})


def generate_suggestions(request):
    Suggestion.objects.all().delete()
    campuses = Campus.objects.all()
    events = SportEvent.objects.all()

    total = 0
    for campus in campuses:
        weather_records = WeatherRecord.objects.filter(campus=campus).order_by("forecast_time")[:72]
        for event in events:
            for record in weather_records:
                score = calculate_sport_score(record, event)
                if score >= 60:
                    Suggestion.objects.create(
                        campus=campus,
                        sport_event=event,
                        suggest_date=record.forecast_time.date(),
                        suggest_time=record.forecast_time.time().replace(second=0, microsecond=0),
                        score=score,
                        weather_summary=f"{weather_text(record.weather_code)} {record.temperature}℃",
                        reason=f"温度、降水和风速较适合 {event.name}，综合评分 {score}",
                    )
                    total += 1

    Notification.objects.create(
        title="智能建议已生成",
        content=f"系统已重新生成 {total} 条运动建议。",
        notification_type="system",
    )
    messages.success(request, f"已生成 {total} 条智能建议")
    return redirect("suggestion_list")


def suggestion_list(request):
    items = Suggestion.objects.select_related("campus", "sport_event").all()[:200]
    return render(request, "core/suggestion_list.html", {"items": items})


def generate_schedule(request, meet_id):
    meet = get_object_or_404(Meet, id=meet_id)

    weather = WeatherRecord.objects.filter(
        campus=meet.campus,
        forecast_time__date=meet.planned_date,
        forecast_time__hour=meet.planned_start_time.hour,
    ).first()

    chosen_venue = meet.venue
    if not chosen_venue:
        chosen_venue = Venue.objects.filter(
            campus=meet.campus,
            status="available",
            capacity__gte=meet.expected_people,
        ).order_by("-indoor", "-capacity").first()

    weather_risk = "未知"
    notes = "依据活动计划时间自动生成。"

    if weather:
        weather_risk = risk_level(weather)
        notes += f" 预计天气：{weather_text(weather.weather_code)}，{weather.temperature}℃。"
        if weather_risk == "高":
            notes += " 建议考虑室内或备用时段。"

    FinalSchedule.objects.update_or_create(
        meet=meet,
        defaults={
            "campus": meet.campus,
            "venue": chosen_venue,
            "scheduled_date": meet.planned_date,
            "scheduled_start_time": meet.planned_start_time,
            "scheduled_end_time": meet.planned_end_time,
            "weather_risk": weather_risk,
            "notes": notes,
        },
    )

    meet.status = "scheduled"
    meet.save(update_fields=["status"])

    Notification.objects.create(
        title="活动已自动排程",
        content=f"《{meet.title}》已生成最终排程。",
        notification_type="schedule",
    )
    messages.success(request, f"《{meet.title}》排程成功")
    return redirect("schedule_list")


def schedule_list(request):
    items = FinalSchedule.objects.select_related("meet", "campus", "venue").all()
    return render(request, "core/schedule_list.html", {"items": items})


def export_schedule_csv(request):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="final_schedule.csv"'
    response.write("\ufeff")

    writer = csv.writer(response)
    writer.writerow(["活动名称", "校区", "场地", "日期", "开始时间", "结束时间", "天气风险", "说明"])

    for item in FinalSchedule.objects.select_related("meet", "campus", "venue").all():
        writer.writerow([
            item.meet.title,
            item.campus.name,
            item.venue.name if item.venue else "未分配",
            item.scheduled_date,
            item.scheduled_start_time,
            item.scheduled_end_time,
            item.weather_risk,
            item.notes,
        ])

    return response


def analytics(request):
    event_distribution = Meet.objects.values("sport_event__name").annotate(total=Count("id")).order_by("-total")
    campus_distribution = Venue.objects.values("campus__name").annotate(total=Count("id")).order_by("-total")
    risk_distribution = FinalSchedule.objects.values("weather_risk").annotate(total=Count("id")).order_by("-total")

    context = {
        "event_distribution": event_distribution,
        "campus_distribution": campus_distribution,
        "risk_distribution": risk_distribution,
    }
    return render(request, "core/analytics.html", context)


def notification_list(request):
    items = Notification.objects.all()[:100]
    return render(request, "core/notification_list.html", {"items": items})