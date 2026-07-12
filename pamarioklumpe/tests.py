from django.test import TestCase
from django.urls import reverse


class PublicSiteTests(TestCase):
    def test_coming_soon_page(self):
        response = self.client.get(reverse("coming-soon"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Greitai...")

