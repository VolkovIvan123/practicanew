from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.db import transaction
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import UserProfile, UserSession, Category, Product, Order, OrderItem

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
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)
    list_display = ('name', 'slug', 'products_count')
    
    def products_count(self, obj):
        """Количество товаров в категории"""
        return obj.products.count()
    products_count.short_description = 'Товаров'

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'year', 'stock', 'in_stock', 'created_at')
    list_filter = ('category', 'in_stock', 'year', 'country')
    search_fields = ('name', 'model')
    prepopulated_fields = {'slug': ('name',)}
    fieldsets = (
        ('Основная информация', {
            'fields': ('category', 'name', 'slug', 'price', 'image')
        }),
        ('Детали', {
            'fields': ('year', 'country', 'model')
        }),
        ('Склад', {
            'fields': ('stock', 'in_stock')
        }),
    )

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product', 'quantity', 'price', 'line_total_display')
    
    def line_total_display(self, obj):
        """Отображение суммы по позиции"""
        if obj.pk:
            return f"{obj.line_total()} ₽"
        return "-"
    line_total_display.short_description = 'Сумма'

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'created_at_display', 'customer_full_name', 'items_count_display', 'status_display', 'total_price_display', 'cancellation_reason_display')
    list_filter = ('status', 'created_at')
    date_hierarchy = 'created_at'
    inlines = [OrderItemInline]
    readonly_fields = ('created_at', 'total_price', 'customer_full_name_display', 'items_count_display')
    actions = ['confirm_orders', 'cancel_orders']
    
    fieldsets = (
        ('Информация о заказе', {
            'fields': ('user', 'customer_full_name_display', 'created_at', 'status', 'total_price')
        }),
        ('Отмена заказа', {
            'fields': ('cancellation_reason',),
            'classes': ('collapse',),
        }),
    )
    
    def created_at_display(self, obj):
        """Отображение даты и времени заказа"""
        return obj.created_at.strftime('%d.%m.%Y %H:%M')
    created_at_display.short_description = 'Дата и время'
    created_at_display.admin_order_field = 'created_at'
    
    def customer_full_name(self, obj):
        """ФИО заказчика"""
        return obj.customer_full_name
    customer_full_name.short_description = 'Заказчик'
    customer_full_name.admin_order_field = 'user__last_name'
    
    def customer_full_name_display(self, obj):
        """ФИО заказчика в форме редактирования"""
        return obj.customer_full_name
    customer_full_name_display.short_description = 'ФИО заказчика'
    
    def items_count_display(self, obj):
        """Количество товаров в заказе"""
        return obj.items_count
    items_count_display.short_description = 'Кол-во товаров'
    
    def status_display(self, obj):
        """Цветное отображение статуса"""
        colors = {
            'new': '#007bff',
            'confirmed': '#28a745',
            'processing': '#17a2b8',
            'shipped': '#ffc107',
            'delivered': '#28a745',
            'cancelled': '#dc3545',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_display.short_description = 'Статус'
    status_display.admin_order_field = 'status'
    
    def total_price_display(self, obj):
        """Отображение общей суммы"""
        return f"{obj.total_price} ₽"
    total_price_display.short_description = 'Сумма'
    total_price_display.admin_order_field = 'total_price'
    
    def cancellation_reason_display(self, obj):
        """Отображение причины отказа"""
        if obj.cancellation_reason:
            return format_html(
                '<span style="color: #dc3545;" title="{}">⚠️ {}</span>',
                obj.cancellation_reason,
                obj.cancellation_reason[:50] + ('...' if len(obj.cancellation_reason) > 50 else '')
            )
        return "-"
    cancellation_reason_display.short_description = 'Причина отказа'
    
    def confirm_orders(self, request, queryset):
        """Действие: подтвердить выбранные заказы"""
        count = 0
        for order in queryset:
            if order.status == 'new':
                order.status = 'confirmed'
                order.save()
                count += 1
        self.message_user(request, f'Подтверждено заказов: {count}')
    confirm_orders.short_description = 'Подтвердить выбранные заказы'
    
    def cancel_orders(self, request, queryset):
        """Действие: отменить выбранные заказы (требует причину)"""
        # Это действие будет обрабатываться через кастомную форму
        # Для простоты используем стандартный механизм Django
        count = 0
        reason = request.POST.get('cancellation_reason', 'Отменено администратором')
        for order in queryset:
            if order.status not in ('cancelled', 'delivered'):
                with transaction.atomic():
                    # Возвращаем товары на склад
                    for item in order.items.all():
                        product = item.product
                        product.stock += item.quantity
                        product.in_stock = True
                        product.save()
                    
                    order.status = 'cancelled'
                    order.cancellation_reason = reason
                    order.save()
                    count += 1
        self.message_user(request, f'Отменено заказов: {count}')
    cancel_orders.short_description = 'Отменить выбранные заказы'
    
    def get_queryset(self, request):
        """Оптимизация запросов"""
        qs = super().get_queryset(request)
        return qs.select_related('user').prefetch_related('items', 'items__product')
    
    def save_model(self, request, obj, form, change):
        """Сохранение модели с обработкой отмены заказа"""
        if change and 'cancellation_reason' in form.changed_data and obj.status == 'cancelled':
            # Если заказ отменяется, возвращаем товары на склад
            with transaction.atomic():
                for item in obj.items.all():
                    product = item.product
                    product.stock += item.quantity
                    product.in_stock = True
                    product.save()
        super().save_model(request, obj, form, change)
