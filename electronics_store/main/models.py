from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

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
