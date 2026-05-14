from requests import Session
from requests.auth import HTTPBasicAuth

from zeep import Client
from zeep.transports import Transport

from django.conf import settings


class SOAPService:

    @classmethod
    def call(
        cls,
        soap_method,
        params=None,
    ):

        session = Session()

        session.auth = HTTPBasicAuth(
            settings.WEB_SERVICE_UID,
            settings.WEB_SERVICE_PWD,
        )

        client = Client(
            settings.BASE_URL,
            transport=Transport(session=session),
        )

        return client.service[soap_method](
            *(params or [])
        )
