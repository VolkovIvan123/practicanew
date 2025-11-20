# main/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),  # Главная страница
    path('catalog/', views.catalog, name='catalog'),
    path('contacts/', views.contacts, name='contacts'),
    path('product/<slug:slug>/', views.product_detail, name='product_detail'),
    path('profile/', views.profile, name='profile'),
    path('cart/', views.cart, name='cart'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register, name='register'),
    path('logout/', views.logout_view, name='logout'),
    # API
    path('api/register', views.api_register, name='api_register'),
    path('api/login', views.api_login, name='api_login'),
    path('api/profile/update', views.api_profile_update, name='api_profile_update'),
    path('api/cart/add', views.api_cart_add, name='api_cart_add'),
    path('api/checkout', views.api_checkout, name='api_checkout'),
    path('api/order/<int:order_id>/delete', views.api_order_delete, name='api_order_delete'),
]