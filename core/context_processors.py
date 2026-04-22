from .permissions import get_user_role


ROLE_DISPLAY = {
    "admin": "管理员",
    "teacher": "教师",
    "student": "学生",
}


def user_role_context(request):
    role = get_user_role(request.user)
    return {
        "current_role": role,
        "current_role_display": ROLE_DISPLAY.get(role, ""),
    }
