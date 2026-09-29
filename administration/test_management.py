from django.contrib.auth.models import User
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.core import mail
from app.models import Acteur, Message, Notification, NewsletterSubscription, MailingList, Temoignage


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class ManagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(username='manager', is_staff=True)
        cls.visitor = User.objects.create_user(username='visitor')
        cls.actor = Acteur.objects.create(designation='Alice', acronyme='AL', email='alice@example.com')
        cls.message = Message.objects.create(acteur=cls.actor, sujet='Bonjour', contenu='Message complet')
        cls.notification = Notification.objects.create(titre='Information', type='Lecture', contenu='Notification complète')
        cls.subscriber = NewsletterSubscription.objects.create(email='subscriber@example.com')
        cls.mailing = MailingList.objects.create(auteur=cls.admin, email='mail@example.com', titre='Mail enregistré')
        cls.testimonial = Temoignage.objects.create(acteur=cls.actor, note=4, contenu='Excellent')

    def setUp(self):
        self.client.force_login(self.admin)

    def records(self):
        return {'abonnes': self.subscriber, 'acteurs': self.actor, 'messages': self.message,
                'notifications': self.notification, 'mails': self.mailing, 'temoignages': self.testimonial}

    def test_all_pages_and_details_render_real_data(self):
        for section, record in self.records().items():
            with self.subTest(section=section):
                response = self.client.get(reverse(section))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context['page_obj'].paginator.count, 1)
                self.assertTemplateUsed(response, f'admins/{section}.html')
                response = self.client.get(reverse(section), {'detail': record.pk})
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'detailModal')
                self.assertEqual(response.context['detail']['object'], record)
        self.message.refresh_from_db()
        self.assertFalse(self.message.lecture)

    def test_create_edit_and_validation(self):
        cases = [
            ('abonnes', NewsletterSubscription, {'email': 'new@example.com', 'is_active': 'on'}, {'email': 'changed@example.com'}),
            ('acteurs', Acteur, {'designation': 'Bob', 'acronyme': 'BO', 'email': 'bob@example.com'}, {'designation': 'Robert', 'acronyme': 'RO', 'email': 'robert@example.com'}),
            ('temoignages', Temoignage, {'acteur': self.actor.pk, 'note': 5, 'contenu': 'Très bien'}, {'acteur': self.actor.pk, 'note': 2, 'contenu': 'Modifié'}),
        ]
        for section, model, data, edits in cases:
            with self.subTest(section=section):
                response = self.client.post(reverse(section), {'action': 'create', **data})
                self.assertEqual(response.status_code, 302)
                record = model.objects.latest('pk')
                response = self.client.get(reverse(section), {'edit': record.pk})
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context['open_form'])
                response = self.client.post(reverse(section), {'action': 'edit', 'object_id': record.pk, **edits})
                self.assertEqual(response.status_code, 302)
                record.refresh_from_db()
                for key, value in edits.items():
                    self.assertEqual(getattr(record, key + '_id' if key == 'acteur' else key), value)
                count = model.objects.count()
                response = self.client.post(reverse(section), {'action': 'create'})
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context['form'].errors)
                self.assertEqual(model.objects.count(), count)

    def test_invalid_email_duplicate_and_rating_are_rejected(self):
        cases = [('abonnes', {'email': self.subscriber.email}), ('acteurs', {'designation': 'X', 'acronyme': 'XX', 'email': 'invalid'}),
                 ('temoignages', {'acteur': self.actor.pk, 'note': 6, 'contenu': 'Test'})]
        for section, data in cases:
            response = self.client.post(reverse(section), {'action': 'create', **data})
            self.assertTrue(response.context['form'].errors)

    def test_read_marks_only_selected_record_and_keeps_detail_after_filter(self):
        for section, record in [('messages', self.message), ('notifications', self.notification)]:
            response = self.client.post(reverse(section) + '?status=0', {'action': 'read', 'object_id': record.pk}, follow=True)
            record.refresh_from_db()
            self.assertTrue(record.lecture)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context['page_obj'].paginator.count, 0)
            self.assertEqual(response.context['detail']['object'], record)

    def test_mail_creation_assigns_current_author_and_never_sends(self):
        response = self.client.post(reverse('mails'), {'action': 'create', 'email': 'newmail@example.com', 'titre': 'Objet', 'contenu': 'Contenu', 'auteur': self.visitor.pk})
        self.assertEqual(response.status_code, 302)
        record = MailingList.objects.get(email='newmail@example.com')
        self.assertEqual(record.auteur, self.admin)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(self.client.post(reverse('mails'), {'action': 'edit', 'object_id': record.pk}).status_code, 400)

    def test_delete_all_types_and_actor_cascade(self):
        for section in ('messages', 'notifications', 'mails', 'temoignages', 'abonnes', 'acteurs'):
            record = self.records()[section]
            response = self.client.post(reverse(section), {'action': 'delete', 'object_id': record.pk})
            self.assertEqual(response.status_code, 302)
            self.assertFalse(type(record).objects.filter(pk=record.pk).exists())

    def test_actor_deletion_removes_related_messages_and_testimonials(self):
        self.client.post(reverse('acteurs'), {'action': 'delete', 'object_id': self.actor.pk})
        self.assertFalse(Message.objects.filter(pk=self.message.pk).exists())
        self.assertFalse(Temoignage.objects.filter(pk=self.testimonial.pk).exists())

    def test_search_status_and_pagination(self):
        for index in range(13):
            NewsletterSubscription.objects.create(email=f'search{index}@example.com', is_active=False)
        response = self.client.get(reverse('abonnes'), {'q': 'search', 'status': '0', 'page': 2})
        self.assertEqual(response.context['page_obj'].paginator.count, 13)
        self.assertEqual(len(response.context['rows']), 1)
        self.assertContains(response, 'q=search')

    def test_access_csrf_and_invalid_actions(self):
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.admin)
        for section, record in self.records().items():
            url = reverse(section)
            self.assertEqual(csrf.post(url, {'action': 'delete', 'object_id': record.pk}).status_code, 403)
            self.assertEqual(self.client.post(url, {'action': 'invalid'}).status_code, 400)
            self.assertEqual(self.client.post(url, {'action': 'delete', 'object_id': 'bad'}).status_code, 400)
            self.assertEqual(self.client.post(url, {'action': 'delete', 'object_id': 999999}).status_code, 404)
        self.client.force_login(self.visitor)
        for section, record in self.records().items():
            self.assertEqual(self.client.get(reverse(section)).url, '/')
            self.assertEqual(self.client.post(reverse(section), {'action': 'delete', 'object_id': record.pk}).url, '/')
            self.assertTrue(type(record).objects.filter(pk=record.pk).exists())
        self.client.logout()
        for section in self.records():
            self.assertEqual(self.client.get(reverse(section)).status_code, 302)

    @override_settings(STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    })
    def test_mail_attachment_and_actor_image_validation(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        response = self.client.post(reverse('mails'), {
            'action': 'create', 'email': 'attachment@example.com',
            'fichier': SimpleUploadedFile('note.txt', b'Document de test', content_type='text/plain'),
        })
        self.assertEqual(response.status_code, 302)
        record = MailingList.objects.get(email='attachment@example.com')
        self.assertEqual(record.fichier.read(), b'Document de test')
        response = self.client.get(reverse('mails'), {'detail': record.pk})
        self.assertContains(response, record.fichier.url)
        self.assertEqual(len(mail.outbox), 0)
        response = self.client.post(reverse('acteurs'), {
            'action': 'create', 'designation': 'Image invalide', 'acronyme': 'II', 'email': 'image@example.com',
            'image': SimpleUploadedFile('photo.png', b'not an image', content_type='image/png'),
        })
        self.assertIn('image', response.context['form'].errors)
        self.assertFalse(Acteur.objects.filter(email='image@example.com').exists())
