"""Auto-discovered modules own both their v1 routes and future legacy adapters."""

from importlib import import_module
from pkgutil import iter_modules

from flask import Blueprint

from .errors import install_error_handlers

def init_app(app):
    blueprint = Blueprint("billing_v1", __name__, url_prefix="/api/v1/billing")
    for module in sorted(iter_modules(__path__), key=lambda item: item.name):
        loaded = import_module(f"{__name__}.{module.name}")
        register = getattr(loaded, "register", None)
        if register:
            register(app, blueprint)
    app.register_blueprint(blueprint)
    install_error_handlers(app)
