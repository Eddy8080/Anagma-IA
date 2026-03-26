from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chat_ai', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='chatsession',
            name='pinned',
            field=models.BooleanField(default=False),
        ),
    ]
