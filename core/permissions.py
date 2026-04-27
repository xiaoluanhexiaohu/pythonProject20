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


def has_feature_perm(user, perm_name):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or get_user_role(user) == ROLE_ADMIN:
        return True
    profile = getattr(user, "profile", None)
    if not profile:
        return False
    return bool(getattr(profile, perm_name, False))


def feature_required(perm_name):
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if has_feature_perm(request.user, perm_name):
                return view_func(request, *args, **kwargs)
            messages.error(request, "您没有该功能权限。")
            return redirect("dashboard")

        return wrapped

    return decorator
