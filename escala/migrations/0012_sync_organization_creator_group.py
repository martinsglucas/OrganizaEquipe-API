from django.db import migrations


CREATOR_GROUP_NAME = 'Organization Creators'


def synchronize_organization_creator_group(apps, schema_editor):
    group_model = apps.get_model('auth', 'Group')
    permission_model = apps.get_model('auth', 'Permission')
    using = schema_editor.connection.alias

    users_group, _ = group_model.objects.using(using).get_or_create(name='Users')
    creator_group, _ = group_model.objects.using(using).get_or_create(
        name=CREATOR_GROUP_NAME,
    )
    permission = permission_model.objects.using(using).filter(
        content_type__app_label='escala',
        codename='add_organization',
    ).first()
    if permission is None:
        return

    users_group.permissions.remove(permission)
    creator_group.permissions.set([permission])


class Migration(migrations.Migration):
    dependencies = [
        ('escala', '0011_team_visibility'),
    ]

    operations = [
        migrations.RunPython(
            synchronize_organization_creator_group,
            migrations.RunPython.noop,
        ),
    ]
