
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import ensure_csrf_cookie
from django.http import JsonResponse
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from .models import UserProfile, UserSession
from django.views.decorators.http import require_POST
import json
import re

@ensure_csrf_cookie
def home(request):
    return render(request, 'index.html')

def catalog(request):
    return render(request, 'catalog.html')

def contacts(request):
    return render(request, 'contacts.html')

@login_required
def profile(request):
    """Страница профиля пользователя"""
    user_profile = request.user.userprofile
    context = {
        'user_profile': user_profile,
        'user_sessions': UserSession.objects.filter(user=request.user, is_active=True).order_by('-last_activity')[:5]
    }
    return render(request, 'profile.html', context)

def logout_view(request):
    """Выход из системы"""
    if request.user.is_authenticated:
        # Деактивация сессий пользователя
        UserSession.objects.filter(user=request.user, session_key=request.session.session_key).update(is_active=False)
        logout(request)
        messages.success(request, 'Вы успешно вышли из системы')
    return redirect('home')

def cart(request):
    return render(request, 'cart.html')

@ensure_csrf_cookie
def login_view(request):
    return render(request, 'login.html')

@ensure_csrf_cookie
def register(request):
    return render(request, 'register.html')

def _json_body(request):
    try:
        return json.loads(request.body.decode('utf-8'))
    except Exception:
        return {}

def api_register(request):
    """API для регистрации пользователя с полной валидацией"""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'errors': {'form': 'Метод не поддерживается'}}, status=405)

    data = _json_body(request)
    errors = {}

    # Получение данных
    name = (data.get('name') or '').strip()
    surname = (data.get('surname') or '').strip()
    patronymic = (data.get('patronymic') or '').strip()
    login_val = (data.get('login') or '').strip()
    email = (data.get('email') or '').strip()
    password = data.get('password') or ''
    password_repeat = data.get('password_repeat') or ''
    rules = bool(data.get('rules'))

    # Регулярные выражения для валидации
    reg_cyr = re.compile(r'^[А-Яа-яЁё\-\s]+$')
    reg_login = re.compile(r'^[A-Za-z0-9\-]+$')

    # Валидация полей
    if not name or not reg_cyr.match(name):
        errors['name'] = 'Имя: кириллица, пробел и тире'
    if not surname or not reg_cyr.match(surname):
        errors['surname'] = 'Фамилия: кириллица, пробел и тире'
    if patronymic and not reg_cyr.match(patronymic):
        errors['patronymic'] = 'Отчество: кириллица, пробел и тире'
    if not login_val or not reg_login.match(login_val):
        errors['login'] = 'Логин: латиница, цифры и тире'
    else:
        if User.objects.filter(username=login_val).exists():
            errors['login'] = 'Такой логин уже занят'
    
    # Валидация email
    from django.core.validators import validate_email
    from django.core.exceptions import ValidationError
    if not email:
        errors['email'] = 'Укажите email'
    else:
        try:
            validate_email(email)
            if User.objects.filter(email=email).exists():
                errors['email'] = 'Email уже используется'
        except ValidationError:
            errors['email'] = 'Некорректный email'
    
    # Валидация пароля
    if not password or len(password) < 6:
        errors['password'] = 'Пароль минимум 6 символов'
    if password_repeat != password:
        errors['password_repeat'] = 'Пароли не совпадают'
    if not rules:
        errors['rules'] = 'Необходимо согласие с правилами'

    if errors:
        return JsonResponse({'ok': False, 'errors': errors}, status=400)

    # Создание пользователя в транзакции
    try:
        with transaction.atomic():
            user = User.objects.create_user(
                username=login_val, 
                email=email, 
                password=password,
                first_name=name, 
                last_name=surname
            )
            
            # Обновление профиля с отчеством
            if patronymic:
                user.userprofile.patronymic = patronymic
                user.userprofile.save()
            
            return JsonResponse({'ok': True, 'message': 'Пользователь успешно зарегистрирован'})
    except Exception as e:
        return JsonResponse({'ok': False, 'errors': {'form': 'Ошибка при создании пользователя'}}, status=500)

def api_login(request):
    """API для авторизации пользователя с отслеживанием сессий"""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'errors': {'form': 'Метод не поддерживается'}}, status=405)
    
    data = _json_body(request)
    login_val = (data.get('login') or '').strip()
    password = data.get('password') or ''
    
    if not login_val:
        return JsonResponse({'ok': False, 'errors': {'login': 'Укажите логин'}}, status=400)
    if not password:
        return JsonResponse({'ok': False, 'errors': {'password': 'Укажите пароль'}}, status=400)
    
    user = authenticate(username=login_val, password=password)
    if user is None:
        return JsonResponse({'ok': False, 'errors': {'auth': 'Неверный логин или пароль'}}, status=401)
    
    # Авторизация пользователя
    login(request, user)
    
    # Создание записи о сессии
    try:
        UserSession.objects.create(
            user=user,
            session_key=request.session.session_key,
            ip_address=_get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )
    except Exception:
        pass  # Игнорируем ошибки создания сессии
    
    return JsonResponse({'ok': True, 'message': 'Успешная авторизация'})

def _get_client_ip(request):
    """Получение IP адреса клиента"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

@login_required
@require_POST
def api_profile_update(request):
    """Обновление данных профиля пользователя"""
    data = _json_body(request)
    profile = request.user.userprofile

    first_name = (data.get('first_name') or '').strip()
    last_name = (data.get('last_name') or '').strip()
    patronymic = (data.get('patronymic') or '').strip()
    phone = (data.get('phone') or '').strip()
    address = (data.get('address') or '').strip()

    # Простая валидация
    errors = {}
    if not first_name:
        errors['first_name'] = 'Укажите имя'
    if not last_name:
        errors['last_name'] = 'Укажите фамилию'
    if errors:
        return JsonResponse({'ok': False, 'errors': errors}, status=400)

    request.user.first_name = first_name
    request.user.last_name = last_name
    request.user.save()

    profile.patronymic = patronymic or None
    profile.phone = phone or None
    profile.address = address or None
    profile.save()

    return JsonResponse({'ok': True, 'message': 'Профиль обновлён'})