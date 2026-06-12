from django.http import HttpResponseRedirect, request
from django.urls import reverse
from django.utils.cache import add_never_cache_headers

def session_auth_middleware(get_response):
    """Simple sync middleware - public paths always accessible"""

    def middleware(request):

        public_paths = [
            "auth",
            "forgot-password",
            "reset",
            "static",
            "media",
            "serviceworker.js",
        ]

        path = request.path.lstrip("/").rstrip("/")

        # Check if path is public (word-boundary aware)
        is_public = any(
            path == p or path.startswith(p + "/")
            for p in public_paths
        )

        # Allow public paths REGARDLESS of session
        # Only check session for protected paths
        if not is_public and not request.session.get("is_authenticated"):
            next_url = request.get_full_path()
            login_url = reverse("auth")
            return HttpResponseRedirect(f"{login_url}?next={next_url}")

        response = get_response(request)

        if not is_public:
            add_never_cache_headers(response)

        return response

    return middleware
