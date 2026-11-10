"""业务错误：统一带大写 code，前端按 code 分支，不解析文案。"""

from rest_framework.exceptions import APIException


class BusinessError(APIException):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.status_code = status_code
        super().__init__(detail=message, code=code)
