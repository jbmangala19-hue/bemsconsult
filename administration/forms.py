from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction

from app.models import Utilisateur, Acteur, NewsletterSubscription, MailingList, Temoignage


class UtilisateurForm(forms.ModelForm):
    telephone = forms.CharField(label="Téléphone", max_length=20, required=False)
    adresse = forms.CharField(label="Adresse", widget=forms.Textarea(attrs={'rows': 3}), required=False)
    image = forms.ImageField(label="Photo", required=False)
    password = forms.CharField(label="Mot de passe", strip=False, required=False, widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'is_active']
        labels = {'username': "Nom d’utilisateur", 'first_name': 'Prénom', 'last_name': 'Nom', 'email': 'Adresse e-mail', 'is_active': 'Compte actif'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].required = True
        self.fields['password'].required = not self.instance.pk
        self.fields['password'].help_text = "Obligatoire à la création ; laissez vide à la modification pour conserver le mot de passe."
        profile = Utilisateur.objects.filter(user=self.instance).first() if self.instance.pk else None
        if profile:
            for name in ('telephone', 'adresse', 'image'):
                self.initial[name] = getattr(profile, name)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-check-input' if isinstance(field.widget, forms.CheckboxInput) else 'form-control'

    def clean(self):
        data = super().clean()
        password = data.get('password')
        if password:
            candidate = User(**{name: data.get(name, '') for name in ('username', 'first_name', 'last_name', 'email')})
            try:
                validate_password(password, candidate)
            except ValidationError as error:
                self.add_error('password', error)
        return data

    @transaction.atomic
    def save(self):
        user = super().save(commit=False)
        if not user.pk:
            user.is_staff = False
            user.is_superuser = False
        if self.cleaned_data['password']:
            user.set_password(self.cleaned_data['password'])
        user.save()
        profile, _ = Utilisateur.objects.get_or_create(user=user)
        profile.telephone = self.cleaned_data['telephone']
        profile.adresse = self.cleaned_data['adresse']
        profile.acronyme = ((user.first_name[:1] + user.last_name[:1]) or user.username[:2]).upper()
        if self.cleaned_data['image'] is False:
            profile.image = ''
        elif self.cleaned_data['image']:
            profile.image = self.cleaned_data['image']
        profile.save()
        return user


class AdminModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = ('form-check-input' if isinstance(field.widget, forms.CheckboxInput)
                else 'form-select' if isinstance(field.widget, forms.Select) else 'form-control')
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs['rows'] = 5


class AbonneForm(AdminModelForm):
    class Meta:
        model = NewsletterSubscription
        fields = ['email', 'is_active']
        labels = {'email': 'Adresse e-mail', 'is_active': 'Abonnement actif'}


class ActeurForm(AdminModelForm):
    class Meta:
        model = Acteur
        fields = ['designation', 'acronyme', 'type', 'fonction', 'telephone', 'email', 'image']
        labels = {'designation': 'Désignation', 'acronyme': 'Initiales', 'telephone': 'Téléphone', 'image': 'Photo'}


class MailForm(AdminModelForm):
    class Meta:
        model = MailingList
        fields = ['email', 'categorie', 'titre', 'contenu', 'fichier']
        labels = {'email': 'Destinataire', 'categorie': 'Catégorie', 'titre': 'Objet', 'fichier': 'Pièce jointe'}


class TemoignageForm(AdminModelForm):
    class Meta:
        model = Temoignage
        fields = ['acteur', 'note', 'contenu']


class AdministrateurForm(UtilisateurForm):
    @transaction.atomic
    def save(self):
        user = super().save()
        user.is_staff = True
        user.save(update_fields=['is_staff'])
        return user


class ProfilForm(UtilisateurForm):
    class Meta(UtilisateurForm.Meta):
        fields = ['username', 'first_name', 'last_name', 'email']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop('password')

    def clean(self):
        data = super().clean()
        data['password'] = ''
        return data
