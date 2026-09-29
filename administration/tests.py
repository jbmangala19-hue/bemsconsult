from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from app.models import Article, Commentaire, Lecture, NewsletterSubscription, Utilisateur, Categorie, CategorieArticle


class DashboardStatsTests(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='secret123',
            is_staff=True,
        )
        self.client.login(username='admin', password='secret123')

        self.utilisateur = Utilisateur.objects.create(user=self.staff_user, acronyme='JB', telephone='123')

        self.article = Article.objects.create(
            titre='Article de test',
            slug='article-de-test',
            contenu='Contenu',
            auteur=self.staff_user,
        )
        self.article_2 = Article.objects.create(
            titre='Deuxième article',
            slug='deuxieme-article',
            contenu='Contenu 2',
            auteur=self.staff_user,
        )

        Lecture.objects.create(article=self.article, utilisateur=self.utilisateur)
        Lecture.objects.create(article=self.article_2, utilisateur=self.utilisateur)

        Commentaire.objects.create(article=self.article, auteur=self.utilisateur, contenu='Nice')
        Commentaire.objects.create(article=self.article_2, auteur=self.utilisateur, contenu='Very nice')
        Commentaire.objects.create(article=self.article, auteur=self.utilisateur, contenu='Again')

        NewsletterSubscription.objects.create(email='abo1@example.com')
        NewsletterSubscription.objects.create(email='abo2@example.com')

    def test_dashboard_returns_real_database_counts(self):
        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['stats']['articles'], 2)
        self.assertEqual(response.context['stats']['lectures'], 2)
        self.assertEqual(response.context['stats']['commentaires'], 3)
        self.assertEqual(response.context['stats']['abonnes'], 2)
        self.assertIn('derniers_abonnes', response.context)
        self.assertIn('derniers_utilisateurs', response.context)
        self.assertIn('dernieres_actions', response.context)
        self.assertIn('dernieres_notifications', response.context)
        self.assertIn('derniers_messages', response.context)
        self.assertIn('derniers_mailings', response.context)
        self.assertContains(response, "Journal d'Activité & Actions")
        self.assertContains(response, "Derniers Abonnés Newsletter")
        self.assertContains(response, "Derniers Utilisateurs Inscrits")
        self.assertContains(response, "Correspondances — Modèle MailingList")


class ArticlesManagementTests(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            username='admin_articles',
            email='admin_art@example.com',
            password='secret123',
            is_staff=True,
        )
        self.client.login(username='admin_articles', password='secret123')

        self.utilisateur = Utilisateur.objects.create(user=self.staff_user, acronyme='AA', telephone='123456')

        self.cat_fiscalite = Categorie.objects.create(nom="Fiscalité")
        self.cat_ifrs = Categorie.objects.create(nom="IFRS")

        self.article1 = Article.objects.create(
            titre="Nouveau Code Fiscal 2026",
            slug="nouveau-code-fiscal-2026",
            contenu="Analyse détaillée des modifications apportées au code fiscal.",
            auteur=self.staff_user,
        )
        CategorieArticle.objects.create(article=self.article1, categorie=self.cat_fiscalite)

        self.article2 = Article.objects.create(
            titre="Reporting de durabilité IFRS S1 et S2",
            slug="reporting-durabilite-ifrs",
            contenu="Guide pratique sur l'application des normes internationales.",
            auteur=self.staff_user,
        )
        CategorieArticle.objects.create(article=self.article2, categorie=self.cat_ifrs)

    def test_articles_list_view(self):
        response = self.client.get(reverse('articles'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('articles', response.context)
        self.assertIn('page_obj', response.context)
        self.assertIn('categories', response.context)
        self.assertEqual(len(response.context['articles']), 2)
        self.assertContains(response, "Nouveau Code Fiscal 2026")
        self.assertContains(response, "Reporting de durabilité IFRS S1 et S2")
        self.assertContains(response, "Ajouter une publication")
        self.assertContains(response, "modalCreateArticle")

    def test_articles_search(self):
        response = self.client.get(reverse('articles') + '?q=durabilité')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['articles']), 1)
        self.assertEqual(response.context['articles'][0].id, self.article2.id)

    def test_articles_filter_by_category(self):
        response = self.client.get(reverse('articles') + f'?categorie={self.cat_fiscalite.id}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['articles']), 1)
        self.assertEqual(response.context['articles'][0].id, self.article1.id)

    def test_article_create_success(self):
        data = {
            'titre': 'Gouvernance et conformité en RDC',
            'contenu': 'Recommandations pour la conformité réglementaire.',
            'categories': [self.cat_fiscalite.id, self.cat_ifrs.id],
        }
        response = self.client.post(reverse('article_create'), data)
        self.assertRedirects(response, reverse('articles'))

        created = Article.objects.filter(titre='Gouvernance et conformité en RDC').first()
        self.assertIsNotNone(created)
        self.assertEqual(created.categorie_articles.count(), 2)

    def test_article_edit_success(self):
        data = {
            'titre': 'Nouveau Code Fiscal 2026 - Édition Révisée',
            'contenu': 'Mise à jour du contenu d analyse.',
            'categories': [self.cat_ifrs.id],
        }
        response = self.client.post(reverse('article_edit', args=[self.article1.id]), data)
        self.assertRedirects(response, reverse('articles'))

        self.article1.refresh_from_db()
        self.assertEqual(self.article1.titre, 'Nouveau Code Fiscal 2026 - Édition Révisée')
        self.assertEqual(self.article1.categorie_articles.first().categorie, self.cat_ifrs)

    def test_article_delete_success(self):
        article_id = self.article2.id
        response = self.client.post(reverse('article_delete', args=[article_id]))
        self.assertRedirects(response, reverse('articles'))
        self.assertFalse(Article.objects.filter(id=article_id).exists())




class UsersManagementTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username='manager', is_staff=True)
        self.member = User.objects.create_user(username='member', email='member@example.com', password='Original-Password-982!')
        self.client.force_login(self.admin)
        self.url = reverse('users')

    def data(self, **overrides):
        data = dict(action='create', username='new_member', email='new@example.com',
                    first_name='Alice', last_name='Martin', telephone='+243123',
                    adresse='Kinshasa', is_active='on', password='Unusual-Password-938!')
        data.update(overrides)
        return data

    def test_listing_includes_accounts_without_profiles_and_excludes_staff(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([u.pk for u in response.context['page_obj']], [self.member.pk])
        self.assertContains(response, 'member@example.com')
        self.assertContains(response, 'modalEditUser')

    def test_create_hashes_password_and_creates_profile_without_privileges(self):
        response = self.client.post(self.url, self.data(is_staff='on', is_superuser='on'))
        self.assertRedirects(response, self.url)
        account = User.objects.get(username='new_member')
        self.assertTrue(account.check_password('Unusual-Password-938!'))
        self.assertFalse(account.is_staff)
        self.assertFalse(account.is_superuser)
        self.assertEqual(account.utilisateur.telephone, '+243123')

    def test_edit_preserves_password_and_creates_missing_profile(self):
        response = self.client.post(self.url, self.data(action='edit', user_id=self.member.pk, password=''))
        self.assertRedirects(response, self.url)
        self.member.refresh_from_db()
        self.assertTrue(self.member.check_password('Original-Password-982!'))
        self.assertEqual(self.member.first_name, 'Alice')
        self.assertEqual(self.member.utilisateur.adresse, 'Kinshasa')

    def test_delete_removes_account_and_profile(self):
        profile = Utilisateur.objects.create(user=self.member)
        response = self.client.post(self.url, {'action': 'delete', 'user_id': self.member.pk})
        self.assertRedirects(response, self.url)
        self.assertFalse(User.objects.filter(pk=self.member.pk).exists())
        self.assertFalse(Utilisateur.objects.filter(pk=profile.pk).exists())

    def test_staff_accounts_cannot_be_modified_or_deleted(self):
        for action in ('edit', 'delete'):
            response = self.client.post(self.url, self.data(action=action, user_id=self.admin.pk))
            self.assertEqual(response.status_code, 404)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_staff)

    def test_invalid_data_is_displayed_without_saving(self):
        for overrides in ({'username': 'member'}, {'email': 'invalid'}, {'password': '123'}, {'telephone': 'x' * 21}):
            response = self.client.post(self.url, self.data(**overrides))
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context['form'].errors)
        self.assertFalse(User.objects.filter(username='new_member').exists())

    def test_search_status_and_pagination(self):
        for i in range(13):
            User.objects.create_user(username=f'visitor{i}', is_active=False)
        response = self.client.get(self.url, {'q': 'visitor', 'status': 'inactive', 'page': 2})
        self.assertEqual(response.context['page_obj'].paginator.count, 13)
        self.assertEqual(len(response.context['page_obj']), 1)
        self.assertContains(response, 'q=visitor')

    def test_non_staff_and_anonymous_cannot_manage_users(self):
        self.client.force_login(self.member)
        for method in (self.client.get, self.client.post):
            response = method(self.url, self.data())
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, '/')
        self.client.logout()
        self.assertEqual(self.client.post(self.url, self.data()).status_code, 302)
        self.assertFalse(User.objects.filter(username='new_member').exists())

    def test_get_does_not_delete_and_post_requires_csrf(self):
        from django.test import Client
        self.client.get(self.url, {'action': 'delete', 'user_id': self.member.pk})
        self.assertTrue(User.objects.filter(pk=self.member.pk).exists())
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        self.assertEqual(client.post(self.url, self.data()).status_code, 403)

    def test_newsletter_status_matches_active_subscription_email_case_insensitively(self):
        NewsletterSubscription.objects.create(email='MEMBER@example.com', is_active=True)
        inactive = User.objects.create_user(username='unsubscribed', email='inactive@example.com')
        NewsletterSubscription.objects.create(email=inactive.email, is_active=False)
        missing = User.objects.create_user(username='no_subscription', email='missing@example.com')
        blank = User.objects.create_user(username='no_email', email='')
        response = self.client.get(self.url)
        statuses = {account.pk: account.newsletter_subscribed for account in response.context['page_obj']}
        self.assertTrue(statuses[self.member.pk])
        for account in (inactive, missing, blank):
            self.assertFalse(statuses[account.pk])
        self.assertContains(response, '<th>Newsletter</th>', html=True)
        self.assertContains(response, 'Abonn\u00e9')
        self.assertContains(response, 'Non abonn\u00e9')
