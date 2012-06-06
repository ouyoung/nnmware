from django.conf import settings
from django.contrib import messages
from datetime import datetime
import json
from nnmware.core.utils import get_message_dict

from threading import local

_thread_locals = local()


def get_request():
    return getattr(_thread_locals, 'request', None)


class ThreadLocalsMiddleware(object):
    """Middleware that saves request in thread local storage"""

    def process_request(self, request):
        _thread_locals.request = request


def get_page(self):
    """
    A function which will be monkeypatched onto the request to get the current
    integer representing the current page.
    """
    try:
        return int(self.REQUEST['page'])
    except (KeyError, ValueError, TypeError):
        return 1


class PaginationMiddleware(object):
    """
    Inserts a variable representing the current page onto the request object if
    it exists in either **GET** or **POST** portions of the request.
    """

    def process_request(self, request):
        request.__class__.page = property(get_page)


class AjaxMessagingMiddleware(object):
    def process_response(self, request, response):
        if request.is_ajax():
            if response['Content-Type'] in ["application/javascript", "application/json"]:
                try:
                    content = json.loads(response.content)
                except ValueError:
                    return response
                django_messages = []
                for message in messages.get_messages(request):
                    django_messages.append({
                        "level": message.level,
                        "message": message.message,
                        "extra_tags": message.tags,
                        })
                content['core_messages'] = django_messages
                response.content = json.dumps(content)
        return response

UNTRACKED_USER_AGENT = [
                "Teoma", "alexa", "froogle", "Gigabot", "inktomi", "looksmart", "URL_Spider_SQL", "Firefly",
                "NationalDirectory", "Ask Jeeves", "TECNOSEEK", "InfoSeek", "WebFindBot", "girafabot", "crawler",
                "www.galaxy.com", "Googlebot", "Googlebot/2.1", "Google", "Webmaster", "Scooter", "James Bond",
                "Slurp", "msnbot", "appie", "FAST", "WebBug", "Spade", "ZyBorg", "rabaz", "Baiduspider",
                "Feedfetcher-Google", "TechnoratiSnoop", "Rankivabot", "Mediapartners-Google", "Sogou web spider",
                "WebAlta Crawler", "MJ12bot", "Yandex/", "YandexBot" ,"YaDirectBot", "StackRambler", "DotBot", "dotbot"
        ]


class VisitorHitMiddleware(object):

    def process_request(self, request):
        if request.is_ajax():
            return
        if request.path.startswith(settings.ADMIN_SYSTEM_PREFIX):
            return
        # see if the user agent is not supposed to be tracked
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:255]
        for ua in UNTRACKED_USER_AGENT:
            # if the keyword is found in the user agent, stop tracking
            if user_agent.find(ua) != -1:
                return
        from nnmware.core.models import VisitorHit
        v = VisitorHit()
        if request.user.is_authenticated():
            v.user = request.user
        v.user_agent = user_agent
        v.ip_address = request.META.get('REMOTE_ADDR','')
        if hasattr(request, 'session') and request.session.session_key:
            # use the current session key if we can
            session_key = request.session.session_key
        else:
            # otherwise just fake a session key
            session_key = '%s:%s' % (v.ip_address, v.user_agent)
            session_key = session_key[:40]
        v.session_key = session_key
        v.secure = request.is_secure()
        v.referrer = request.META.get('HTTP_REFERRER','')
        v.hostname = request.META.get('REMOTE_HOST','')[:100]
        v.url = request.get_full_path()
        v.date = datetime.now()
        v.save()
