from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Article, Commentaire, Lecture, Notification, Utilisateur


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
