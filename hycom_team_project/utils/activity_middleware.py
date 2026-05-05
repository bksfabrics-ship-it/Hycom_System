import logging
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)

class ActivityMiddleware(MiddlewareMixin):
    def process_request(self, request):
        user = getattr(request.user, 'username', 'Anonymous') if request.user.is_authenticated else 'Anonymous'
        ip = request.META.get('REMOTE_ADDR', 'unknown')
        logger.info(f"API HIT | Method: {request.method} | Path: {request.path} | User: {user} | IP: {ip}")
        return None

    def process_response(self, request, response):
        status = response.status_code
        user = getattr(request.user, 'username', 'Anonymous') if request.user.is_authenticated else 'Anonymous'
        ip = request.META.get('REMOTE_ADDR', 'unknown')
        logger.info(f"API RESPONSE | Status: {status} | Method: {request.method} | Path: {request.path} | User: {user} | IP: {ip}")
        return response

    def process_exception(self, request, exception):
        user = getattr(request.user, 'username', 'Anonymous') if request.user.is_authenticated else 'Anonymous'
        ip = request.META.get('REMOTE_ADDR', 'unknown')
        logger.error(f"API ERROR | Path: {request.path} | Method: {request.method} | User: {user} | IP: {ip} | Error: {str(exception)}")
        return None
