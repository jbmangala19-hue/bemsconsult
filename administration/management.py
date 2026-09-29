"""Pages de gestion des contacts et communications de l'administration."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from app.models import Acteur, Message, Notification, NewsletterSubscription, MailingList, Temoignage
from .accounts import log_action
from .forms import AbonneForm, ActeurForm, MailForm, TemoignageForm


PAGES = {
    'abonnes': dict(model=NewsletterSubscription, form=AbonneForm, title='Abonnés à la newsletter',
        description='Gérez les adresses et les abonnements à votre newsletter.', icon='bi-person-check',
        fields=['email', 'is_active', 'date_inscription'], search=['email'], date='date_inscription',
        status='is_active', editable=True),
    'acteurs': dict(model=Acteur, form=ActeurForm, title='Acteurs',
        description='Gérez les contacts et les intervenants du cabinet.', icon='bi-person-lines-fill',
        fields=['designation', 'type', 'fonction', 'telephone', 'email'],
        search=['designation', 'email', 'telephone', 'type', 'fonction'], date='created_at', editable=True),
    'messages': dict(model=Message, title='Messages reçus',
        description='Consultez les messages reçus et suivez leur lecture.', icon='bi-chat-left-text',
        fields=['sujet', 'acteur', 'lecture', 'created_at'], search=['sujet', 'contenu', 'acteur__designation', 'acteur__email'],
        date='created_at', status='lecture', related=['acteur'], readable=True),
    'notifications': dict(model=Notification, title='Notifications',
        description='Consultez les notifications et suivez leur lecture.', icon='bi-bell',
        fields=['titre', 'type', 'auteur', 'lecture', 'created_at'], search=['titre', 'contenu', 'auteur__user__username'],
        date='created_at', status='lecture', related=['auteur__user'], readable=True),
    'mails': dict(model=MailingList, form=MailForm, title='Mails',
        description='Consultez et enregistrez vos mails. Aucun mail n’est envoyé depuis cette page.', icon='bi-envelope',
        fields=['titre', 'email', 'categorie', 'auteur', 'date'], search=['titre', 'email', 'categorie', 'contenu'],
        date='date', related=['auteur']),
    'temoignages': dict(model=Temoignage, form=TemoignageForm, title='Témoignages',
        description='Gérez les témoignages et les notes de vos acteurs.', icon='bi-chat-quote',
        fields=['acteur', 'note', 'contenu', 'created_at'], search=['contenu', 'acteur__designation'],
        date='created_at', related=['acteur'], editable=True),
}
LABELS = {'created_at': 'Date', 'date_inscription': 'Inscription', 'is_active': 'Abonnement',
    'lecture': 'Lecture', 'email': 'Adresse e-mail', 'designation': 'Désignation', 'telephone': 'Téléphone',
    'categorie': 'Catégorie', 'acronyme': 'Initiales', 'fichier': 'Pièce jointe'}


def _cell(obj, name):
    value = getattr(obj, name)
    cell = {'label': LABELS.get(name, name.capitalize()), 'value': value}
    if name in ('is_active', 'lecture'):
        cell.update(badge=True, positive=value, value=('Actif' if value else 'Inactif') if name == 'is_active' else ('Lu' if value else 'Non lu'))
    elif name in ('created_at', 'date_inscription', 'date'):
        cell['date'] = True
    elif name in ('image', 'fichier'):
        cell.update(file=True, image=name == 'image', url=value.url if value else '')
    elif name == 'note':
        cell['value'] = f'{value}/5'
    return cell


@login_required
@require_http_methods(['GET', 'POST'])
def management_page(request, section):
    if not request.user.is_staff:
        return redirect('/')
    config = PAGES[section]
    model = config['model']
    objects = model.objects.select_related(*config.get('related', []))
    form_class = config.get('form')
    form = form_class(auto_id='create_%s') if form_class else None
    editing_id = None
    if request.method == 'POST':
        action = request.POST.get('action')
        allowed = ['delete'] + (['create'] if form_class else []) + (['edit'] if config.get('editable') else []) + (['read'] if config.get('readable') else [])
        if action not in allowed:
            return HttpResponseBadRequest('Action inconnue.')
        instance = None
        if action != 'create':
            object_id = request.POST.get('object_id', '')
            if not object_id.isdigit():
                return HttpResponseBadRequest('Identifiant invalide.')
            instance = get_object_or_404(objects, pk=int(object_id))
        if action == 'delete':
            with transaction.atomic():
                log_action(request.user, 'Suppression', instance, f'Suppression : {instance}')
                instance.delete()
            messages.success(request, 'Suppression effectuée.')
            return redirect(request.get_full_path())
        if action == 'read':
            with transaction.atomic():
                instance.lecture = True
                instance.save(update_fields=['lecture'])
                log_action(request.user, 'Consultation', instance, f'Lecture : {instance}')
            params = request.GET.copy()
            params['detail'] = instance.pk
            return redirect(f'{request.path}?{params.urlencode()}')
        editing_id = instance.pk if instance else None
        form = form_class(request.POST, request.FILES, instance=instance, auto_id='bound_%s')
        if form.is_valid():
            record = form.save(commit=False)
            if section == 'mails':
                record.auteur = request.user
            with transaction.atomic():
                record.save()
                log_action(request.user, 'Modification' if instance else 'Creation', record,
                    f'Modification : {record}' if instance else f'Création : {record}')
            messages.success(request, 'Modifications enregistrées.' if instance else 'Ajout effectué.')
            return redirect(request.get_full_path())

    query = request.GET.get('q', '').strip()
    if query:
        condition = Q()
        for field in config['search']:
            condition |= Q(**{f'{field}__icontains': query})
        objects = objects.filter(condition)
    status = request.GET.get('status', '')
    if config.get('status') and status in ('1', '0'):
        objects = objects.filter(**{config['status']: status == '1'})
    page = Paginator(objects.order_by('-' + config['date'], '-pk'), 12).get_page(request.GET.get('page'))
    rows = []
    for obj in page:
        rows.append({'object': obj, 'cells': [_cell(obj, name) for name in config['fields']]})
    # Details can be opened even when marking a record read removes it from the unread filter.
    detail = None
    detail_id = request.GET.get('detail', '')
    if detail_id.isdigit():
        obj = get_object_or_404(model.objects.select_related(*config.get('related', [])), pk=int(detail_id))
        detail = {'object': obj, 'cells': [_cell(obj, field.name) for field in model._meta.fields if field.name not in ('id', 'unsubscribe_token')]}
    edit_id = request.GET.get('edit', '')
    if request.method == 'GET' and config.get('editable') and edit_id.isdigit():
        obj = get_object_or_404(model, pk=int(edit_id))
        editing_id = obj.pk
        form = form_class(instance=obj, auto_id='edit_%s')
    params = request.GET.copy()
    for key in ('page', 'detail', 'edit'):
        params.pop(key, None)
    return render(request, f'admins/{section}.html', {
        'section': section, 'config': config, 'rows': rows, 'page_obj': page,
        'headers': [LABELS.get(name, name.capitalize()) for name in config['fields']],
        'query': query, 'status': status, 'pagination_query': params.urlencode(),
        'form': form, 'editing_id': editing_id, 'detail': detail,
        'open_form': bool(editing_id or (form and form.is_bound)),
        'notifications': Notification.objects.select_related('auteur__user').filter(lecture=False).order_by('-created_at')[:8],
        'messages_list': Message.objects.select_related('acteur').filter(lecture=False).order_by('-created_at')[:6],
    })
