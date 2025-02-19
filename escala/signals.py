from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import Group
from escala.models import Usuario

@receiver(post_save, sender=Usuario)
def add_user_to_group(sender, instance, created, **kwargs):
    if created:
        group = Group.objects.get(name='Usuarios')
        instance.groups.add(group)
