"""Gestion des administrateurs, du profil et du journal des actions."""
import json
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from app.models import Action, Article, Commentaire, Lecture, MailingList, Message, Notification
from .forms import AdministrateurForm, ProfilForm


def log_action(author, kind, obj, description):
    # Never record submitted credentials or personal form data in the journal.
    Action.objects.create(auteur=author, type_action=kind,
        model_name=obj.__class__.__name__, description=description,
        content_type=ContentType.objects.get_for_model(obj), object_id=obj.pk)


def navbar_context():
    return {
        'notifications': Notification.objects.select_related('auteur__user').filter(lecture=False).order_by('-created_at')[:8],
        'messages_list': Message.objects.select_related('acteur').filter(lecture=False).order_by('-created_at')[:6],
    }


def action_context(request, queryset):
    scope = queryset
    query = request.GET.get('q', '').strip()
    kind = request.GET.get('type', '')
    if query:
        queryset = queryset.filter(Q(description__icontains=query) | Q(model_name__icontains=query)
            | Q(auteur__username__icontains=query))
    if kind in dict(Action.liste_choix):
        queryset = queryset.filter(type_action=kind)
    detail = None
    detail_id = request.GET.get('detail', '')
    if detail_id.isdigit():
        # Use the original author scope, independently of the current search filters.
        detail = get_object_or_404(scope, pk=int(detail_id))
    params = request.GET.copy()
    params.pop('page', None)
    params.pop('detail', None)
    return {'page_obj': Paginator(queryset.order_by('-created_at', '-pk'), 12).get_page(request.GET.get('page')),
        'query': query, 'kind': kind, 'action_types': Action.liste_choix,
        'action_detail': detail,
        'action_json': json.dumps(detail.details, ensure_ascii=False, indent=2) if detail and detail.details is not None else '',
        'pagination_query': params.urlencode()}


@login_required
@require_http_methods(['GET', 'POST'])
def parametres(request):
    if not request.user.is_staff:
        return redirect('/')
    tab = request.GET.get('tab', 'administrateurs')
    if tab not in ('administrateurs', 'actions'):
        tab = 'administrateurs'
    context = navbar_context()
    context['tab'] = tab
    if tab == 'actions':
        if request.method == 'POST':
            return HttpResponseBadRequest('Le journal est en lecture seule.')
        scope = Action.objects.select_related('auteur', 'content_type')
        context.update(action_context(request, scope))
        return render(request, 'admins/parametres.html', context)

    accounts = User.objects.filter(is_staff=True).select_related('utilisateur')
    form = AdministrateurForm()
    editing_id = None
    if request.method == 'POST':
        operation = request.POST.get('action')
        if operation not in ('create', 'edit', 'delete'):
            return HttpResponseBadRequest('Action inconnue.')
        account = None
        if operation != 'create':
            account_id = request.POST.get('user_id', '')
            if not account_id.isdigit():
                return HttpResponseBadRequest('Administrateur invalide.')
            account = get_object_or_404(accounts, pk=int(account_id))
            if account.is_superuser and not request.user.is_superuser:
                return HttpResponseForbidden('Seul un superutilisateur peut gérer ce compte.')
        if operation == 'delete':
            if account.pk == request.user.pk:
                messages.error(request, 'Vous ne pouvez pas supprimer votre propre compte.')
            else:
                with transaction.atomic():
                    log_action(request.user, 'Suppression', account, f'Suppression de l’administrateur {account.username}')
                    account.delete()
                messages.success(request, 'Administrateur supprimé.')
            return redirect('parametres')
        editing_id = account.pk if account else None
        form = AdministrateurForm(request.POST, request.FILES, instance=account)
        if form.is_valid():
            if editing_id == request.user.pk and not form.cleaned_data['is_active']:
                form.add_error('is_active', 'Vous ne pouvez pas désactiver votre propre compte.')
            else:
                with transaction.atomic():
                    saved = form.save()
                    log_action(request.user, 'Modification' if editing_id else 'Creation', saved,
                        f'Modification de l’administrateur {saved.username}' if editing_id else f'Création de l’administrateur {saved.username}')
                if saved.pk == request.user.pk:
                    update_session_auth_hash(request, saved)
                messages.success(request, 'Administrateur enregistré avec son profil utilisateur.')
                return redirect('parametres')
    edit_id = request.GET.get('edit', '')
    if request.method == 'GET' and edit_id.isdigit():
        account = get_object_or_404(accounts, pk=int(edit_id))
        if account.is_superuser and not request.user.is_superuser:
            return HttpResponseForbidden('Seul un superutilisateur peut gérer ce compte.')
        editing_id = account.pk
        form = AdministrateurForm(instance=account)
    query = request.GET.get('q', '').strip()
    if query:
        accounts = accounts.filter(Q(username__icontains=query) | Q(email__icontains=query)
            | Q(first_name__icontains=query) | Q(last_name__icontains=query))
    context.update({'form': form, 'editing_id': editing_id, 'query': query,
        'page_obj': Paginator(accounts.order_by('-date_joined', '-pk'), 12).get_page(request.GET.get('page')),
        'pagination_query': urlencode({'tab': 'administrateurs', 'q': query}),
        'open_form': bool(editing_id or form.is_bound)})
    return render(request, 'admins/parametres.html', context)


@login_required
@require_http_methods(['GET', 'POST'])
def profil(request):
    if not request.user.is_staff:
        return redirect('/')
    user = request.user
    form = ProfilForm(instance=user)
    password_form = PasswordChangeForm(user)
    if request.method == 'POST':
        operation = request.POST.get('action')
        if operation == 'profile':
            form = ProfilForm(request.POST, request.FILES, instance=user)
            if form.is_valid():
                with transaction.atomic():
                    form.save()
                    log_action(user, 'Modification', user, 'Mise à jour du profil personnel')
                messages.success(request, 'Vos informations ont été enregistrées.')
                return redirect('profil')
        elif operation == 'password':
            password_form = PasswordChangeForm(user, request.POST)
            if password_form.is_valid():
                with transaction.atomic():
                    saved = password_form.save()
                    log_action(user, 'Modification', user, 'Modification du mot de passe personnel')
                update_session_auth_hash(request, saved)
                messages.success(request, 'Votre mot de passe a été modifié.')
                return redirect('profil')
        else:
            return HttpResponseBadRequest('Action inconnue.')
    for field in password_form.fields.values():
        field.widget.attrs['class'] = 'form-control'
    contributions = {
        'articles': Article.objects.filter(auteur=user).order_by('-created_at', '-pk'),
        'mails': MailingList.objects.filter(auteur=user).order_by('-date', '-pk'),
        'commentaires': Commentaire.objects.filter(auteur__user=user).select_related('article').order_by('-created_at', '-pk'),
        'lectures': Lecture.objects.filter(utilisateur__user=user).select_related('article').order_by('-date_lecture', '-pk'),
        'notifications': Notification.objects.filter(auteur__user=user).order_by('-created_at', '-pk'),
    }
    scope = Action.objects.filter(auteur=user).select_related('auteur', 'content_type')
    stats = {key: qs.count() for key, qs in contributions.items()}
    stats['actions'] = scope.count()
    tab = request.GET.get('tab', 'actions')
    if tab not in ('actions', *contributions):
        tab = 'actions'
    context = navbar_context()
    context.update({'form': form, 'password_form': password_form, 'stats': stats, 'tab': tab,
                    'profile_user': user, 'profile': getattr(user, 'utilisateur', None)})
    if tab == 'actions':
        context.update(action_context(request, scope))
    else:
        context['page_obj'] = Paginator(contributions[tab], 12).get_page(request.GET.get('page'))
        context['pagination_query'] = 'tab=' + tab
    return render(request, 'admins/profil.html', context)
