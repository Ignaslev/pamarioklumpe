from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Worker


class WorkerManagementTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="admin", email="admin@example.com", password="test-password-123"
        )
        self.worker = Worker.objects.create(
            first_name="Jonas", last_name="Jonaitis", job_title="Virėjas"
        )

    def test_worker_list_requires_login(self):
        response = self.client.get(reverse("worker-list"))
        self.assertEqual(response.status_code, 302)

    def test_admin_can_create_worker(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("worker-create"),
            {
                "first_name": "Ona",
                "last_name": "Onaitė",
                "job_title": "Padavėja",
                "phone": "",
                "email": "",
                "notes": "",
            },
        )
        self.assertRedirects(response, reverse("worker-list"))
        self.assertTrue(Worker.objects.filter(first_name="Ona").exists())

    def test_admin_can_delete_worker(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("worker-delete", args=[self.worker.pk]))
        self.assertRedirects(response, reverse("worker-list"))
        self.assertFalse(Worker.objects.filter(pk=self.worker.pk).exists())
