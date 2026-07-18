"""
Initial migrations for Document Service models
"""
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Document',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('title', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True, null=True)),
                ('category', models.CharField(max_length=100)),
                ('keywords', models.TextField(blank=True, help_text='Comma-separated tags')),
                ('owner_id', models.IntegerField()),
                ('block_id', models.IntegerField(blank=True, null=True)),
                ('service_id', models.IntegerField(blank=True, null=True)),
                ('department_id', models.IntegerField(blank=True, null=True)),
                ('status', models.CharField(
                    choices=[('draft', 'Brouillon'), ('pending', 'En attente'), ('validated', 'Validé'), ('rejected', 'Refusé')],
                    default='pending',
                    max_length=20
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='DocumentVersion',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('version_number', models.IntegerField()),
                ('file_path', models.CharField(max_length=500)),
                ('file_size', models.BigIntegerField()),
                ('mime_type', models.CharField(max_length=100)),
                ('file_hash', models.CharField(max_length=64, unique=True)),
                ('author_id', models.IntegerField()),
                ('comment', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('document', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='versions', to='document.document')),
            ],
            options={
                'ordering': ['-version_number'],
            },
        ),
        migrations.CreateModel(
            name='DocumentHistory',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('user_id', models.IntegerField()),
                ('action', models.CharField(
                    choices=[('upload', 'Upload'), ('modification', 'Modification'), ('deletion', 'Suppression'), 
                            ('download', 'Téléchargement'), ('view', 'Consultation'), ('validation', 'Validation'),
                            ('rejection', 'Rejet'), ('restore', 'Restauration')],
                    max_length=20
                )),
                ('details', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('document', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='history', to='document.document')),
            ],
            options={
                'verbose_name_plural': 'Document Histories',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddField(
            model_name='document',
            name='current_version',
            field=models.OneToOneField(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='current_document', to='document.documentversion'),
        ),
        migrations.AddIndex(
            model_name='documenthistory',
            index=models.Index(fields=['document'], name='document_doc_id_idx'),
        ),
        migrations.AddIndex(
            model_name='documenthistory',
            index=models.Index(fields=['user_id'], name='document_user_idx'),
        ),
        migrations.AddIndex(
            model_name='documenthistory',
            index=models.Index(fields=['action'], name='document_action_idx'),
        ),
        migrations.AddIndex(
            model_name='documentversion',
            index=models.Index(fields=['document'], name='document_ver_doc_idx'),
        ),
        migrations.AddIndex(
            model_name='documentversion',
            index=models.Index(fields=['file_hash'], name='document_hash_idx'),
        ),
        migrations.AddIndex(
            model_name='document',
            index=models.Index(fields=['owner_id'], name='document_owner_idx'),
        ),
        migrations.AddIndex(
            model_name='document',
            index=models.Index(fields=['status'], name='document_status_idx'),
        ),
        migrations.AddIndex(
            model_name='document',
            index=models.Index(fields=['deleted_at'], name='document_deleted_idx'),
        ),
        migrations.AddIndex(
            model_name='document',
            index=models.Index(fields=['category'], name='document_category_idx'),
        ),
    ]
