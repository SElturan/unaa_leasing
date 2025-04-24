from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

User = get_user_model()

@receiver(pre_save, sender=User)
def invalidate_tokens_on_role_change(sender, instance, **kwargs):
    if not instance.pk:
        return  # новый пользователь

    try:
        old_user = User.objects.get(pk=instance.pk)
    except User.DoesNotExist:
        return

    # Проверка: изменился ли статус роли
    role_changed = (
        old_user.is_staff != instance.is_staff or
        old_user.is_superuser != instance.is_superuser
    )

    if role_changed:
        # инвалидируем все refresh токены
        tokens = OutstandingToken.objects.filter(user=instance)
        for token in tokens:
            try:
                BlacklistedToken.objects.get_or_create(token=token)
            except Exception:
                pass
