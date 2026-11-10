"""把 DRF 异常统一收口成 {code,message,detail?}，前端只认 code，不解析文案。"""

from rest_framework.views import exception_handler

CODE_BY_STATUS = {
    400: "VALIDATION_ERROR",
    401: "TOKEN_INVALID",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    429: "TOO_MANY_REQUESTS",
}


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None

    data = response.data
    detail = data.get("detail") if isinstance(data, dict) else None
    code = CODE_BY_STATUS.get(response.status_code, "ERROR")
    # 业务码统一大写，DRF 内建 code（authentication_failed 之类）保持小写，据此区分。
    codes = exc.get_codes() if hasattr(exc, "get_codes") else None
    if isinstance(codes, str) and codes.isupper():
        code = codes

    payload = {"code": code, "message": str(detail) if detail is not None else "请求参数不合法"}
    # 字段级错误保留原结构，前端按字段渲染表单提示。
    if detail is None:
        payload["detail"] = data
    response.data = payload
    return response
