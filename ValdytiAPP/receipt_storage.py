import os

from django.conf import settings
from django.core.files.storage import FileSystemStorage


class PrivateReceiptStorage(FileSystemStorage):
    """Never serve originals through the public /media/ route."""

    @property
    def base_location(self):
        return settings.RECEIPT_STORAGE_ROOT

    @property
    def location(self):
        return os.path.abspath(self.base_location)

    def url(self, name):
        raise ValueError("Čekių originalai pasiekiami tik per prisijungimu apsaugotą peržiūrą.")
