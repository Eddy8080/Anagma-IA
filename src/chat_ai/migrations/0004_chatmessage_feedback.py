from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chat_ai', '0003_chatsession_pinned'),
    ]

    operations = [
        migrations.AddField(
            model_name='chatmessage',
            name='feedback',
            field=models.CharField(
                blank=True,
                choices=[('like', 'Curtiu'), ('dislike', 'Não curtiu')],
                max_length=10,
                null=True,
            ),
        ),
    ]
