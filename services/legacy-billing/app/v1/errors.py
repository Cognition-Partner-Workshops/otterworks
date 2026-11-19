from flask import jsonify, request
from psycopg.errors import CheckViolation, ForeignKeyViolation, UniqueViolation
from werkzeug.exceptions import HTTPException


class InvalidRequest(Exception):
    def __init__(self, field, issue):
        self.field = field
        self.issue = issue
        super().__init__(f"{field} {issue}")


def install_error_handlers(app):
    @app.errorhandler(Exception)
    def handle_error(error):
        if not (request.path == "/api/v1/billing" or request.path.startswith("/api/v1/billing/")):
            if isinstance(error, HTTPException):
                return error
            # Preserve Flask's normal exception logging and Werkzeug 500 page.
            return app.handle_exception(error)
        details = None
        if isinstance(error, InvalidRequest):
            status, code, message = 400, "invalid_request", str(error)
            details = [{"field": error.field, "issue": error.issue}]
        elif isinstance(error, UniqueViolation):
            status, code, message = 409, "conflict", "Resource already exists"
        elif isinstance(error, (ForeignKeyViolation, CheckViolation)):
            status, code, message = 422, "unprocessable", "Database rejected the request"
        elif isinstance(error, HTTPException) and error.code in (400, 401, 404, 405, 409, 422):
            status = error.code
            code = {400: "invalid_request", 401: "unauthorized", 404: "not_found",
                    405: "method_not_allowed", 409: "conflict", 422: "unprocessable"}[status]
            message = error.name
        else:
            app.logger.error("Billing v1 request failed", exc_info=error)
            status, code, message = 500, "internal", "Internal server error"
        body = {"code": code, "message": message}
        if details is not None:
            body["details"] = details
        response = jsonify(error=body)
        response.status_code = status
        if isinstance(error, HTTPException):
            for key, value in error.get_headers():
                if key.lower() not in ("content-type", "content-length"):
                    response.headers[key] = value
        return response
