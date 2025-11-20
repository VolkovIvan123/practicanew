
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import ensure_csrf_cookie
from django.http import JsonResponse
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from .models import UserProfile, UserSession, Product, Category, Order, OrderItem
from django.views.decorators.http import require_POST
import json
import re

@ensure_csrf_cookie
def home(request):
    return render(request, 'index.html')

def catalog(request):
    """Каталог с фильтрами и сортировкой, минимум JS, всё на сервере"""
    qs = Product.objects.filter(in_stock=True)

    # Фильтр по категории (slug)
    category_slug = request.GET.get('category')
    active_category = None
    if category_slug:
        active_category = Category.objects.filter(slug=category_slug).first()
        if active_category:
            qs = qs.filter(category=active_category)

    # Сортировка
    sort = request.GET.get('sort')  # year|name|price
    sort_map = {
        'year': 'year',
        'name': 'name',
        'price': 'price',
    }
    if sort in sort_map:
        qs = qs.order_by(sort_map[sort])
    else:
        qs = qs.order_by('-created_at')  # по новизне

    context = {
        'products': qs.select_related('category'),
        'categories': Category.objects.all(),
        'active_category': active_category,
        'active_sort': sort or 'new',
    }
    return render(request, 'catalog.html', context)

def contacts(request):
    return render(request, 'contacts.html')

@login_required
def profile(request):
    """Страница профиля пользователя"""
    user_profile = request.user.userprofile
    # Получаем заказы пользователя, упорядоченные от новых к старым
    orders = Order.objects.filter(user=request.user).prefetch_related('items__product').order_by('-created_at')
    context = {
        'user_profile': user_profile,
        'user_sessions': UserSession.objects.filter(user=request.user, is_active=True).order_by('-last_activity')[:5],
        'orders': orders
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
    # Корзина хранится в сессии как словарь {product_id: qty}
    cart = request.session.get('cart', {})
    items = []
    total = 0
    if cart:
        products = Product.objects.filter(id__in=cart.keys())
        for p in products:
            qty = max(0, min(int(cart.get(str(p.id), 0)), p.stock))
            line = float(p.price) * qty
            total += line
            items.append({ 'product': p, 'qty': qty, 'line': line })
    return render(request, 'cart.html', { 'items': items, 'total': total })

def product_detail(request, slug):
    product = Product.objects.filter(slug=slug, in_stock=True).select_related('category').first()
    if not product:
        from django.http import Http404
        raise Http404('Товар не найден или отсутствует в наличии')
    return render(request, 'product_detail.html', { 'product': product })

@require_POST
def api_cart_add(request):
    data = _json_body(request)
    product_id = str(data.get('product_id'))
    delta = int(data.get('delta', 1))  # +1 или -1
    cart = request.session.get('cart', {})
    try:
        p = Product.objects.get(id=product_id, in_stock=True)
    except Product.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Товар недоступен'}, status=404)
    current = int(cart.get(product_id, 0))
    new_qty = max(0, min(current + delta, p.stock))
    if new_qty == 0:
        cart.pop(product_id, None)
    else:
        cart[product_id] = new_qty
    request.session['cart'] = cart
    return JsonResponse({'ok': True, 'qty': new_qty})

@login_required
@require_POST
def api_checkout(request):
    data = _json_body(request)
    password = data.get('password') or ''
    if not request.user.check_password(password):
        return JsonResponse({'ok': False, 'error': 'Неверный пароль'}, status=400)

    cart = request.session.get('cart', {})
    if not cart:
        return JsonResponse({'ok': False, 'error': 'Корзина пуста'}, status=400)

    products = Product.objects.select_for_update().filter(id__in=cart.keys(), in_stock=True)
    if products.count() == 0:
        return JsonResponse({'ok': False, 'error': 'Товары недоступны'}, status=400)

    # Создание заказа с проверкой остатков
    try:
        with transaction.atomic():
            order = Order.objects.create(user=request.user, total_price=0)
            total = 0
            id_to_product = { str(p.id): p for p in products }
            for pid, qty in cart.items():
                p = id_to_product.get(str(pid))
                if not p:
                    continue
                qty = max(0, min(int(qty), p.stock))
                if qty == 0:
                    continue
                OrderItem.objects.create(order=order, product=p, quantity=qty, price=p.price)
                p.stock -= qty
                if p.stock == 0:
                    p.in_stock = False
                p.save()
                total += float(p.price) * qty
            if total == 0:
                raise Exception('empty')
            order.total_price = total
            order.save()
            # Очистить корзину
            request.session['cart'] = {}
            return JsonResponse({'ok': True, 'order_id': order.id, 'total': total})
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Не удалось оформить заказ'}, status=500)

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

@login_required
@require_POST
def api_order_delete(request, order_id):
    """Удаление нового заказа"""
    try:
        order = Order.objects.get(id=order_id, user=request.user)
    except Order.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Заказ не найден'}, status=404)
    
    # Проверяем, что заказ можно удалить (только новые)
    if not order.can_be_deleted:
        return JsonResponse({'ok': False, 'error': 'Можно удалить только новые заказы'}, status=400)
    
    # Возвращаем товары на склад
    try:
        with transaction.atomic():
            for item in order.items.all():
                product = item.product
                product.stock += item.quantity
                product.in_stock = True
                product.save()
            order.delete()
            return JsonResponse({'ok': True, 'message': 'Заказ удален'})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': 'Ошибка при удалении заказа'}, status=500)