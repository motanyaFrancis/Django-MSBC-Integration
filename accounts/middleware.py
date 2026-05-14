from django.http import HttpResponseRedirect
from django.urls import reverse

def session_auth_middleware(get_response):
    """Simple sync middleware - public paths always accessible"""

    def middleware(request):
        public_paths = [
            "auth",
            # "login",
            "forgot-password",
            "reset-password",
            # "reset-password-confirm",
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
            return HttpResponseRedirect(reverse("auth"))

        response = get_response(request)
        return response

    return middleware
