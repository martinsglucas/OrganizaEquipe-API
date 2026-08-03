from django.db import migrations


def create_users_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.using(schema_editor.connection.alias).get_or_create(name="Users")


class Migration(migrations.Migration):

    dependencies = [
        ("escala", "0005_teamjoinrequest"),
    ]

    operations = [
        migrations.RunPython(create_users_group, migrations.RunPython.noop),
    ]
