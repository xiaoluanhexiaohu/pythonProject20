from .permissions import get_user_role
from .models import OperationLog


class OperationLogMiddleware:
    """记录登录用户的关键操作日志。"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if request.path.startswith("/static/"):
            return response

        user = request.user if request.user.is_authenticated else None
        action = ""
        if getattr(request, "resolver_match", None):
            action = request.resolver_match.view_name or request.resolver_match.url_name or ""

        ip_address = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
        if not ip_address:
            ip_address = request.META.get("REMOTE_ADDR", "")

        key_actions = {"login", "logout", "campus_create", "campus_edit", "campus_delete", "venue_create", "venue_edit", "venue_delete",
                       "event_create", "event_edit", "event_delete", "meet_create", "meet_edit", "meet_delete", "approve_registration",
                       "reject_registration", "refresh_weather", "generate_suggestions", "generate_schedule", "export_schedule_csv"}
        if request.method != "POST" and action not in key_actions:
            return response

        OperationLog.objects.create(
            user=user,
            role=get_user_role(user) if user else "",
            action=action,
            method=request.method,
            path=request.path,
            status_code=response.status_code,
            ip_address=ip_address,
            detail=f"query={request.META.get('QUERY_STRING', '')}"[:500],
        )
        return response
