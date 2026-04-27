import csv
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.db.models import Case, Count, IntegerField, Q, Value, When
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET

from .forms import (
    CampusForm,
    MeetForm,
    RegisterForm,
    RegistrationRejectForm,
    SportEventForm,
    UserEditForm,
    VenueFeedbackForm,
    VenueFeedbackReplyForm,
    VenueForm,
    WeatherFeedbackForm,
    WeatherFeedbackReplyForm,
)
from .models import (
    ActivityRegistration,
    Campus,
    FinalSchedule,
    Meet,
    Notification,
    NotificationRead,
    OperationLog,
    SportEvent,
    Suggestion,
    UserProfile,
    Venue,
    VenueFeedback,
    WeatherAlert,
    WeatherFeedback,
    WeatherRecord,
)
from .permissions import (
    ROLE_ADMIN,
    ROLE_STUDENT,
    ROLE_TEACHER,
    feature_required,
    get_user_role,
    has_feature_perm,
    role_required,
)
from .services import WeatherService
from .utils import calculate_sport_score, risk_level, weather_text


def create_notification(
    title,
    content,
    notification_type="system",
    recipient=None,
    target_role="",
    source_module="system",
    created_by=None,
    related_meet=None,
):
    return Notification.objects.create(
        title=title,
        content=content,
        notification_type=notification_type,
        recipient=recipient,
        target_role=target_role,
        source_module=source_module,
        created_by=created_by,
        related_meet=related_meet,
    )


def get_activity_duration(meet):
    start_dt = datetime.combine(meet.planned_date, meet.planned_start_time)
    end_dt = datetime.combine(meet.planned_date, meet.planned_end_time)
    duration = end_dt - start_dt
    return duration if duration > timedelta(0) else timedelta(hours=1)


def time_overlap(start1, end1, start2, end2):
    return start1 < end2 and end1 > start2


def venue_has_conflict(venue, scheduled_date, start_time, end_time, meet=None):
    schedules = FinalSchedule.objects.filter(venue=venue, scheduled_date=scheduled_date)
    if meet:
        schedules = schedules.exclude(meet=meet)
    return any(time_overlap(s.scheduled_start_time, s.scheduled_end_time, start_time, end_time) for s in schedules)


def choose_best_weather_slot(meet):
    now = timezone.now()
    records = list(WeatherRecord.objects.filter(campus=meet.campus, forecast_time__gte=now).order_by("forecast_time")[:72])
    if not records:
        return None, 0, "未知", "未来72小时缺少天气数据，已回退到活动原计划时间。"

    candidates = [(record, calculate_sport_score(record, meet.sport_event), risk_level(record)) for record in records]
    non_high = [item for item in candidates if item[2] != "高"]
    pool = non_high if non_high else candidates
    risk_warning = "" if non_high else "天气风险较高，建议人工复核或调整。"
    best_record, best_score, best_risk = sorted(pool, key=lambda item: (-item[1], item[0].forecast_time))[0]
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

    candidates = Venue.objects.filter(campus=meet.campus, status="available", capacity__gte=meet.expected_people).order_by("-indoor", "-capacity")
    for venue in candidates:
        if not venue_has_conflict(venue, scheduled_date, start_time, end_time, meet=meet):
            return venue, f"{fallback_note} 已选择同校区可用场地（室内优先、容量优先）。" if fallback_note else "系统自动匹配同校区可用场地（室内优先、容量优先）。"

    return None, "未找到满足容量或时间条件的可用场地，请人工处理。"


def get_meet_capacity_limit(meet):
    capacity_limit = meet.expected_people
    if meet.venue:
        capacity_limit = min(meet.expected_people, meet.venue.capacity)
    return max(capacity_limit, 0)


def get_meet_registration_counts(meet):
    approved_count = ActivityRegistration.objects.filter(meet=meet, status="approved").count()
    pending_count = ActivityRegistration.objects.filter(meet=meet, status="pending").count()
    return approved_count, pending_count


def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        messages.success(request, "登录成功")
        return redirect("dashboard")
    return render(request, "core/login.html", {"form": form})


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save(commit=False)
        user.email = form.cleaned_data.get("email", "")
        user.save()
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.role = ROLE_STUDENT
        profile.display_name = form.cleaned_data.get("display_name", "") or profile.display_name or user.username
        profile.save()
        messages.success(request, "注册成功，请登录")
        return redirect("login")
    return render(request, "core/register.html", {"form": form})


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


@role_required(ROLE_ADMIN)
def user_manage(request):
    user_model = get_user_model()
    users = user_model.objects.select_related("profile").all().order_by("-date_joined")
    return render(request, "core/user_manage.html", {"users": users})


@role_required(ROLE_ADMIN)
def user_edit(request, user_id):
    user_model = get_user_model()
    managed_user = get_object_or_404(user_model.objects.select_related("profile"), id=user_id)
    profile, _ = UserProfile.objects.get_or_create(user=managed_user)
    initial = {"display_name": profile.display_name, "role": profile.role, "is_active": managed_user.is_active}
    for field in UserEditForm.base_fields:
        if hasattr(profile, field):
            initial[field] = getattr(profile, field)

    form = UserEditForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        managed_user.is_active = form.cleaned_data["is_active"]
        managed_user.save(update_fields=["is_active"])

        if not managed_user.is_superuser:
            profile.role = form.cleaned_data["role"]
        profile.display_name = form.cleaned_data["display_name"]
        for field in UserEditForm.base_fields:
            if hasattr(profile, field) and field not in ["display_name", "role", "is_active"]:
                setattr(profile, field, form.cleaned_data.get(field, False))
        profile.save()
        messages.success(request, "用户信息与授权已更新")
        return redirect("user_manage")

    return render(request, "core/user_edit.html", {"form": form, "managed_user": managed_user})


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
    return render(request, "core/venue_list.html", {"items": Venue.objects.select_related("campus").all()})


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
    items = Meet.objects.select_related("campus", "venue", "sport_event").all()
    registration_map = {}
    if current_role == ROLE_STUDENT:
        registration_map = {obj.meet_id: obj for obj in ActivityRegistration.objects.filter(student=request.user)}

    for item in items:
        approved_count, pending_count = get_meet_registration_counts(item)
        item.approved_count = approved_count
        item.pending_count = pending_count
        item.capacity_limit = get_meet_capacity_limit(item)
        item.is_full = item.approved_count >= item.capacity_limit
        current_registration = registration_map.get(item.id)
        item.current_registration_status = current_registration.status if current_registration else ""
        item.can_manage_registrations = has_feature_perm(request.user, "can_manage_registrations")
    return render(request, "core/meet_list.html", {"items": items})


@login_required
def register_meet(request, meet_id):
    if get_user_role(request.user) != ROLE_STUDENT:
        messages.error(request, "仅学生可以报名活动。")
        return redirect("meet_list")
    if not has_feature_perm(request.user, "can_register_activity"):
        messages.error(request, "您没有该功能权限")
        return redirect("dashboard")

    meet = get_object_or_404(Meet.objects.select_related("venue"), id=meet_id)
    if meet.status in ("completed", "cancelled"):
        messages.error(request, "该活动当前不可报名。")
        return redirect("meet_list")

    approved_count, _ = get_meet_registration_counts(meet)
    if approved_count >= get_meet_capacity_limit(meet):
        messages.error(request, "该活动名额已满")
        return redirect("meet_list")

    registration, created = ActivityRegistration.objects.get_or_create(
        student=request.user,
        meet=meet,
        defaults={"status": "pending"},
    )
    if not created:
        if registration.status == "pending":
            messages.info(request, "报名正在审核中")
            return redirect("meet_list")
        if registration.status == "approved":
            messages.info(request, "你已成功报名该活动")
            return redirect("meet_list")
        registration.status = "pending"
        registration.review_reason = ""
        registration.reviewed_by = None
        registration.reviewed_at = None
        registration.save(update_fields=["status", "review_reason", "reviewed_by", "reviewed_at", "updated_at"])

    create_notification(
        title="活动报名已提交",
        content=f"你已提交《{meet.title}》的报名申请，请等待教师审核。",
        notification_type="registration",
        recipient=request.user,
        target_role="student",
        source_module="activity_registration",
        created_by=request.user,
        related_meet=meet,
    )
    create_notification(
        title="新的活动报名待审核",
        content=f"学生 {request.user.username} 提交了《{meet.title}》的报名申请。",
        notification_type="registration",
        target_role="teacher",
        source_module="activity_registration",
        created_by=request.user,
        related_meet=meet,
    )
    messages.success(request, "报名已提交，等待审核")
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
    if registration.status not in ("pending", "approved"):
        messages.info(request, "当前状态不可取消")
        return redirect("my_registrations")

    registration.status = "cancelled"
    registration.save(update_fields=["status", "updated_at"])
    create_notification(
        title="活动报名已取消",
        content=f"你已取消《{meet.title}》的报名。",
        notification_type="registration",
        recipient=request.user,
        target_role="student",
        source_module="activity_registration",
        created_by=request.user,
        related_meet=meet,
    )
    messages.success(request, "取消报名成功")
    return redirect("my_registrations")


@login_required
@feature_required("can_register_activity")
def my_registrations(request):
    if get_user_role(request.user) != ROLE_STUDENT:
        messages.info(request, "该页面为学生报名记录页面")
        return redirect("meet_list")
    items = ActivityRegistration.objects.select_related(
        "meet", "meet__campus", "meet__venue", "meet__sport_event", "reviewed_by"
    ).filter(student=request.user)
    return render(request, "core/my_registrations.html", {"items": items})


@role_required(ROLE_ADMIN, ROLE_TEACHER)
def meet_create(request):
    if get_user_role(request.user) == ROLE_TEACHER and not has_feature_perm(request.user, "can_manage_meets"):
        messages.error(request, "您没有该功能权限")
        return redirect("dashboard")
    form = MeetForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, "活动创建成功")
        return redirect("meet_list")
    return render(request, "core/meet_form.html", {"form": form, "title": "新增活动"})


@login_required
def registration_manage(request):
    role = get_user_role(request.user)
    if role not in (ROLE_ADMIN, ROLE_TEACHER) or (role == ROLE_TEACHER and not has_feature_perm(request.user, "can_manage_registrations")):
        messages.error(request, "您没有该功能权限")
        return redirect("dashboard")

    status = request.GET.get("status", "pending")
    items = ActivityRegistration.objects.select_related("student", "meet", "meet__campus", "meet__venue", "meet__sport_event", "reviewed_by")
    if status and status != "all":
        items = items.filter(status=status)
    return render(request, "core/registration_manage.html", {"items": items, "status": status})


@login_required
def meet_registration_manage(request, meet_id):
    role = get_user_role(request.user)
    if role not in (ROLE_ADMIN, ROLE_TEACHER) or (role == ROLE_TEACHER and not has_feature_perm(request.user, "can_manage_registrations")):
        messages.error(request, "您没有该功能权限")
        return redirect("dashboard")

    meet = get_object_or_404(Meet, id=meet_id)
    items = ActivityRegistration.objects.select_related("student", "reviewed_by").filter(meet=meet)
    return render(request, "core/meet_registration_manage.html", {"meet": meet, "items": items})


@login_required
def approve_registration(request, registration_id):
    role = get_user_role(request.user)
    if role not in (ROLE_ADMIN, ROLE_TEACHER) or (role == ROLE_TEACHER and not has_feature_perm(request.user, "can_manage_registrations")):
        messages.error(request, "您没有该功能权限")
        return redirect("dashboard")

    registration = get_object_or_404(ActivityRegistration.objects.select_related("meet", "student"), id=registration_id)
    if registration.status != "pending":
        messages.error(request, "仅待审核记录可审批")
        return redirect("registration_manage")

    approved_count, _ = get_meet_registration_counts(registration.meet)
    if approved_count >= get_meet_capacity_limit(registration.meet):
        messages.error(request, "该活动名额已满")
        return redirect("registration_manage")

    registration.status = "approved"
    registration.review_reason = registration.review_reason or "报名已通过"
    registration.reviewed_by = request.user
    registration.reviewed_at = timezone.now()
    registration.save(update_fields=["status", "review_reason", "reviewed_by", "reviewed_at", "updated_at"])
    create_notification(
        title="活动报名成功",
        content=f"你报名的《{registration.meet.title}》已审核通过。",
        notification_type="registration",
        recipient=registration.student,
        target_role="student",
        source_module="activity_registration",
        created_by=request.user,
        related_meet=registration.meet,
    )
    messages.success(request, "已批准报名")
    return redirect("registration_manage")


@login_required
def reject_registration(request, registration_id):
    role = get_user_role(request.user)
    if role not in (ROLE_ADMIN, ROLE_TEACHER) or (role == ROLE_TEACHER and not has_feature_perm(request.user, "can_manage_registrations")):
        messages.error(request, "您没有该功能权限")
        return redirect("dashboard")

    registration = get_object_or_404(ActivityRegistration.objects.select_related("meet", "student"), id=registration_id)
    if registration.status != "pending":
        messages.error(request, "仅待审核记录可审批")
        return redirect("registration_manage")

    form = RegistrationRejectForm(request.POST or None, instance=registration)
    if request.method == "POST" and form.is_valid():
        registration = form.save(commit=False)
        registration.status = "rejected"
        registration.review_reason = registration.review_reason or "报名未通过"
        registration.reviewed_by = request.user
        registration.reviewed_at = timezone.now()
        registration.save()
        create_notification(
            title="活动报名未通过",
            content=f"你报名的《{registration.meet.title}》未通过审核，原因：{registration.review_reason}",
            notification_type="registration",
            recipient=registration.student,
            target_role="student",
            source_module="activity_registration",
            created_by=request.user,
            related_meet=registration.meet,
        )
        messages.success(request, "已驳回报名")
        return redirect("registration_manage")
    return render(request, "core/registration_review_form.html", {"form": form, "registration": registration})


@login_required
def weather_center(request):
    if not has_feature_perm(request.user, "can_view_weather") and get_user_role(request.user) == ROLE_STUDENT:
        messages.error(request, "您没有该功能权限")
        return redirect("dashboard")
    campus_id = request.GET.get("campus")
    campuses = Campus.objects.all()
    current_campus = campuses.first()
    if campus_id:
        current_campus = get_object_or_404(Campus, id=campus_id)

    next_24h, next_7d = [], []
    if current_campus:
        records = list(WeatherRecord.objects.filter(campus=current_campus).order_by("forecast_time"))
        next_24h, next_7d = records[:24], records[:24 * 7 : 24]
        for item in next_24h + next_7d:
            item.weather_name = weather_text(item.weather_code)
    return render(request, "core/weather_center.html", {"campuses": campuses, "current_campus": current_campus, "next_24h": next_24h, "next_7d": next_7d})


@login_required
def submit_venue_feedback(request, venue_id=None):
    if get_user_role(request.user) != ROLE_STUDENT:
        messages.error(request, "仅学生可以提交场地反馈。")
        return redirect("venue_list")
    if not has_feature_perm(request.user, "can_submit_feedback"):
        messages.error(request, "您没有该功能权限")
        return redirect("dashboard")

    initial = {"venue": get_object_or_404(Venue, id=venue_id)} if venue_id else {}
    form = VenueFeedbackForm(request.POST or None, initial=initial)
    if form.is_valid():
        feedback = form.save(commit=False)
        feedback.student = request.user
        feedback.save()
        create_notification("场地反馈已提交", "你的场地反馈已提交，等待教师或管理员处理。", "feedback", request.user, "student", "venue_feedback", request.user)
        create_notification("新的场地反馈待处理", f"学生 {request.user.username} 提交了场地反馈。", "feedback", None, "teacher", "venue_feedback", request.user)
        messages.success(request, "场地反馈提交成功")
        return redirect("my_feedbacks")
    return render(request, "core/venue_feedback_form.html", {"form": form})


@login_required
def submit_weather_feedback(request):
    if get_user_role(request.user) != ROLE_STUDENT:
        messages.error(request, "仅学生可以提交天气反馈。")
        return redirect("weather_center")
    if not has_feature_perm(request.user, "can_submit_feedback"):
        messages.error(request, "您没有该功能权限")
        return redirect("dashboard")

    form = WeatherFeedbackForm(request.POST or None)
    if form.is_valid():
        feedback = form.save(commit=False)
        feedback.student = request.user
        feedback.save()
        create_notification("天气反馈已提交", "你的天气反馈已提交，等待教师或管理员处理。", "feedback", request.user, "student", "weather_feedback", request.user)
        create_notification("新的天气反馈待处理", f"学生 {request.user.username} 提交了天气反馈。", "feedback", None, "teacher", "weather_feedback", request.user)
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
    return render(request, "core/my_feedbacks.html", {"venue_feedbacks": venue_feedbacks, "weather_feedbacks": weather_feedbacks})


@role_required(ROLE_ADMIN, ROLE_TEACHER)
def feedback_manage(request):
    if get_user_role(request.user) == ROLE_TEACHER and not has_feature_perm(request.user, "can_manage_feedback"):
        messages.error(request, "您没有该功能权限")
        return redirect("dashboard")
    venue_feedbacks = VenueFeedback.objects.select_related("student", "venue").order_by(Case(When(status="pending", then=Value(0)), default=Value(1), output_field=IntegerField()), "-created_at")
    weather_feedbacks = WeatherFeedback.objects.select_related("student", "campus", "weather_record").order_by(Case(When(status="pending", then=Value(0)), default=Value(1), output_field=IntegerField()), "-created_at")
    return render(request, "core/feedback_manage.html", {"venue_feedbacks": venue_feedbacks, "weather_feedbacks": weather_feedbacks})


@role_required(ROLE_ADMIN, ROLE_TEACHER)
def process_venue_feedback(request, feedback_id):
    if get_user_role(request.user) == ROLE_TEACHER and not has_feature_perm(request.user, "can_manage_feedback"):
        messages.error(request, "您没有该功能权限")
        return redirect("dashboard")
    feedback = get_object_or_404(VenueFeedback, id=feedback_id)
    form = VenueFeedbackReplyForm(request.POST or None, instance=feedback)
    if form.is_valid():
        form.save()
        create_notification("场地反馈已处理", f"你提交的场地反馈已处理，回复：{feedback.reply}", "feedback", feedback.student, "student", "venue_feedback", request.user)
        messages.success(request, "场地反馈已处理")
        return redirect("feedback_manage")
    return render(request, "core/feedback_process_form.html", {"form": form, "title": "处理场地反馈"})


@role_required(ROLE_ADMIN, ROLE_TEACHER)
def process_weather_feedback(request, feedback_id):
    if get_user_role(request.user) == ROLE_TEACHER and not has_feature_perm(request.user, "can_manage_feedback"):
        messages.error(request, "您没有该功能权限")
        return redirect("dashboard")
    feedback = get_object_or_404(WeatherFeedback, id=feedback_id)
    form = WeatherFeedbackReplyForm(request.POST or None, instance=feedback)
    if form.is_valid():
        form.save()
        create_notification("天气反馈已处理", f"你提交的天气反馈已处理，回复：{feedback.reply}", "feedback", feedback.student, "student", "weather_feedback", request.user)
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
    try:
        campus = get_object_or_404(Campus, id=campus_id)
        result = WeatherService.fetch_and_store_for_campus_with_provider(campus, provider="qweather")
        return JsonResponse({"ok": True, "version": "v1", "provider": "qweather", "data": result})
    except Exception as exc:
        return JsonResponse({"ok": False, "version": "v1", "provider": "qweather", "error": str(exc)}, status=400)


@require_GET
@role_required(ROLE_ADMIN, ROLE_TEACHER)
def api_refresh_weather_v2(request, campus_id):
    try:
        campus = get_object_or_404(Campus, id=campus_id)
        result = WeatherService.fetch_and_store_for_campus_with_provider(campus, provider="amap")
        return JsonResponse({"ok": True, "version": "v2", "provider": "amap", "data": result})
    except Exception as exc:
        return JsonResponse({"ok": False, "version": "v2", "provider": "amap", "error": str(exc)}, status=400)


@login_required
def alert_center(request):
    if get_user_role(request.user) == ROLE_STUDENT and not has_feature_perm(request.user, "can_view_alerts"):
        messages.error(request, "您没有该功能权限")
        return redirect("dashboard")
    return render(request, "core/alert_center.html", {"items": WeatherAlert.objects.select_related("campus").filter(active=True)})


@role_required(ROLE_ADMIN, ROLE_TEACHER)
def generate_suggestions(request):
    if get_user_role(request.user) == ROLE_TEACHER and not has_feature_perm(request.user, "can_generate_suggestions"):
        messages.error(request, "您没有该功能权限")
        return redirect("dashboard")

    Suggestion.objects.all().delete()
    total = 0
    for campus in Campus.objects.all():
        weather_records = WeatherRecord.objects.filter(campus=campus).order_by("forecast_time")[:72]
        for event in SportEvent.objects.all():
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

    create_notification("智能建议已生成", f"系统已重新生成 {total} 条运动建议。", "suggestion", None, "student", "suggestion", request.user)
    messages.success(request, f"已生成 {total} 条智能建议")
    return redirect("suggestion_list")


@login_required
def suggestion_list(request):
    if get_user_role(request.user) == ROLE_STUDENT and not has_feature_perm(request.user, "can_view_suggestions"):
        messages.error(request, "您没有该功能权限")
        return redirect("dashboard")
    return render(request, "core/suggestion_list.html", {"items": Suggestion.objects.select_related("campus", "sport_event").all()[:200]})


@role_required(ROLE_ADMIN, ROLE_TEACHER)
def generate_schedule(request, meet_id):
    if get_user_role(request.user) == ROLE_TEACHER and not has_feature_perm(request.user, "can_generate_schedule"):
        messages.error(request, "您没有该功能权限")
        return redirect("dashboard")

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
        weather_summary = f"{weather_text(best_record.weather_code)}，温度 {best_record.temperature}℃，降水 {best_record.precipitation}mm，风速 {best_record.wind_speed}m/s"

    notes = "\n".join([
        f"原计划时间：{meet.planned_date} {meet.planned_start_time.strftime('%H:%M')}-{meet.planned_end_time.strftime('%H:%M')}。",
        f"系统推荐时间：{scheduled_date} {scheduled_start_time.strftime('%H:%M')}-{scheduled_end_time.strftime('%H:%M')}。",
        f"天气情况：{weather_summary}。",
        f"运动适宜度评分：{best_score}（采用与智能建议一致的 calculate_sport_score 评分规则）。",
        "时间选择原因：优先规避高风险天气，在低风险候选中选择评分最高且时间更早的时段。",
        f"场地选择原因：{venue_note}",
        risk_warning,
    ]).strip()

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

    create_notification(
        title="活动已智能排期",
        content=f"《{meet.title}》推荐时间为 {scheduled_date} {scheduled_start_time.strftime('%H:%M')}，场地：{chosen_venue.name if chosen_venue else '未分配'}，天气风险：{weather_risk}。",
        notification_type="schedule",
        target_role="student",
        source_module="smart_schedule",
        created_by=request.user,
        related_meet=meet,
    )
    messages.success(request, f"《{meet.title}》智能排期成功")
    return redirect("schedule_list")


@login_required
def schedule_list(request):
    if get_user_role(request.user) == ROLE_STUDENT and not has_feature_perm(request.user, "can_view_schedule"):
        messages.error(request, "您没有该功能权限")
        return redirect("dashboard")
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
        writer.writerow([item.meet.title, item.campus.name, item.venue.name if item.venue else "未分配", item.scheduled_date, item.scheduled_start_time, item.scheduled_end_time, item.weather_risk, item.notes])
    return response


@login_required
def analytics(request):
    if get_user_role(request.user) == ROLE_TEACHER and not has_feature_perm(request.user, "can_view_statistics"):
        messages.error(request, "您没有该功能权限")
        return redirect("dashboard")
    event_distribution = Meet.objects.values("sport_event__name").annotate(total=Count("id")).order_by("-total")
    campus_distribution = Venue.objects.values("campus__name").annotate(total=Count("id")).order_by("-total")
    risk_distribution = FinalSchedule.objects.values("weather_risk").annotate(total=Count("id")).order_by("-total")
    return render(request, "core/analytics.html", {"event_distribution": event_distribution, "campus_distribution": campus_distribution, "risk_distribution": risk_distribution})


@login_required
def notification_list(request):
    role = get_user_role(request.user)
    qs = Notification.objects.all()

    if role == ROLE_ADMIN:
        items = qs
    elif role == ROLE_TEACHER:
        teacher_q = Q(recipient=request.user)
        if has_feature_perm(request.user, "can_manage_registrations"):
            teacher_q |= Q(target_role="teacher", source_module="activity_registration")
        if has_feature_perm(request.user, "can_manage_feedback"):
            teacher_q |= Q(target_role="teacher", source_module__in=["venue_feedback", "weather_feedback"])
        if has_feature_perm(request.user, "can_view_weather") or has_feature_perm(request.user, "can_generate_schedule"):
            teacher_q |= Q(target_role="student", source_module="weather_alert")
        if has_feature_perm(request.user, "can_generate_schedule"):
            teacher_q |= Q(target_role="student", source_module="smart_schedule")
        if has_feature_perm(request.user, "can_generate_suggestions"):
            teacher_q |= Q(target_role="student", source_module="suggestion")
        teacher_q |= Q(target_role="teacher", source_module="system")
        items = qs.filter(teacher_q)
    else:
        allowed_student_modules = ["activity_registration", "venue_feedback", "weather_feedback", "weather_alert", "smart_schedule", "suggestion"]
        items = qs.filter(Q(recipient=request.user) | Q(target_role="student", source_module__in=allowed_student_modules))

    items = items.distinct().order_by("-created_at")[:100]
    read_ids = set(NotificationRead.objects.filter(user=request.user, is_read=True).values_list("notification_id", flat=True))
    for item in items:
        item.current_user_is_read = item.id in read_ids
    return render(request, "core/notification_list.html", {"items": items})


@role_required(ROLE_ADMIN)
def operation_log_list(request):
    return render(request, "core/operation_log_list.html", {"items": OperationLog.objects.select_related("user").all()[:300]})
