from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import Group
from escala.models import User

@receiver(post_save, sender=User)
def add_user_to_group(sender, instance, created, **kwargs):
    if created:
        group = Group.objects.get(name='Users')
        instance.groups.add(group)
