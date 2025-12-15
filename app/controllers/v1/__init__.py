# NOTE: you can modify this file as appropriate.

from flask import Blueprint
from flask_restx import Api

v1 = Blueprint("v1", __name__, url_prefix="/api/v1")

_api = Api(
    v1,
    title='Version 1',
    version='1',
    description='The first stable version.',
)

from .conversations import api as conversations_api
from .metrics import api as metrics_api, core_metrics_api

_api.add_namespace(conversations_api)
_api.add_namespace(metrics_api)
_api.add_namespace(core_metrics_api, path='/core/metrics')
