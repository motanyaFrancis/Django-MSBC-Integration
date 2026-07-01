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

    def upload_attachment(self, soap_method, doc_no, file, *params):
        """
        - doc_no  : document number, always first in SOAP params
        - file    : file object, encoded to base64
        - *params : any extra params (tableID, userID, etc.) passed through in order
        """
        file_name = file.name
        file_content = base64.b64encode(file.read()).decode("utf-8")

        final_params = [
            doc_no,        # always first
            file_name,     # always second
            file_content,  # always third
            *params,       # tableID, userID, anything else — in call order
        ]

        return SOAPService.call(
            soap_method=soap_method,
            params=final_params,
        )
