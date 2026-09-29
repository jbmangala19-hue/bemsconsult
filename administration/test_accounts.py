from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from app.models import Action, Article, Commentaire, Lecture, MailingList, Notification, Utilisateur


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class AccountPagesTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username='admin', email='admin@example.com', password='Original-Strong-942!', is_staff=True)
        self.other = User.objects.create_user(username='other', email='other@example.com', is_staff=True)
        self.visitor = User.objects.create_user(username='visitor')
        self.superuser = User.objects.create_superuser(username='super', email='super@example.com', password='Strong-928!')
        self.client.force_login(self.admin)

    def data(self, **overrides):
        data = {'action': 'create', 'username': 'newadmin', 'first_name': 'Alice', 'last_name': 'Martin',
                'email': 'alice@example.com', 'telephone': '12345', 'adresse': 'Kinshasa',
                'is_active': 'on', 'password': 'New-Strong-Password-942!'}
        data.update(overrides)
        return data

    def test_admin_creation_links_profile_and_does_not_grant_superuser(self):
        response = self.client.post(reverse('parametres'), self.data(is_superuser='on'))
        self.assertRedirects(response, reverse('parametres'))
        account = User.objects.get(username='newadmin')
        self.assertTrue(account.is_staff)
        self.assertFalse(account.is_superuser)
        self.assertTrue(account.check_password('New-Strong-Password-942!'))
        self.assertEqual(account.utilisateur.user_id, account.pk)
        self.assertEqual(account.utilisateur.telephone, '12345')
        self.assertEqual(Action.objects.get().type_action, 'Creation')
        self.assertNotIn('New-Strong', Action.objects.get().description)

    def test_admin_creation_rolls_back_if_profile_fails(self):
        with patch('administration.forms.Utilisateur.objects.get_or_create', side_effect=RuntimeError('profile failed')):
            with self.assertRaises(RuntimeError):
                self.client.post(reverse('parametres'), self.data())
        self.assertFalse(User.objects.filter(username='newadmin').exists())
        self.assertFalse(Action.objects.exists())

    def test_admin_edit_and_delete(self):
        response = self.client.get(reverse('parametres'), {'edit': self.other.pk})
        self.assertTrue(response.context['open_form'])
        response = self.client.post(reverse('parametres'), self.data(action='edit', user_id=self.other.pk, password=''))
        self.assertEqual(response.status_code, 302)
        self.other.refresh_from_db()
        self.assertTrue(self.other.is_staff)
        self.assertEqual(self.other.first_name, 'Alice')
        profile_id = self.other.utilisateur.pk
        self.client.post(reverse('parametres'), {'action': 'delete', 'user_id': self.other.pk})
        self.assertFalse(User.objects.filter(pk=self.other.pk).exists())
        self.assertFalse(Utilisateur.objects.filter(pk=profile_id).exists())
        self.assertEqual(Action.objects.filter(type_action='Suppression').count(), 1)

    def test_self_deletion_deactivation_and_superuser_changes_are_blocked(self):
        self.client.post(reverse('parametres'), {'action': 'delete', 'user_id': self.admin.pk})
        response = self.client.post(reverse('parametres'), self.data(action='edit', user_id=self.admin.pk, is_active='', password=''))
        self.assertIn('is_active', response.context['form'].errors)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)
        self.assertEqual(self.admin.username, 'admin')
        for operation in ('edit', 'delete'):
            response = self.client.post(reverse('parametres'), self.data(action=operation, user_id=self.superuser.pk))
            self.assertEqual(response.status_code, 403)
        response = self.client.post(reverse('parametres'), self.data(action='edit', user_id=self.visitor.pk))
        self.assertEqual(response.status_code, 404)

    def test_profile_updates_only_current_account_and_keeps_privileges(self):
        response = self.client.post(reverse('profil'), self.data(action='profile', user_id=self.other.pk, is_staff='', is_superuser='on', is_active=''))
        self.assertRedirects(response, reverse('profil'))
        self.admin.refresh_from_db()
        self.other.refresh_from_db()
        self.assertTrue(self.admin.is_staff)
        self.assertTrue(self.admin.is_active)
        self.assertFalse(self.admin.is_superuser)
        self.assertEqual(self.other.username, 'other')
        self.assertEqual(self.admin.utilisateur.adresse, 'Kinshasa')
        self.assertTrue(self.admin.check_password('Original-Strong-942!'))

    def test_password_requires_old_password_and_preserves_session(self):
        data = {'action': 'password', 'old_password': 'wrong', 'new_password1': 'Updated-Strong-293!', 'new_password2': 'Updated-Strong-293!'}
        response = self.client.post(reverse('profil'), data)
        self.assertIn('old_password', response.context['password_form'].errors)
        data['old_password'] = 'Original-Strong-942!'
        response = self.client.post(reverse('profil'), data, follow=True)
        self.assertEqual(response.status_code, 200)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password('Updated-Strong-293!'))
        self.assertEqual(int(self.client.session['_auth_user_id']), self.admin.pk)
        self.assertEqual(Action.objects.count(), 1)

    def test_own_admin_password_change_preserves_session(self):
        response = self.client.post(reverse('parametres'), self.data(action='edit', user_id=self.admin.pk), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.admin.pk)

    def test_journal_details_search_and_author_scoping(self):
        own = Action.objects.create(auteur=self.admin, type_action='Creation', model_name='Article', description='Own article', details={'note': '<script>alert(1)</script>'})
        other = Action.objects.create(auteur=self.other, type_action='Suppression', description='Other action')
        orphan = Action.objects.create(auteur=None, description='Deleted author')
        response = self.client.get(reverse('parametres'), {'tab': 'actions', 'detail': own.pk})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '&lt;script&gt;')
        self.assertEqual(response.context['page_obj'].paginator.count, 3)
        response = self.client.get(reverse('parametres'), {'tab': 'actions', 'type': 'Creation', 'q': 'Own'})
        self.assertEqual(response.context['page_obj'].paginator.count, 1)
        self.assertEqual(self.client.get(reverse('parametres'), {'tab': 'actions', 'detail': orphan.pk}).status_code, 200)
        self.assertEqual(self.client.get(reverse('profil'), {'detail': other.pk}).status_code, 404)
        response = self.client.get(reverse('profil'), {'detail': own.pk})
        self.assertEqual(response.context['page_obj'].paginator.count, 1)
        self.assertEqual(response.context['action_detail'], own)
        self.assertEqual(self.client.post(reverse('parametres') + '?tab=actions', {'action': 'delete', 'user_id': own.pk}).status_code, 400)

    def test_profile_stats_and_contribution_tabs(self):
        profile = Utilisateur.objects.create(user=self.admin)
        article = Article.objects.create(auteur=self.admin, titre='My article', slug='my-article', contenu='Text')
        Article.objects.create(auteur=self.other, titre='Other', slug='other', contenu='Text')
        MailingList.objects.create(auteur=self.admin, email='mail@example.com')
        Commentaire.objects.create(auteur=profile, article=article, contenu='My comment')
        Lecture.objects.create(utilisateur=profile, article=article)
        Notification.objects.create(auteur=profile, type='Lecture', titre='My notification', contenu='Text')
        response = self.client.get(reverse('profil'))
        for key in ('articles', 'mails', 'commentaires', 'lectures', 'notifications'):
            self.assertEqual(response.context['stats'][key], 1)
            response = self.client.get(reverse('profil'), {'tab': key})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context['page_obj'].paginator.count, 1)

    def test_invalid_forms_pagination_and_access(self):
        response = self.client.post(reverse('parametres'), self.data(username='admin', email='invalid'))
        self.assertTrue(response.context['form'].errors)
        self.assertEqual(self.client.get(reverse('parametres')).context['page_obj'].paginator.count, 3)
        for index in range(13):
            Action.objects.create(auteur=self.admin, description=f'Action {index}')
        response = self.client.get(reverse('parametres'), {'tab': 'actions', 'page': 2})
        self.assertEqual(len(response.context['page_obj']), 1)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.admin)
        for name in ('profil', 'parametres'):
            self.assertEqual(csrf.post(reverse(name), self.data()).status_code, 403)
        self.client.force_login(self.visitor)
        for name in ('profil', 'parametres'):
            self.assertEqual(self.client.get(reverse(name)).url, '/')
            self.assertEqual(self.client.post(reverse(name), self.data()).url, '/')
        self.client.logout()
        for name in ('profil', 'parametres'):
            self.assertEqual(self.client.get(reverse(name)).status_code, 302)
