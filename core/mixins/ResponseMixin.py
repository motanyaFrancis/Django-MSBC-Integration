from django.shortcuts import render


class ResponseMixin:

    def render_response(
        self,
        request,
        template,
        context=None,
    ):

        return render(
            request,
            template,
            context or {},
        )
