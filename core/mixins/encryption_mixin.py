import base64

from cryptography.fernet import Fernet

from django.conf import settings


class EncryptionMixin:

    cipher_suite = Fernet(settings.ENCRYPT_KEY)

    def encrypt_password(self, password):

        encrypted_text = self.cipher_suite.encrypt(
            password.encode("ascii")
        )

        encrypted_password = base64.urlsafe_b64encode(
            encrypted_text
        ).decode("ascii")

        return encrypted_password

    def decrypt_password(self, password):

        portal_password = base64.urlsafe_b64decode(password)

        decoded_text = self.cipher_suite.decrypt(
            portal_password
        ).decode("ascii")

        return decoded_text