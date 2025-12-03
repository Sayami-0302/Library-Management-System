from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('lib', '0015_alter_notification_notification_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='admin',
            name='is_active',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='admin',
            name='is_superuser',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='book',
            name='status',
            field=models.CharField(choices=[('available', 'Available'), ('issued', 'Issued'), ('lost', 'Lost')], default='available', max_length=20),
        ),
    ]


