from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from urllib.parse import urlencode

from .models import Acteur, Article, Categorie, Message, NewsletterSubscription, Utilisateur, Temoignage


def home(request):
    articles = Article.objects.select_related('auteur').prefetch_related('categorie_articles__categorie').order_by('-created_at')[:3]
    temoignages = Temoignage.objects.select_related('acteur').order_by('-created_at')[:8]

    try:
        message = request.GET.get('message', False)
    except:
        message = False

    return render(request, 'index.html', {'articles': articles, 'temoignages': temoignages, 'message': message})


def blog(request):
    query = request.GET.get('q', '').strip()
    category_id = request.GET.get('categorie', '').strip()
    articles = Article.objects.select_related('auteur').prefetch_related('categorie_articles__categorie').order_by('-created_at')
    if query:
        articles = articles.filter(
            Q(titre__icontains=query)
            | Q(contenu__icontains=query)
            | Q(categorie_articles__categorie__nom__icontains=query)
        ).distinct()
    if category_id.isdigit():
        articles = articles.filter(categorie_articles__categorie_id=int(category_id)).distinct()
    else:
        category_id = ''

    recent_articles = articles[:3]
    paginator = Paginator(articles, 6)
    page_obj = paginator.get_page(request.GET.get('page'))
    pagination_params = request.GET.copy()
    pagination_params.pop('page', None)
    categories = Categorie.objects.order_by('nom')
    return render(request, 'blog.html', {
        'blog_active': 'active',
        'articles': page_obj.object_list,
        'page_obj': page_obj,
        'pagination_query': urlencode(pagination_params),
        'recent_articles': recent_articles,
        'categories': categories,
        'category_id': category_id,
        'query': query,
    })


def detail_article(request, article_slug):

    article = Article.objects.select_related('auteur').prefetch_related('categorie_articles__categorie').get(slug=article_slug)

    if request.method == 'POST':
        
        contenu = request.POST.get('contenu', '').strip()
        if contenu:
            utilisateur = Utilisateur.objects.get(user=request.user)
            article.commentaires.create(auteur=utilisateur, contenu=contenu)
            return redirect('detail_article', article_slug=article_slug)
        else:
            messages.error(request, "Le contenu du commentaire ne peut pas être vide.")

    if request.user.is_authenticated:
        utilisateur = Utilisateur.objects.get(user=request.user)
        if not article.lectures.filter(utilisateur=utilisateur).exists():
            article.lectures.create(utilisateur=utilisateur)

    else:
        article.lectures.create(utilisateur=None)


    categories = Categorie.objects.order_by('nom')
    articles = Article.objects.select_related('auteur').prefetch_related('categorie_articles__categorie').order_by('-created_at')
    recent_articles = articles[:3]
    return render(request, 'detail_article.html', {'article': article, 'recent_articles': recent_articles, 'blog_active': 'active', 'articles': articles, 'categories': categories})


def cabinet(request):
    return render(request, 'cabinet.html', {'cabinet_active': 'active'})


def contact(request):
    if request.method == 'POST':
        nom = request.POST.get('nom', '').strip()
        email = request.POST.get('email', '').strip()
        telephone = request.POST.get('tel', '').strip()
        sujet = request.POST.get('sujet', '').strip()
        contenu = request.POST.get('message', '').strip()

        if not nom or not email or not sujet or not contenu:
            messages.error(request, 'Veuillez remplir tous les champs requis.')
        else:
            acteur = Acteur.objects.filter(email=email).first()
            if acteur is None:
                parts = nom.split()
                acronyme = ''.join(part[0] for part in parts[:2]).upper()[:2] or 'BC'
                acteur = Acteur.objects.create(
                    acronyme=acronyme,
                    designation=nom,
                    telephone=telephone,
                    email=email,
                )
            elif telephone and not acteur.telephone:
                acteur.telephone = telephone
                acteur.save(update_fields=['telephone'])

            Message.objects.create(
                acteur=acteur,
                sujet=sujet,
                contenu=contenu,
            )
            return redirect('/contact/?message=Votre message a été envoyé avec succès. Nous vous répondrons dans les plus brefs délais.')
    else:
        try:
            message=request.GET.get('message', False)
        except:
            message=False

    
    return render(request, 'contact.html', {'contact_active': 'active', 'message': message})


def services(request):
    temoignages = Temoignage.objects.select_related('acteur').order_by('-created_at')[:8]
    return render(request, 'services.html', {'services_active': 'active', 'temoignages': temoignages})


def connexion(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        
        user = User.objects.filter(email=email).first()
        if not user:
            return render(request, 'login.html', {'error': 'Identifiants incorrects. Veuillez réessayer.'})

        verification = authenticate(request, username=user.username, password=password)
        if verification:
            login(request, user)
            return redirect('home')

        return render(request, 'login.html', {'error': 'Identifiants incorrects. Veuillez réessayer.'})

    return render(request, 'login.html')


def deconnexion(request):
    logout(request)
    return redirect('home')


def inscription(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        nom = request.POST.get('nom', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        telephone = request.POST.get('tel', '').strip()
        newsletter = request.POST.get('newsletter', '') == '1'

        if User.objects.filter(email=email).exists() or User.objects.filter(username=email).exists():
            return render(request, 'inscription.html', {'error': 'Un compte avec cette adresse e-mail existe déjà.'})

        parts = nom.split()
        first_name = parts[0] if parts else ''
        last_name = ' '.join(parts[1:]) if len(parts) > 1 else ''

        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
        )
        acronyme = first_name[0].upper() + last_name[0].upper() if first_name and last_name else 'BC'
        Utilisateur.objects.create(user=user, acronyme=acronyme, telephone=telephone)

        if newsletter:
            NewsletterSubscription.objects.create(email=email)

        login(request, user)
        return redirect('home')

    return render(request, 'inscription.html')


def newsletter_subscription(request):
        
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        if not email:
            message = "Veuillez fournir une adresse e-mail valide."
            return redirect(f'/?message={message}') 

        subscription, created = NewsletterSubscription.objects.get_or_create(email=email)
        if not created:
            message = "Vous êtes déjà abonné à notre newsletter."
        else:
            message = "Merci pour votre abonnement à notre newsletter !"

        return redirect(f'/?message={message}')
    else:
        return redirect('/')