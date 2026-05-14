from core.services.soap_service import SOAPService


class SOAPMixin:

    def call_soap(
        self,
        soap_method,
        params=None,
    ):

        return SOAPService.call(
            soap_method=soap_method,
            params=params or [],
        )
