
from django.shortcuts import render

def home(request):
    return render(request, 'index.html')

def catalog(request):
    return render(request, 'catalog.html')

def contacts(request):
    return render(request, 'contacts.html')

def profile(request):
    return render(request, 'profile.html')

def cart(request):
    return render(request, 'cart.html')

def login_view(request):
    return render(request, 'login.html')

def register(request):
    return render(request, 'register.html')