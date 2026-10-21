from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Article, Commentaire, Lecture, Notification, Utilisateur


class ConnexionTests(TestCase):
    def test_unknown_email_renders_login_template_with_error(self):
        response = self.client.post(
            reverse('connexion'),
            {'email': 'inconnu@example.com', 'password': 'incorrect'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/login.html')
        self.assertContains(response, 'Identifiants incorrects')


class DetailArticleNotificationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='alice', email='alice@example.com', password='secret123')
        self.utilisateur = Utilisateur.objects.create(user=self.user, acronyme='AL', telephone='123456')
        self.article = Article.objects.create(
            titre='Article de test',
            slug='article-de-test',
            contenu='Contenu',
            auteur=self.user,
        )

    def test_new_lecture_creates_notification(self):
        self.client.force_login(self.user)

        self.client.get(reverse('detail_article', args=[self.article.slug]))

        self.assertTrue(Notification.objects.filter(type='Lecture').exists())

    def test_new_comment_creates_notification(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('detail_article', args=[self.article.slug]),
            {'contenu': 'Très bon article'},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Notification.objects.filter(type='Commentaire').exists())

    def test_formatted_article_content_is_rendered_as_html(self):
        self.article.contenu = '<h2>Introduction</h2><p>Un texte <strong>important</strong>.</p>'
        self.article.save(update_fields=['contenu'])

        response = self.client.get(reverse('detail_article', args=[self.article.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<h2>Introduction</h2>', html=True)
        self.assertContains(response, '<strong>important</strong>', html=True)
