from fastapi import Request
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")


def check_login(request: Request) -> bool:
    return request.session.get("logined", False)
