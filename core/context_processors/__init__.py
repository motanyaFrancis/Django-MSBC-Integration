from django.shortcuts import redirect


class SessionAuthMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        protected_paths = ["/dashboard", "/leave", "/profile"]

        if any(request.path.startswith(p) for p in protected_paths):
            if not request.session.get("User_ID"):
                return redirect("auth")

        return self.get_response(request)
