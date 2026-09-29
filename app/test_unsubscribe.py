from django.core.exceptions import PermissionDenied
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import path, reverse

from .models import NewsletterSubscription


def forbidden(request):
    raise PermissionDenied


def broken(request):
    raise RuntimeError('Internal detail')


urlpatterns = [path('forbidden/', forbidden), path('broken/', broken)]


class UnsubscribeTests(TestCase):
    def setUp(self):
        self.subscription = NewsletterSubscription.objects.create(email='Alice@example.com')
        self.url = reverse('desabonnement')

    def test_get_does_not_unsubscribe(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'action="' + self.url + '"')
        self.subscription.refresh_from_db()
        self.assertTrue(self.subscription.is_active)

    def test_post_unsubscribes_case_insensitively_and_is_repeatable(self):
        for _ in range(2):
            response = self.client.post(self.url, {'email': ' alice@example.com '})
            self.assertContains(response, 'Votre d?sabonnement est confirm?')
            self.subscription.refresh_from_db()
            self.assertFalse(self.subscription.is_active)
        self.assertEqual(NewsletterSubscription.objects.count(), 1)

    def test_invalid_and_unknown_addresses_leave_subscription_active(self):
        for email in ['', 'invalid', 'unknown@example.com']:
            response = self.client.post(self.url, {'email': email})
            self.assertContains(response, 'role="alert"')
            self.subscription.refresh_from_db()
            self.assertTrue(self.subscription.is_active)

    def test_csrf_is_required(self):
        self.assertEqual(Client(enforce_csrf_checks=True).post(self.url, {'email': self.subscription.email}).status_code, 403)

    def test_unsupported_method(self):
        self.assertEqual(self.client.delete(self.url).status_code, 405)


@override_settings(DEBUG=False, ROOT_URLCONF=__name__)
class ErrorPageTests(SimpleTestCase):
    def test_error_handlers_render_custom_pages(self):
        client = Client(raise_request_exception=False)
        for url, status, title in [
            ('/forbidden/', 403, 'Acc?s refus?'),
            ('/missing/', 404, 'Page introuvable'),
            ('/broken/', 500, 'Une erreur est survenue'),
        ]:
            response = client.get(url)
            self.assertContains(response, title, status_code=status)
            self.assertTemplateUsed(response, f'{status}.html')
            self.assertNotContains(response, 'Internal detail', status_code=status)
