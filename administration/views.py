from django.http import HttpResponseBadRequest
from .forms import UtilisateurForm
from .accounts import log_action
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Exists, OuterRef, Q
from django.utils.text import slugify
from django.contrib.contenttypes.models import ContentType
from urllib.parse import urlencode
from app.models import *

# Create your views here.


@login_required
def dashboard(request):

    if not request.user.is_staff:
        return redirect("/")

    utilisateur = Utilisateur.objects.filter(user=request.user).first()
    if not utilisateur:
        acronyme = (request.user.first_name[:1] + request.user.last_name[:1]).upper() if request.user.first_name and request.user.last_name else (request.user.username[:2]).upper()
        utilisateur = Utilisateur.objects.create(
            user=request.user,
            acronyme=acronyme or 'US',
            telephone='',
        )

    articles = Article.objects.select_related('auteur').prefetch_related('categorie_articles__categorie').order_by('-created_at')[:4]
    temoignages = Temoignage.objects.select_related('acteur').order_by('-created_at')[:4]

    derniers_abonnes = NewsletterSubscription.objects.order_by('-date_inscription')[:8]
    derniers_utilisateurs = Utilisateur.objects.select_related('user').order_by('-created_at')[:6]
    dernieres_actions = Action.objects.select_related('auteur').order_by('-created_at')[:10]
    dernieres_notifications = Notification.objects.select_related('auteur__user').filter(lecture=False).order_by('-created_at')[:8]
    derniers_messages = Message.objects.select_related('acteur').filter(lecture=False).order_by('-created_at')[:6]
    derniers_mailings = MailingList.objects.select_related('auteur').order_by('-date')[:6]

    stats = {
        'articles': Article.objects.count(),
        'lectures': Lecture.objects.count(),
        'commentaires': Commentaire.objects.count(),
        'abonnes': NewsletterSubscription.objects.filter(is_active=True).count(),
        'abonnes_total': NewsletterSubscription.objects.count(),
        'utilisateurs': User.objects.count(),
        'messages': Message.objects.count(),
        'messages_non_lus': Message.objects.filter(lecture=False).count(),
        'notifications_total': Notification.objects.count(),
        'notifications_non_lues': Notification.objects.filter(lecture=False).count(),
        'mailings': MailingList.objects.count(),
        'actions': Action.objects.count(),
    }

    # Pour la navbar du base.html
    notifications = dernieres_notifications
    messages_list = derniers_messages

    return render(request, 'admins/index.html', {
        'articles': articles,
        'temoignages': temoignages,
        'derniers_abonnes': derniers_abonnes,
        'derniers_utilisateurs': derniers_utilisateurs,
        'dernieres_actions': dernieres_actions,
        'dernieres_notifications': dernieres_notifications,
        'derniers_messages': derniers_messages,
        'derniers_mailings': derniers_mailings,
        'stats': stats,
        'notifications': notifications,
        'messages_list': messages_list,
        'accueil_active': 'active',
    })


def _get_unique_slug(title, instance=None):
    base_slug = slugify(title) or "publication"
    slug = base_slug
    counter = 1
    qs = Article.objects.all()
    if instance:
        qs = qs.exclude(pk=instance.pk)
    while qs.filter(slug=slug).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1
    return slug


@login_required
def articles(request):
    if not request.user.is_staff:
        return redirect("/")

    utilisateur = Utilisateur.objects.filter(user=request.user).first()
    if not utilisateur:
        acronyme = (request.user.first_name[:1] + request.user.last_name[:1]).upper() if request.user.first_name and request.user.last_name else (request.user.username[:2]).upper()
        utilisateur = Utilisateur.objects.create(
            user=request.user,
            acronyme=acronyme or 'US',
            telephone='',
        )

    query = request.GET.get('q', '').strip()
    category_id = request.GET.get('categorie', '').strip()
    view_mode = request.GET.get('view', 'cards').strip()

    articles_qs = Article.objects.select_related('auteur').prefetch_related('categorie_articles__categorie').order_by('-created_at')

    if query:
        articles_qs = articles_qs.filter(
            Q(titre__icontains=query)
            | Q(contenu__icontains=query)
            | Q(categorie_articles__categorie__nom__icontains=query)
        ).distinct()

    if category_id.isdigit():
        articles_qs = articles_qs.filter(categorie_articles__categorie_id=int(category_id)).distinct()
    else:
        category_id = ''

    categories = Categorie.objects.all().order_by('nom')

    paginator = Paginator(articles_qs, 8)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    pagination_params = request.GET.copy()
    pagination_params.pop('page', None)
    pagination_query = urlencode(pagination_params)

    stats = {
        'articles': Article.objects.count(),
        'lectures': Lecture.objects.count(),
        'commentaires': Commentaire.objects.count(),
        'categories': categories.count(),
    }

    dernieres_notifications = Notification.objects.select_related('auteur__user').filter(lecture=False).order_by('-created_at')[:8]
    derniers_messages = Message.objects.select_related('acteur').filter(lecture=False).order_by('-created_at')[:6]

    notifications = dernieres_notifications
    messages_list = derniers_messages

    return render(request, 'admins/articles.html', {
        'articles': page_obj.object_list,
        'page_obj': page_obj,
        'categories': categories,
        'query': query,
        'category_id': category_id,
        'view_mode': view_mode,
        'pagination_query': pagination_query,
        'stats': stats,
        'dernieres_notifications': dernieres_notifications,
        'derniers_messages': derniers_messages,
        'notifications': notifications,
        'messages_list': messages_list,
        'articles_active': 'active',
    })


@login_required
def article_create(request):
    if not request.user.is_staff:
        return redirect("/")

    if request.method == 'POST':
        titre = request.POST.get('titre', '').strip()
        contenu = request.POST.get('contenu', '').strip()
        category_names = request.POST.getlist('categories')
        image = request.FILES.get('image')
        jointure = request.FILES.get('jointure')

        if not titre or not contenu:
            messages.error(request, "Le titre et le contenu sont obligatoires pour créer une publication.")
            return redirect('articles')

        slug = _get_unique_slug(titre)
        article = Article.objects.create(
            titre=titre,
            slug=slug,
            contenu=contenu,
            auteur=request.user,
            image=image if image else None,
            jointure=jointure or '',
        )

        for category_name in category_names:
            category_name = category_name.strip()
            if category_name:
                category, _ = Categorie.objects.get_or_create(nom=category_name)
                CategorieArticle.objects.get_or_create(article=article, categorie=category)

        content_type = ContentType.objects.get_for_model(Article)
        Action.objects.create(
            auteur=request.user,
            type_action="Creation",
            model_name="Article",
            description=f'Publication de l\'article "{article.titre}"',
            content_type=content_type,
            object_id=article.id,
        )

        messages.success(request, f'L\'article "{article.titre}" a été créé et publié avec succès !')
        return redirect('articles')

    return redirect('articles')


@login_required
def article_edit(request, article_id):
    if not request.user.is_staff:
        return redirect("/")

    article = get_object_or_404(Article, id=article_id)

    if request.method == 'POST':
        titre = request.POST.get('titre', '').strip()
        contenu = request.POST.get('contenu', '').strip()
        category_ids = request.POST.getlist('categories')
        image = request.FILES.get('image')

        if not titre or not contenu:
            messages.error(request, "Le titre et le contenu ne peuvent pas être vides.")
            return redirect('articles')

        if titre != article.titre:
            article.slug = _get_unique_slug(titre, instance=article)
            article.titre = titre

        article.contenu = contenu

        if image:
            article.image = image

        article.save()

        # Update categories
        CategorieArticle.objects.filter(article=article).delete()
        for cat_id in category_ids:
            if cat_id.isdigit():
                cat = Categorie.objects.filter(id=int(cat_id)).first()
                if cat:
                    CategorieArticle.objects.create(article=article, categorie=cat)

        content_type = ContentType.objects.get_for_model(Article)
        Action.objects.create(
            auteur=request.user,
            type_action="Modification",
            model_name="Article",
            description=f'Mise à jour de l\'article "{article.titre}"',
            content_type=content_type,
            object_id=article.id,
        )

        messages.success(request, f'L\'article "{article.titre}" a été modifié avec succès !')
        return redirect('articles')

    return redirect('articles')


@login_required
def article_delete(request, article_id):
    if not request.user.is_staff:
        return redirect("/")

    article = get_object_or_404(Article, id=article_id)

    if request.method == 'POST':
        titre = article.titre
        article.delete()

        Action.objects.create(
            auteur=request.user,
            type_action="Suppression",
            model_name="Article",
            description=f'Suppression de l\'article "{titre}"',
        )

        messages.warning(request, f'L\'article "{titre}" a été supprimé.')
        return redirect('articles')

    return redirect('articles')


@login_required
def users(request):
    if not request.user.is_staff:
        return redirect("/")

    active_subscriptions = NewsletterSubscription.objects.filter(
        email__iexact=OuterRef('email'), is_active=True,
    ).exclude(email='')
    accounts = User.objects.filter(is_staff=False).select_related('utilisateur').annotate(
        newsletter_subscribed=Exists(active_subscriptions),
    )
    form = UtilisateurForm()
    editing_id = None
    if request.method == 'POST':
        action = request.POST.get('action')
        if action not in ('create', 'edit', 'delete'):
            return HttpResponseBadRequest("Action inconnue.")
        account = None
        if action in ('edit', 'delete'):
            account_id = request.POST.get('user_id', '')
            if not account_id.isdigit():
                return HttpResponseBadRequest("Utilisateur invalide.")
            account = get_object_or_404(accounts, pk=int(account_id))
        if action == 'delete':
            with transaction.atomic():
                log_action(request.user, 'Suppression', account, f'Suppression de l’utilisateur {account.username}')
                account.delete()
            messages.success(request, "L’utilisateur a été supprimé.")
            return redirect('users')
        editing_id = account.pk if account else None
        form = UtilisateurForm(request.POST, request.FILES, instance=account)
        if form.is_valid():
            with transaction.atomic():
                saved = form.save()
                log_action(request.user, 'Modification' if editing_id else 'Creation', saved,
                    f'Modification de l’utilisateur {saved.username}' if editing_id else f'Création de l’utilisateur {saved.username}')
            messages.success(request, "L’utilisateur a été modifié." if account else "L’utilisateur a été ajouté.")
            return redirect('users')

    query = request.GET.get('q', '').strip()
    status = request.GET.get('status', '')
    if query:
        accounts = accounts.filter(Q(username__icontains=query) | Q(first_name__icontains=query)
            | Q(last_name__icontains=query) | Q(email__icontains=query)
            | Q(utilisateur__telephone__icontains=query))
    if status in ('active', 'inactive'):
        accounts = accounts.filter(is_active=(status == 'active'))
    page_obj = Paginator(accounts.order_by('-date_joined', '-pk'), 12).get_page(request.GET.get('page'))
    rows = [(account, UtilisateurForm(instance=account, auto_id=f'user_{account.pk}_%s')) for account in page_obj]
    params = request.GET.copy()
    params.pop('page', None)
    return render(request, "admins/users.html", {
        'user_rows': rows, 'page_obj': page_obj, 'form': form,
        'editing_id': editing_id, 'query': query, 'status': status,
        'pagination_query': params.urlencode(),
        'notifications': Notification.objects.select_related('auteur__user').filter(lecture=False).order_by('-created_at')[:8],
        'messages_list': Message.objects.select_related('acteur').filter(lecture=False).order_by('-created_at')[:6],
    })
