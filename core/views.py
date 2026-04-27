import csv
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.db.models import Count, Q, Case, When, Value, IntegerField
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET

from .forms import (
    CampusForm,
    VenueForm,
    SportEventForm,
    MeetForm,
    VenueFeedbackForm,
    WeatherFeedbackForm,
    VenueFeedbackReplyForm,
    WeatherFeedbackReplyForm,
)
from .permissions import ROLE_ADMIN, ROLE_TEACHER, ROLE_STUDENT, get_user_role, role_required
from .models import (
    Campus,
    Venue,
    SportEvent,
    Meet,
    ActivityRegistration,
    WeatherRecord,
    WeatherAlert,
    VenueFeedback,
    WeatherFeedback,
    Suggestion,
    FinalSchedule,
    Notification,
    OperationLog,
)
from .services import WeatherService
from .utils import calculate_sport_score, risk_level, weather_text


def get_activity_duration(meet):
    start_dt = datetime.combine(meet.planned_date, meet.planned_start_time)
    end_dt = datetime.combine(meet.planned_date, meet.planned_end_time)
    duration = end_dt - start_dt
    if duration <= timedelta(0):
        return timedelta(hours=1)
    return duration


def time_overlap(start1, end1, start2, end2):
    return start1 < end2 and end1 > start2


def venue_has_conflict(venue, scheduled_date, start_time, end_time, meet=None):
    schedules = FinalSchedule.objects.filter(venue=venue, scheduled_date=scheduled_date)
    if meet:
        schedules = schedules.exclude(meet=meet)

    for schedule in schedules:
        if time_overlap(schedule.scheduled_start_time, schedule.scheduled_end_time, start_time, end_time):
            return True
    return False


def choose_best_weather_slot(meet):
    now = timezone.now()
    records = list(
        WeatherRecord.objects.filter(campus=meet.campus, forecast_time__gte=now)
        .order_by("forecast_time")[:72]
    )
    if not records:
        return None, 0, "未知", "未来72小时缺少天气数据，已回退到活动原计划时间。"

    candidates = []
    for record in records:
        score = calculate_sport_score(record, meet.sport_event)
        weather_risk = risk_level(record)
        candidates.append((record, score, weather_risk))

    non_high = [item for item in candidates if item[2] != "高"]
    risk_warning = ""
    if non_high:
        pool = non_high
    else:
        pool = candidates
        risk_warning = "天气风险较高，建议人工复核或调整。"

    best_record, best_score, best_risk = sorted(
        pool,
        key=lambda item: (-item[1], item[0].forecast_time),
    )[0]
    return best_record, best_score, best_risk, risk_warning


def choose_best_venue(meet, scheduled_date, start_time, end_time):
    fallback_note = ""
    preferred = meet.venue
    if preferred:
        venue_valid = (
            preferred.campus_id == meet.campus_id
            and preferred.status == "available"
            and preferred.capacity >= meet.expected_people
            and not venue_has_conflict(preferred, scheduled_date, start_time, end_time, meet=meet)
        )
        if venue_valid:
            return preferred, "沿用活动原指定场地（满足校区、状态、容量与时间要求）。"
        fallback_note = "原指定场地不满足条件，系统已自动选择候选场地。"

    candidates = Venue.objects.filter(
        campus=meet.campus,
        status="available",
        capacity__gte=meet.expected_people,
    ).order_by("-indoor", "-capacity")

    for venue in candidates:
        if not venue_has_conflict(venue, scheduled_date, start_time, end_time, meet=meet):
            if fallback_note:
                return venue, f"{fallback_note} 已选择同校区可用场地（室内优先、容量优先）。"
            return venue, "系统自动匹配同校区可用场地（室内优先、容量优先）。"

    return None, "未找到满足容量或时间条件的可用场地，请人工处理。"


def get_meet_capacity_limit(meet):
    capacity_limit = meet.expected_people
    if meet.venue:
        capacity_limit = min(meet.expected_people, meet.venue.capacity)
    return max(capacity_limit, 0)


def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        messages.success(request, "登录成功")
        return redirect("dashboard")
    return render(request, "core/login.html", {"form": form})


@login_required
def logout_view(request):
    logout(request)
    messages.success(request, "您已退出登录")
    return redirect("login")


@login_required
def dashboard(request):
    context = {
        "campus_count": Campus.objects.count(),
        "venue_count": Venue.objects.count(),
        "event_count": SportEvent.objects.count(),
        "meet_count": Meet.objects.count(),
        "schedule_count": FinalSchedule.objects.count(),
        "alert_count": WeatherAlert.objects.filter(active=True).count(),
        "latest_notifications": Notification.objects.all()[:6],
        "current_role": get_user_role(request.user),
    }
    return render(request, "core/dashboard.html", context)


@login_required
def campus_list(request):
    return render(request, "core/campus_list.html", {"items": Campus.objects.all()})


@role_required(ROLE_ADMIN)
def campus_create(request):
    form = CampusForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, "校区创建成功")
        return redirect("campus_list")
    return render(request, "core/campus_form.html", {"form": form, "title": "新增校区"})


@login_required
def venue_list(request):
    items = Venue.objects.select_related("campus").all()
    return render(request, "core/venue_list.html", {"items": items})


@role_required(ROLE_ADMIN)
def venue_create(request):
    form = VenueForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, "场地创建成功")
        return redirect("venue_list")
    return render(request, "core/venue_form.html", {"form": form, "title": "新增场地"})


@login_required
def event_list(request):
    return render(request, "core/event_list.html", {"items": SportEvent.objects.all()})


@role_required(ROLE_ADMIN, ROLE_TEACHER)
def event_create(request):
    form = SportEventForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, "运动项目创建成功")
        return redirect("event_list")
    return render(request, "core/event_form.html", {"form": form, "title": "新增运动项目"})


@login_required
def meet_list(request):
    current_role = get_user_role(request.user)
    items = (
        Meet.objects.select_related("campus", "venue", "sport_event")
        .annotate(
            registered_count=Count(
                "registrations",
                filter=Q(registrations__status="registered"),
            )
        )
        .all()
    )
    registration_map = {}
    if current_role == ROLE_STUDENT:
        registration_map = {
            obj.meet_id: obj.status
            for obj in ActivityRegistration.objects.filter(student=request.user)
        }

    for item in items:
        item.capacity_limit = get_meet_capacity_limit(item)
        item.is_full = item.registered_count >= item.capacity_limit
        item.current_user_registered = registration_map.get(item.id) == "registered"
        item.can_register = (
            current_role == ROLE_STUDENT
            and item.status not in ("completed", "cancelled")
            and not item.current_user_registered
            and not item.is_full
        )
    return render(request, "core/meet_list.html", {"items": items})


@login_required
def register_meet(request, meet_id):
    if get_user_role(request.user) != ROLE_STUDENT:
        messages.error(request, "仅学生可以报名活动。")
        return redirect("meet_list")

    meet = get_object_or_404(Meet.objects.select_related("venue"), id=meet_id)
    if meet.status in ("completed", "cancelled"):
        messages.error(request, "该活动当前不可报名。")
        return redirect("meet_list")

    capacity_limit = get_meet_capacity_limit(meet)
    registered_count = ActivityRegistration.objects.filter(meet=meet, status="registered").count()

    existing_registration = ActivityRegistration.objects.filter(student=request.user, meet=meet).first()
    if not existing_registration and registered_count >= capacity_limit:
        messages.error(request, "该活动报名人数已满")
        return redirect("meet_list")

    registration, created = ActivityRegistration.objects.get_or_create(
        student=request.user,
        meet=meet,
        defaults={"status": "registered"},
    )
    if not created:
        if registration.status == "registered":
            messages.info(request, "你已经报名该活动")
            return redirect("meet_list")
        if registered_count >= capacity_limit:
            messages.error(request, "该活动报名人数已满")
            return redirect("meet_list")
        registration.status = "registered"
        registration.save(update_fields=["status", "updated_at"])
    Notification.objects.create(
        title="活动报名成功",
        content=f"你已成功报名《{meet.title}》。",
        notification_type="system",
    )
    messages.success(request, "报名成功")
    return redirect("meet_list")


@login_required
def cancel_registration(request, meet_id):
    if get_user_role(request.user) != ROLE_STUDENT:
        messages.error(request, "仅学生可以取消报名。")
        return redirect("meet_list")

    meet = get_object_or_404(Meet, id=meet_id)
    registration = ActivityRegistration.objects.filter(student=request.user, meet=meet).first()
    if not registration:
        messages.error(request, "未找到报名记录")
        return redirect("meet_list")
    if registration.status == "cancelled":
        messages.info(request, "该报名已取消")
        return redirect("meet_list")

    registration.status = "cancelled"
    registration.save(update_fields=["status", "updated_at"])
    Notification.objects.create(
        title="活动报名已取消",
        content=f"你已取消报名《{meet.title}》。",
        notification_type="system",
    )
    messages.success(request, "取消报名成功")
    return redirect("my_registrations")


@login_required
def my_registrations(request):
    if get_user_role(request.user) != ROLE_STUDENT:
        messages.info(request, "该页面为学生报名记录页面")
        return redirect("meet_list")
    items = ActivityRegistration.objects.select_related(
        "meet",
        "meet__campus",
        "meet__venue",
        "meet__sport_event",
    ).filter(student=request.user)
    return render(request, "core/my_registrations.html", {"items": items})


@role_required(ROLE_ADMIN, ROLE_TEACHER)
def meet_create(request):
    form = MeetForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, "活动创建成功")
        return redirect("meet_list")
    return render(request, "core/meet_form.html", {"form": form, "title": "新增活动"})


@login_required
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


@login_required
def submit_venue_feedback(request, venue_id=None):
    if get_user_role(request.user) != ROLE_STUDENT:
        messages.error(request, "仅学生可以提交场地反馈。")
        return redirect("venue_list")

    initial = {}
    if venue_id:
        initial["venue"] = get_object_or_404(Venue, id=venue_id)

    form = VenueFeedbackForm(request.POST or None, initial=initial)
    if form.is_valid():
        feedback = form.save(commit=False)
        feedback.student = request.user
        feedback.save()
        Notification.objects.create(
            title="场地反馈已提交",
            content="你的场地反馈已提交，等待教师或管理员处理。",
            notification_type="system",
        )
        messages.success(request, "场地反馈提交成功")
        return redirect("my_feedbacks")
    return render(request, "core/venue_feedback_form.html", {"form": form})


@login_required
def submit_weather_feedback(request):
    if get_user_role(request.user) != ROLE_STUDENT:
        messages.error(request, "仅学生可以提交天气反馈。")
        return redirect("weather_center")

    form = WeatherFeedbackForm(request.POST or None)
    if form.is_valid():
        feedback = form.save(commit=False)
        feedback.student = request.user
        feedback.save()
        Notification.objects.create(
            title="天气反馈已提交",
            content="你的天气反馈已提交，等待教师或管理员处理。",
            notification_type="system",
        )
        messages.success(request, "天气反馈提交成功")
        return redirect("my_feedbacks")
    return render(request, "core/weather_feedback_form.html", {"form": form})


@login_required
def my_feedbacks(request):
    if get_user_role(request.user) != ROLE_STUDENT:
        messages.info(request, "该页面为学生反馈记录页面")
        return redirect("dashboard")
    venue_feedbacks = VenueFeedback.objects.select_related("venue", "venue__campus").filter(student=request.user)
    weather_feedbacks = WeatherFeedback.objects.select_related("campus", "weather_record").filter(student=request.user)
    return render(
        request,
        "core/my_feedbacks.html",
        {"venue_feedbacks": venue_feedbacks, "weather_feedbacks": weather_feedbacks},
    )


@role_required(ROLE_ADMIN, ROLE_TEACHER)
def feedback_manage(request):
    venue_feedbacks = VenueFeedback.objects.select_related("student", "venue").order_by(
        Case(
            When(status="pending", then=Value(0)),
            default=Value(1),
            output_field=IntegerField(),
        ),
        "-created_at",
    )
    weather_feedbacks = WeatherFeedback.objects.select_related("student", "campus", "weather_record").order_by(
        Case(
            When(status="pending", then=Value(0)),
            default=Value(1),
            output_field=IntegerField(),
        ),
        "-created_at",
    )
    return render(
        request,
        "core/feedback_manage.html",
        {"venue_feedbacks": venue_feedbacks, "weather_feedbacks": weather_feedbacks},
    )


@role_required(ROLE_ADMIN, ROLE_TEACHER)
def process_venue_feedback(request, feedback_id):
    feedback = get_object_or_404(VenueFeedback, id=feedback_id)
    form = VenueFeedbackReplyForm(request.POST or None, instance=feedback)
    if form.is_valid():
        feedback = form.save()
        Notification.objects.create(
            title="场地反馈已处理",
            content=f"你提交的场地反馈已处理，回复：{feedback.reply}",
            notification_type="system",
        )
        messages.success(request, "场地反馈已处理")
        return redirect("feedback_manage")
    return render(request, "core/feedback_process_form.html", {"form": form, "title": "处理场地反馈"})


@role_required(ROLE_ADMIN, ROLE_TEACHER)
def process_weather_feedback(request, feedback_id):
    feedback = get_object_or_404(WeatherFeedback, id=feedback_id)
    form = WeatherFeedbackReplyForm(request.POST or None, instance=feedback)
    if form.is_valid():
        feedback = form.save()
        Notification.objects.create(
            title="天气反馈已处理",
            content=f"你提交的天气反馈已处理，回复：{feedback.reply}",
            notification_type="system",
        )
        messages.success(request, "天气反馈已处理")
        return redirect("feedback_manage")
    return render(request, "core/feedback_process_form.html", {"form": form, "title": "处理天气反馈"})


@role_required(ROLE_ADMIN, ROLE_TEACHER)
def refresh_weather(request):
    count = WeatherService.refresh_all_campus_weather()
    messages.success(request, f"天气更新成功，已同步 {count} 个校区")
    return redirect("weather_center")


@require_GET
@role_required(ROLE_ADMIN, ROLE_TEACHER)
def api_refresh_weather_v1(request, campus_id):
    """V1：QWeather（和风天气）"""
    try:
        campus = get_object_or_404(Campus, id=campus_id)
        result = WeatherService.fetch_and_store_for_campus_with_provider(campus, provider="qweather")
        return JsonResponse({"ok": True, "version": "v1", "provider": "qweather", "data": result})
    except Exception as exc:
        return JsonResponse({"ok": False, "version": "v1", "provider": "qweather", "error": str(exc)}, status=400)


@require_GET
@role_required(ROLE_ADMIN, ROLE_TEACHER)
def api_refresh_weather_v2(request, campus_id):
    """V2：高德天气"""
    try:
        campus = get_object_or_404(Campus, id=campus_id)
        result = WeatherService.fetch_and_store_for_campus_with_provider(campus, provider="amap")
        return JsonResponse({"ok": True, "version": "v2", "provider": "amap", "data": result})
    except Exception as exc:
        return JsonResponse({"ok": False, "version": "v2", "provider": "amap", "error": str(exc)}, status=400)


@login_required
def alert_center(request):
    items = WeatherAlert.objects.select_related("campus").filter(active=True)
    return render(request, "core/alert_center.html", {"items": items})


@role_required(ROLE_ADMIN, ROLE_TEACHER)
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


@login_required
def suggestion_list(request):
    items = Suggestion.objects.select_related("campus", "sport_event").all()[:200]
    return render(request, "core/suggestion_list.html", {"items": items})


@role_required(ROLE_ADMIN, ROLE_TEACHER)
def generate_schedule(request, meet_id):
    meet = get_object_or_404(Meet, id=meet_id)
    duration = get_activity_duration(meet)
    best_record, best_score, weather_risk, risk_warning = choose_best_weather_slot(meet)

    if best_record:
        scheduled_date = best_record.forecast_time.date()
        scheduled_start_time = best_record.forecast_time.time().replace(second=0, microsecond=0)
    else:
        scheduled_date = meet.planned_date
        scheduled_start_time = meet.planned_start_time.replace(second=0, microsecond=0)

    start_dt = datetime.combine(scheduled_date, scheduled_start_time)
    scheduled_end_time = (start_dt + duration).time().replace(second=0, microsecond=0)
    chosen_venue, venue_note = choose_best_venue(meet, scheduled_date, scheduled_start_time, scheduled_end_time)

    weather_summary = "无天气记录"
    if best_record:
        weather_summary = (
            f"{weather_text(best_record.weather_code)}，温度 {best_record.temperature}℃，"
            f"降水 {best_record.precipitation}mm，风速 {best_record.wind_speed}m/s"
        )

    notes_parts = [
        (
            f"原计划时间：{meet.planned_date} "
            f"{meet.planned_start_time.strftime('%H:%M')}-{meet.planned_end_time.strftime('%H:%M')}。"
        ),
        (
            f"系统推荐时间：{scheduled_date} "
            f"{scheduled_start_time.strftime('%H:%M')}-{scheduled_end_time.strftime('%H:%M')}。"
        ),
        f"天气情况：{weather_summary}。",
        f"运动适宜度评分：{best_score}（采用与智能建议一致的 calculate_sport_score 评分规则）。",
        "时间选择原因：优先规避高风险天气，在低风险候选中选择评分最高且时间更早的时段。",
        f"场地选择原因：{venue_note}",
    ]
    if risk_warning:
        notes_parts.append(risk_warning)

    notes = "\n".join(notes_parts)

    FinalSchedule.objects.update_or_create(
        meet=meet,
        defaults={
            "campus": meet.campus,
            "venue": chosen_venue,
            "scheduled_date": scheduled_date,
            "scheduled_start_time": scheduled_start_time,
            "scheduled_end_time": scheduled_end_time,
            "weather_risk": weather_risk,
            "notes": notes,
        },
    )

    meet.status = "scheduled"
    meet.save(update_fields=["status"])

    Notification.objects.create(
        title="活动已智能排期",
        content=(
            f"《{meet.title}》推荐时间为 {scheduled_date} {scheduled_start_time.strftime('%H:%M')}，"
            f"场地：{chosen_venue.name if chosen_venue else '未分配'}，天气风险：{weather_risk}。"
        ),
        notification_type="schedule",
    )
    messages.success(request, f"《{meet.title}》智能排期成功")
    return redirect("schedule_list")


@login_required
def schedule_list(request):
    items = FinalSchedule.objects.select_related("meet", "campus", "venue").all()
    pending_meets = Meet.objects.select_related("campus", "sport_event").filter(status="pending")
    return render(request, "core/schedule_list.html", {"items": items, "pending_meets": pending_meets})


@role_required(ROLE_ADMIN, ROLE_TEACHER)
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


@login_required
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


@login_required
def notification_list(request):
    items = Notification.objects.all()[:100]
    return render(request, "core/notification_list.html", {"items": items})


@role_required(ROLE_ADMIN)
def operation_log_list(request):
    items = OperationLog.objects.select_related("user").all()[:300]
    return render(request, "core/operation_log_list.html", {"items": items})
