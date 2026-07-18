# Generated migration for OutboxEvent model

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='OutboxEvent',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('routing_key', models.CharField(max_length=255)),
                ('payload', models.JSONField()),
                ('is_published', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('published_at', models.DateTimeField(blank=True, null=True)),
                ('attempt_count', models.PositiveIntegerField(default=0)),
                ('last_error', models.TextField(blank=True, null=True)),
            ],
            options={
                'ordering': ['created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='outboxevent',
            index=models.Index(fields=['is_published', 'created_at'], name='org_outboxe_is_publ_idx'),
        ),
    ]
