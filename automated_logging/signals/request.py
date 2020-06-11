import logging
import urllib.parse

from django.contrib.auth.models import AnonymousUser
from django.core.handlers.wsgi import WSGIRequest
from django.dispatch import receiver
from django.core.signals import got_request_exception, request_started, request_finished
from django.http import Http404
from django.urls import resolve

from automated_logging.middleware import AutomatedLoggingMiddleware
from automated_logging.models import RequestEvent, Application
from automated_logging.settings import settings
from automated_logging.helpers import namedtuple2dict
from automated_logging.signals import request_exclusion

logger = logging.getLogger(__name__)


@receiver(request_finished)
def request_finished_signal(sender, **kwargs) -> None:
    """
    This signal gets the environment from the local thread and
    sends a logging message, that message will be processed by the
    handler later on.

    This is a simple redirection.

    :return: -
    """
    level = settings.request.loglevel
    environ = AutomatedLoggingMiddleware.get_current_environ()

    if not environ:
        logger.info(
            "Environment for request couldn't be determined. "
            "Request was not recorded."
        )
        return

    request = RequestEvent()
    if not isinstance(environ.request.user, AnonymousUser):
        request.user = environ.request.user

    request.uri = environ.request.get_full_path()

    if not settings.request.data.query:
        request.uri = urllib.parse.urlparse(request.uri).path

    if settings.request.data.enabled:
        request.content = environ.response.content

    request.content_type = environ.response['Content-Type']

    request.status = environ.response.status_code if environ.response else None
    request.method = environ.request.method

    try:
        # TODO: handler should get_or_create
        application = resolve(environ.request.path).func.__module__.split('.')[0]
        request.application = Application(name=application)
    except Http404:
        pass

    if request_exclusion(request):
        return

    logger.log(
        level,
        f'[{request.method}] [{request.status}] {request.user or "Anonymous"} at {request.uri}',
        extra={'action': 'request', 'event': request},
    )


@receiver(got_request_exception, weak=False)
def request_exception(sender, request, **kwargs):
    """
    Exception logging for requests, via the django signal.

    The signal can also return a WSGIRequest exception, which does not
    have all fields that are needed.

    :return: -
    """

    status = int(request.status_code) if hasattr(request, 'status_code') else None
    method = request.method_code if hasattr(request, 'method') else None
    reason = request.reason_phrase if hasattr(request, 'reason_phrase') else None
    level = logging.CRITICAL if status and status <= 500 else logging.WARNING

    is_wsgi = isinstance(request, WSGIRequest)

    logger.log(
        level,
        f'[{method or "UNK"}] [{status or "UNK"}] '
        f'Exception: {reason or "UNKNOWN"}'
        f'{is_wsgi and "WSGIResponse"}',
    )


@receiver(request_finished)
def thread_cleanup(sender, **kwargs):
    """
    This signal just calls the thread cleanup function to make sure,
    that the custom thread object is always clean for the next request.
    This needs to be always the last function registered by the receiver!

    :return: -
    """
    AutomatedLoggingMiddleware.cleanup()
