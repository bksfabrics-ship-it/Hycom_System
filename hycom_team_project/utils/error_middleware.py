import logging
from django.shortcuts import redirect
from django.contrib import messages
from django.http import JsonResponse

logger = logging.getLogger(__name__)

class GlobalExceptionMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)

        except Exception as e:

            logger.error(f"Unhandled Exception: {str(e)}", exc_info=True)

            # Skip admin/static
            if request.path.startswith('/admin') or request.path.startswith('/static'):
                raise e

            # API response
            if request.path.startswith('/api/'):
                return JsonResponse({'error': 'Server error'}, status=500)

            # UI response
            messages.error(request, "Something went wrong. Please try again.")
            return redirect('/api/')