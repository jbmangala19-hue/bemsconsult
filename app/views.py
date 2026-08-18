from django.shortcuts import render

# Create your views here.

def home(request):
    return render(request, 'index.html')


def blog(request):
    return render(request, 'blog.html')


def cabinet(request):
    return render(request, 'cabinet.html')


def contact(request):
    return render(request, 'contact.html')


def services(request):
    return render(request, 'services.html')