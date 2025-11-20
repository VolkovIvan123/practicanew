from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class Category(models.Model):
    """Категория товара (например, лазерные/струйные/термо принтеры)"""
    slug = models.SlugField(max_length=50, unique=True, verbose_name="Слаг")
    name = models.CharField(max_length=100, unique=True, verbose_name="Название")

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"

    def __str__(self):
        return self.name

class Product(models.Model):
    """Товар каталога"""
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='products', verbose_name="Категория")
    name = models.CharField(max_length=200, verbose_name="Наименование")
    slug = models.SlugField(max_length=220, unique=True, verbose_name="Слаг")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Цена")
    year = models.PositiveSmallIntegerField(verbose_name="Год выпуска")
    country = models.CharField(max_length=100, verbose_name="Страна-производитель")
    model = models.CharField(max_length=100, verbose_name="Модель")
    image = models.ImageField(upload_to='products/', blank=True, null=True, verbose_name="Фото")
    stock = models.PositiveIntegerField(default=0, verbose_name="Остаток на складе")
    in_stock = models.BooleanField(default=True, verbose_name="В наличии")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Добавлен")

    class Meta:
        verbose_name = "Товар"
        verbose_name_plural = "Товары"
        ordering = ['-created_at']  # по умолчанию новизна

    def __str__(self):
        return self.name

class Order(models.Model):
    """Заказ пользователя"""
    STATUS_CHOICES = [
        ('new', 'Новый'),
        ('processing', 'В обработке'),
        ('shipped', 'Отправлен'),
        ('delivered', 'Доставлен'),
        ('cancelled', 'Отменен'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Пользователь")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создан")
    total_price = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Сумма")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new', verbose_name="Статус")

    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"
        ordering = ['-created_at']  # От новых к старым

    def __str__(self):
        return f"Заказ #{self.id} от {self.created_at.strftime('%d.%m.%Y %H:%M')}"
    
    @property
    def can_be_deleted(self):
        """Проверка, можно ли удалить заказ (только новые)"""
        return self.status == 'new'

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items', verbose_name="Заказ")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, verbose_name="Товар")
    quantity = models.PositiveIntegerField(verbose_name="Кол-во")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Цена за ед.")

    class Meta:
        verbose_name = "Позиция заказа"
        verbose_name_plural = "Позиции заказа"

    def line_total(self):
        return self.price * self.quantity

class UserProfile(models.Model):
    """Расширенный профиль пользователя"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name="Пользователь")
    patronymic = models.CharField(max_length=100, blank=True, null=True, verbose_name="Отчество")
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="Телефон")
    birth_date = models.DateField(blank=True, null=True, verbose_name="Дата рождения")
    address = models.TextField(blank=True, null=True, verbose_name="Адрес")
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True, verbose_name="Аватар")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    
    class Meta:
        verbose_name = "Профиль пользователя"
        verbose_name_plural = "Профили пользователей"
    
    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name} ({self.user.username})"
    
    @property
    def full_name(self):
        """Полное имя пользователя"""
        parts = [self.user.first_name, self.user.last_name]
        if self.patronymic:
            parts.insert(1, self.patronymic)
        return ' '.join(filter(None, parts))

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Автоматически создавать профиль при создании пользователя"""
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Сохранять профиль при сохранении пользователя"""
    if hasattr(instance, 'userprofile'):
        instance.userprofile.save()

class UserSession(models.Model):
    """Модель для отслеживания сессий пользователей"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Пользователь")
    session_key = models.CharField(max_length=40, verbose_name="Ключ сессии")
    ip_address = models.GenericIPAddressField(verbose_name="IP адрес")
    user_agent = models.TextField(verbose_name="User Agent")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата входа")
    last_activity = models.DateTimeField(auto_now=True, verbose_name="Последняя активность")
    is_active = models.BooleanField(default=True, verbose_name="Активна")
    
    class Meta:
        verbose_name = "Сессия пользователя"
        verbose_name_plural = "Сессии пользователей"
        unique_together = ['user', 'session_key']
    
    def __str__(self):
        return f"{self.user.username} - {self.created_at.strftime('%d.%m.%Y %H:%M')}"
