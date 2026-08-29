from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('escala', '0012_sync_organization_creator_group'),
    ]

    operations = [
        migrations.DeleteModel(
            name='OrganizationCreationRequest',
        ),
    ]
