from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('escala', '0009_invitationlink'),
    ]

    operations = [
        migrations.AddField(
            model_name='schedule',
            name='notes',
            field=models.TextField(blank=True, default=''),
        ),
    ]
