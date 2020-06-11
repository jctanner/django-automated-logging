import threading
from collections import namedtuple
from typing import NamedTuple, Optional

from django.http import Http404, HttpRequest, HttpResponse
from django.urls import resolve
from django.utils.deprecation import MiddlewareMixin

RequestInformation = NamedTuple(
    'RequestInformation',
    [
        ('request', HttpRequest),
        ('response', Optional[HttpResponse]),
        ('exception', Optional[Exception]),
    ],
)


class AutomatedLoggingMiddleware:
    thread = threading.local()

    def __init__(self, get_response):
        self.get_response = get_response
        self.thread = threading.local()

        AutomatedLoggingMiddleware.thread.__dal__ = None

    def save(self, request, response=None, exception=None):
        """
        Helper middleware, that sadly needs to be present.
        the request_finished and request_started signals only
        expose the class, not the actual request and response.

        We save the request and response specific data in the thread.

        :param request: Django Request
        :param response: Optional Django Response
        :param exception: Optional Exception
        :return:
        """

        AutomatedLoggingMiddleware.thread.__dal__ = RequestInformation(
            request, response, exception
        )

    def __call__(self, request):
        response = self.get_response(request)

        self.save(request, response)

        return response

    def process_exception(self, request, exception):
        """
        Exception proceeds the same as __call__ and therefore should
        also save things in the local thread.

        :param request: Django Request
        :param exception: Thrown Exception
        :return: -
        """
        self.save(request, exception=exception)

    @staticmethod
    def cleanup():
        """
        Cleanup function, that should be called last. Overwrites the
        custom __dal__ object with None, to make sure the next request
        does not use the same object.

        :return: -
        """
        AutomatedLoggingMiddleware.thread.__dal__ = None

    @staticmethod
    def get_current_environ() -> Optional[RequestInformation]:
        """
        Helper staticmethod that looks if the __dal__ custom attribute
        is present and returns either the attribute or None

        :return: -
        """

        if hasattr(AutomatedLoggingMiddleware.thread, '__dal__'):
            return RequestInformation(*AutomatedLoggingMiddleware.thread.__dal__)

        return None
