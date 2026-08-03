from django.contrib.auth.models import Group, Permission
from django.db.models.signals import post_migrate, post_save
from django.dispatch import receiver

from escala.models import User


USER_GROUP_PERMISSION_CODENAMES = {
    f"{action}_{model}"
    for model in (
        "organization",
        "team",
        "role",
        "unavailability",
        "schedule",
        "scheduleparticipation",
        "teaminvitation",
        "organizationinvitation",
        "request",
        "user",
    )
    for action in ("add", "change", "delete", "view")
}


@receiver(
    post_migrate,
    dispatch_uid="escala.synchronize_default_users_group",
    weak=False,
)
def synchronize_default_users_group(sender, using="default", **kwargs):
    if sender is not None and sender.label != "escala":
        return

    group, _ = Group.objects.using(using).get_or_create(name="Users")
    permissions = Permission.objects.using(using).filter(
        content_type__app_label="escala",
        codename__in=USER_GROUP_PERMISSION_CODENAMES,
    )
    group.permissions.set(permissions)


@receiver(post_save, sender=User)
def add_user_to_group(sender, instance, created, using="default", **kwargs):
    if created:
        group = Group.objects.using(using).get(name="Users")
        instance.groups.add(group)
