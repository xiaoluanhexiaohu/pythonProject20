from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


ROLE_ADMIN = "admin"
ROLE_TEACHER = "teacher"
ROLE_STUDENT = "student"


def get_user_role(user):
    if not user or not user.is_authenticated:
        return ""
    if user.is_superuser:
        return ROLE_ADMIN
    profile = getattr(user, "profile", None)
    return getattr(profile, "role", ROLE_STUDENT)


def role_required(*allowed_roles):
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            role = get_user_role(request.user)
            if role not in allowed_roles:
                messages.error(request, "您没有权限执行该操作。")
                return redirect("dashboard")
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator
