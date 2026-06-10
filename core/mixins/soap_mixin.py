import base64

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
    
    def upload_attachment(
        self,
        soap_method,
        file,
        *params
    ):
        """
        Generic SOAP attachment uploader.

        - Encodes file to base64
        - Keeps params fully dynamic for scaling across endpoints
        """

        file_name = file.name
        file_content = base64.b64encode(file.read())

        final_params = [
            *params,
            file_name,
            file_content,
        ]

        return SOAPService.call(
            soap_method=soap_method,
            params=final_params,
        )
