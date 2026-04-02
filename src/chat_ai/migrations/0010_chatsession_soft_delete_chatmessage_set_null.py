import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chat_ai', '0009_alter_aiconsistencycorrection_message'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Soft delete: preserva sessão e todo seu histórico ao invés de apagar
        migrations.AddField(
            model_name='chatsession',
            name='deleted_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='chatsession',
            name='deleted_by',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='deleted_sessions',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        # Protege mensagens do CASCADE: se uma sessão for hard-deletada (purga admin),
        # as mensagens sobrevivem com session=NULL para manter a cadeia RLHF intacta.
        migrations.AlterField(
            model_name='chatmessage',
            name='session',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='messages',
                to='chat_ai.chatsession',
            ),
        ),
    ]
