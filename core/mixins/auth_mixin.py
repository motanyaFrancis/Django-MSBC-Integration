from django.shortcuts import redirect

class AuthRequiredMixin:
    """
    Protects all views. Redirects to login with next param to return after auth.
    """
    def dispatch(self, request, *args, **kwargs):
        if not request.session.get("is_authenticated"):
            next_url = request.get_full_path()
            return redirect(f"/auth/?next={next_url}")
        return super().dispatch(request, *args, **kwargs)