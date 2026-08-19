from fastapi import Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")


def check_login(request: Request) -> bool:
    return request.session.get("logined", False)


def get_current_user(request: Request) -> dict:
    return {
        "user_id": request.session.get("user_id", 1),
        "user_name": request.session.get("user_name", ""),
        "user_role": request.session.get("user_role", "employee"),
    }


def require_admin(request: Request):
    """관리자 권한 체크. 권한 없으면 RedirectResponse 반환, 있으면 None."""
    if request.session.get("user_role", "employee") != "admin":
        return RedirectResponse(url="/emp_dash", status_code=303)
    return None
