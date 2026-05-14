from django.shortcuts import redirect

class AuthRequiredMixin:
    """
    Protects all views
    """

    def dispatch(self, request, *args, **kwargs):
        if not request.session.get("User_ID"):
            return redirect("auth")
        return super().dispatch(request, *args, **kwargs)