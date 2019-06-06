import logging
import sys

import json_logging
from json_logging.framework_base import (
    AppRequestInstrumentationConfigurator, RequestAdapter, ResponseAdapter,
)


def is_django_present():
    try:
        import django
    except ImportError:
        return False
    else:
        return True


class DjangoRequestAdapter(RequestAdapter):

    @staticmethod
    def support_global_request_object():
        return False

    @staticmethod
    def get_request_class_type():
        from django.http import HttpRequest
        return HttpRequest

    def get_http_header(self, request, header_name, default=json_logging.EMPTY_VALUE):
        header_name_converted = 'HTTP_' + header_name.upper().replace('-', '_')
        return request.META.get(header_name_converted, default)

    def get_remote_user(self, request):
        if hasattr(request, 'user'):
            return request.user.get_username()
        else:
            return json_logging.EMPTY_VALUE

    def is_in_request_context(self, request):
        return request is not None

    def set_correlation_id(self, request, value):
        request.META['HTTP_X_CORRELATION_ID'] = value

    def get_correlation_id_in_request_context(self, request):
        return request.META.get('HTTP_X_CORRELATION_ID', json_logging.EMPTY_VALUE)

    def get_protocol(self, request):
        return request.META.get('SERVER_PROTOCOL', json_logging.EMPTY_VALUE)

    def get_path(self, request):
        return request.path

    def get_content_length(self, request):
        return request.META.get('CONTENT_LENGTH', json_logging.EMPTY_VALUE)

    def get_method(self, request):
        return request.method

    def get_remote_ip(self, request):
        return request.META.get('REMOTE_ADDR', json_logging.EMPTY_VALUE)

    def get_remote_port(self, request):
        return json_logging.EMPTY_VALUE


class DjangoResponseAdapter(ResponseAdapter):

    def get_status_code(self, response):
        return response.status_code

    def get_response_size(self, response):
        if 'Content-Length' in response:
            return response['Content-Length']
        try:
            return response.tell()
        except OSError:
            return json_logging.EMPTY_VALUE

    def get_content_type(self, response):
        return response['Content-Type']


class DjangoAppRequestInstrumentationConfigurator(AppRequestInstrumentationConfigurator):

    def config(self, app):
        if not is_django_present():
            raise RuntimeError("django is not available in system runtime")

        from django.core.handlers.base import BaseHandler
        from django.core.handlers.exception import convert_exception_to_response

        if not isinstance(app, BaseHandler):
            raise RuntimeError("app is not a valid django.core.handlers.BaseHandler instance")

        self.request_logger = logging.getLogger('json_logging.django')
        self.request_logger.setLevel(logging.DEBUG)
        self.request_logger.addHandler(logging.StreamHandler(sys.stdout))

        handler = app._middleware_chain
        mw_instance = Middleware(handler)
        app._middleware_chain = convert_exception_to_response(mw_instance)


class Middleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_info = json_logging.RequestInfo(request)
        request.request_info = request_info

        response = self.get_response(request)

        request_info.update_response_status(response)
        self.request_logger.info('', extra={'request_info': request_info})

        return response
