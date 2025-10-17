from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import UserProfile, UserSession, Category, Product

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Профиль'
    fields = ('patronymic', 'phone', 'birth_date', 'address', 'avatar')

class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'date_joined')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'date_joined')

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'full_name', 'phone', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'patronymic', 'phone')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'ip_address', 'created_at', 'last_activity', 'is_active')
    list_filter = ('is_active', 'created_at', 'last_activity')
    search_fields = ('user__username', 'ip_address')
    readonly_fields = ('created_at', 'last_activity')

# Перерегистрируем User с новым админом
admin.site.unregister(User)
admin.site.register(User, UserAdmin)

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    prepopulated_fields = { 'slug': ('name',) }
    search_fields = ('name',)

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'year', 'in_stock', 'created_at')
    list_filter = ('category', 'in_stock', 'year', 'country')
    search_fields = ('name', 'model')
    prepopulated_fields = { 'slug': ('name',) }
