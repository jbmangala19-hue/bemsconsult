from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
import uuid


class Acteur(models.Model):
    acronyme = models.CharField(max_length=2)
    designation = models.CharField(max_length=255)
    type = models.CharField(max_length=25, blank=True)
    fonction = models.CharField(max_length=255, blank=True)
    telephone = models.CharField(max_length=20, blank=True)
    image = models.ImageField(blank=True)
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Acteur"
        verbose_name_plural = "Acteurs"

    def __str__(self):
        return self.designation


class Utilisateur(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="utilisateur")
    acronyme = models.CharField(max_length=2, blank=True)
    telephone = models.CharField(max_length=20, blank=True)
    adresse = models.TextField(blank=True)
    image = models.ImageField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"

    def __str__(self):
        return self.user.username


class Temoignage(models.Model):
    liste_notes = [(0, 0), (1, 1), (2, 2), (3, 3), (4, 4), (5, 5)]
    note = models.PositiveIntegerField("Note", choices=liste_notes, default=5)
    acteur = models.ForeignKey(Acteur, on_delete=models.CASCADE, related_name="temoignages")
    contenu = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Témoignage"
        verbose_name_plural = "Témoignages"

    def __str__(self):
        return f"Témoignage de {self.acteur.designation}"


class Message(models.Model):
    acteur = models.ForeignKey(Acteur, on_delete=models.CASCADE, related_name="messages")
    sujet = models.CharField(max_length=255)
    contenu = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    lecture = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Message"
        verbose_name_plural = "Messages"

    def __str__(self):
        return self.sujet


class Categorie(models.Model):
    nom = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Catégorie"
        verbose_name_plural = "Catégories"

    def __str__(self):
        return self.nom


class Article(models.Model):
    titre = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    contenu = models.TextField()
    auteur = models.ForeignKey(User, on_delete=models.CASCADE, related_name="articles")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    image = models.ImageField(upload_to='articles/', blank=True, null=True)
    jointure = models.FileField(upload_to='articles/jointure/', blank=True)

    class Meta:
        verbose_name = "Article"
        verbose_name_plural = "Articles"

    def __str__(self):
        return f"{self.titre}"


class CategorieArticle(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="categorie_articles")
    categorie = models.ForeignKey(Categorie, on_delete=models.CASCADE, related_name="articles_associes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("article", "categorie")
        verbose_name = "Catégorie d'article"
        verbose_name_plural = "Catégories d'articles"

    def __str__(self):
        return f"Article {self.article.id} - {self.categorie.nom}"


class Commentaire(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="commentaires")
    auteur = models.ForeignKey(Utilisateur, on_delete=models.CASCADE, related_name="commentaires")
    contenu = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Commentaire"
        verbose_name_plural = "Commentaires"

    def __str__(self):
        return f"Commentaire de {self.auteur.user.username} sur {self.article.titre}"


class Lecture(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="lectures")
    utilisateur = models.ForeignKey(Utilisateur, on_delete=models.CASCADE, related_name="lectures", blank=True, null=True)
    date_lecture = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("article", "utilisateur")
        verbose_name = "Lecture"
        verbose_name_plural = "Lectures"

    def __str__(self):
        lecteur = self.utilisateur.user.username if self.utilisateur else "Un visiteur"
        return f"{lecteur} a lu {self.article.titre}"


class MailingList(models.Model):
    auteur = models.ForeignKey(User, on_delete=models.CASCADE, related_name="mailing_lists")
    categorie = models.CharField(max_length=255, blank=True) 
    date = models.DateTimeField(auto_now_add=True)
    email = models.EmailField(unique=True)
    titre = models.CharField(max_length=255, blank=True)
    contenu = models.TextField(blank=True)
    fichier = models.FileField(upload_to='mailing_files/', blank=True, null=True)

    class Meta:
        verbose_name = "Liste de diffusion"
        verbose_name_plural = "Listes de diffusion"

    def __str__(self):
        return self.email
    

class NewsletterSubscription(models.Model):
    email = models.EmailField(unique=True)
    unsubscribe_token = models.UUIDField(default=uuid.uuid4, unique=True)
    is_active = models.BooleanField(default=True)
    date_inscription = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Abonné à la newsletter"
        verbose_name_plural = "Abonnés à la newsletter"

    def __str__(self):
        return self.email



class Notification(models.Model):
    liste_choix = [("Commentaire", "commentaire"), ("Lecture", "lecture"), ("Inscription", "inscription"), ("Abonnement", "abonnement")]
    auteur = models.ForeignKey(Utilisateur, on_delete=models.CASCADE, related_name="notifications", blank=True, null=True)
    type = models.CharField(max_length=30, choices=liste_choix)
    titre = models.CharField(max_length=255)
    contenu = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    lecture = models.BooleanField(default=False)

    def __str__(self):
        return self.titre



class Action(models.Model):
    liste_choix = [
        ("Creation", "création"),
        ("Modification", "modification"),
        ("Suppression", "suppression"),
        ("Connexion", "connexion"),
        ("Deconnexion", "déconnexion"),
        ("Consultation", "consultation"),
        ("Export", "export"),
    ]

    auteur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="actions")
    type_action = models.CharField(max_length=30, choices=liste_choix, default="Consultation")
    model_name = models.CharField(max_length=100, blank=True, default="")
    description = models.TextField(blank=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True, related_name="actions")
    object_id = models.PositiveIntegerField(null=True, blank=True)
    objet = GenericForeignKey("content_type", "object_id")
    details = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Action"
        verbose_name_plural = "Actions"

    def __str__(self):
        auteur_nom = self.auteur.get_full_name() or self.auteur.username if self.auteur else "Système"
        return f"{auteur_nom} - {self.get_type_action_display()} - {self.model_name or 'objet'}"


class Associe(models.Model):
    liste_choix = [("Client", "client"), ("Partenaire", "partenaire"), ("Affiliation", "affiliation")]
    type = models.CharField(max_length=30, choices=liste_choix)
    designation = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    lien = models.TextField(blank=True)
    image = models.ImageField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Associé"
        verbose_name_plural = "Associés"


    def __str__(self):
        return self.designation
