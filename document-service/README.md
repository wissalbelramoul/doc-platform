# Document Service

Service de gestion complète du cycle de vie des documents : upload, versioning, téléchargement, modification, suppression, historique.

## Architecture

```
├── apps/
│   ├── document/
│   │   ├── models.py          # Document, DocumentVersion, DocumentHistory
│   │   ├── serializers.py     # DRF serializers
│   │   ├── views.py           # ViewSets & API endpoints
│   │   ├── permissions.py     # Custom permissions
│   │   ├── validators.py      # File validation
│   │   ├── utils.py           # Event publishing, signed URLs
│   │   ├── admin.py           # Django admin
│   │   ├── signals.py         # Signal handlers
│   │   └── tests.py           # Unit tests
│   └── __init__.py
├── config/
│   ├── settings.py            # Django configuration
│   ├── urls.py                # URL routing
│   └── wsgi.py                # WSGI application
├── manage.py                  # Django CLI
├── Dockerfile                 # Container configuration
├── requirements.txt           # Python dependencies
└── README.md
```

## Modèles de données

### Document
- **id** (UUID): Identifiant unique
- **title**: Titre du document
- **description**: Description
- **category**: Catégorie
- **keywords**: Mots-clés (séparés par des virgules)
- **owner_id**: ID du propriétaire (référence vers User Service)
- **block_id**: ID du bloc
- **service_id**: ID du service
- **department_id**: ID du département
- **status**: État (draft, pending, validated, rejected)
- **current_version**: Référence à la version courante
- **created_at**, **updated_at**, **deleted_at** (soft delete)

### DocumentVersion
Gestion complète du versioning :
- Chaque modification de fichier crée une nouvelle version
- Jamais d'écrasement du fichier original
- Historique complet conservé
- Restauration facile à une version antérieure

### DocumentHistory
Audit trail pour toutes les actions :
- upload, modification, suppression, téléchargement, consultation
- Utilisateur qui a effectué l'action
- Détails additionnels (JSON)
- Timestamp

## Endpoints API

### Documents

```
POST   /api/documents/                          Créer un document
GET    /api/documents/                          Lister les documents
GET    /api/documents/{id}/                     Détails d'un document
PUT    /api/documents/{id}/                     Modifier un document
PATCH  /api/documents/{id}/                     Modification partielle
DELETE /api/documents/{id}/                     Supprimer (soft delete)
```

### Versions

```
GET    /api/documents/{id}/versions/            Lister toutes les versions
POST   /api/documents/{id}/restore_version/     Restaurer une version ancienne
GET    /api/versions/                           Lister les versions
GET    /api/versions/{id}/                      Détails d'une version
```

### Teléchargement & Historique

```
GET    /api/documents/{id}/download/            Télécharger la version courante
GET    /api/documents/{id}/history/             Historique complet
POST   /api/documents/{id}/restore/             Restaurer un document supprimé
```

## Filtrage & Recherche

```
GET /api/documents/?status=pending              Filtrer par statut
GET /api/documents/?category=finance            Filtrer par catégorie
GET /api/documents/?block_id=1                  Filtrer par bloc
GET /api/documents/?search=facture              Recherche texte
GET /api/documents/?ordering=-created_at        Tri
```

## Logique métier

### Upload
1. Valider le type de fichier (whitelist stricte)
2. Vérifier la taille (max 20 Mo)
3. Calculer le hash SHA-256 pour l'intégrité
4. Stocker le fichier (local, S3, ou MinIO)
5. Créer l'enregistrement Document + Version
6. Statut initial : `pending`
7. Émettre événement `document.created` (RabbitMQ)

### Modification
- Toute modification de fichier crée une **nouvelle version**
- Les métadonnées peuvent être modifiées sans créer de version
- Le document repasse en statut `pending` après modification

### Suppression
- **Soft delete** uniquement (champ `deleted_at`)
- Jamais de suppression physique immédiate
- Purge définitive après 90 jours (configurable) via Celery

### Téléchargement
- URL signée temporaire (expire après 15 minutes)
- Chaque téléchargement est enregistré dans `DocumentHistory`
- Support S3, MinIO, et stockage local

### Sécurité fichiers

**Fichiers texte/code** (.py, .html, .js, .svg) :
- Scan du contenu pour détecter les patterns malveillants
- Servir avec header `Content-Disposition: attachment` (force le téléchargement)
- Jamais d'exécution côté serveur
- Affichage avec syntax highlighting côté frontend

## Intégrations

| Service | Interaction |
|---|---|
| **Validation Service** | Reçoit `document.created` → déclenche workflow |
| **Search Service** | Reçoit `document.validated` → indexe le contenu |
| **Notification Service** | Reçoit tous les événements documents |
| **Stats Service** | Consomme les événements pour compteurs |

## Événements RabbitMQ

Le service publie les événements suivants :

```
document.created
document.modified
document.deleted
document.restored
document.version_restored
document.downloaded
document.validated (reçu d'autres services)
document.rejected
document.permanently_deleted
```

## Installation

### Prérequis
- Python 3.11+
- PostgreSQL 13+
- RabbitMQ 3.11+
- MinIO ou S3 (optionnel)

### Setup local

```bash
# Cloner et naviguer
cd document-service

# Créer venv
python -m venv venv
source venv/bin/activate  # ou `venv\Scripts\activate` sur Windows

# Installer dépendances
pip install -r requirements.txt

# Configuration
cp .env.example .env
# Éditer .env avec vos paramètres

# Migrations
python manage.py migrate

# Créer super user
python manage.py createsuperuser

# Démarrer
python manage.py runserver
```

### Avec Docker

```bash
# Construire
docker build -t document-service .

# Démarrer avec docker-compose
cd ..
docker compose up document-service

# Migrations
docker compose exec document-service python manage.py migrate

# Accéder à l'API
curl http://localhost:8000/api/documents/
```

## Variables d'environnement

```
SECRET_KEY                    Clé secrète Django
DEBUG                         Mode debug (False en prod)
ALLOWED_HOSTS                 Hosts autorisés
DB_NAME                       Nom de la base
DB_USER                       Utilisateur PostgreSQL
DB_PASSWORD                   Mot de passe PostgreSQL
DB_HOST                       Host PostgreSQL
DB_PORT                       Port PostgreSQL
CORS_ALLOWED_ORIGINS          Origins CORS
STORAGE_TYPE                  local | s3 | minio
AWS_ACCESS_KEY_ID             (si S3)
AWS_SECRET_ACCESS_KEY         (si S3)
MINIO_ENDPOINT                (si MinIO)
MINIO_ACCESS_KEY              (si MinIO)
RABBITMQ_HOST                 Host RabbitMQ
RABBITMQ_PORT                 Port RabbitMQ
SOFT_DELETE_RETENTION_DAYS     Jours avant purge (défaut: 90)
```

## Validation des fichiers

### Extensions autorisées

Documents : pdf, doc, docx, xls, xlsx, ppt, pptx
Code : py, c, cpp, h, java, js, ts, html, css, sql, sh
Texte : txt, md, csv, json, xml, yaml
Images : png, jpg, jpeg, gif, svg

### Types MIME autorisés

- text/* (pour le code)
- application/json
- application/pdf
- application/msword
- image/*
- Et autres (voir `settings.ALLOWED_MIME_TYPES`)

### Scan de sécurité

Les fichiers potentiellement dangereux (.html, .js, .svg) sont scannés pour :
- `<script>`
- `javascript:`
- Handlers d'événements (`onerror=`, `onload=`, etc.)
- Fonctions dangereuses (`eval()`, `exec()`)

## Permissions

- **Employé** : Lecture/écriture ses propres documents
- **Chef de bloc** : Lecture bloc + approbation
- **Chef de service/département** : Lecture élargie
- **Admin** : Accès complet

## Tests

```bash
# Lancer les tests
python manage.py test

# Avec coverage
pip install coverage
coverage run --source='apps' manage.py test
coverage report
coverage html
```

## Développement

### Créer une migration

```bash
python manage.py makemigrations

python manage.py migrate
```

### Lancer le serveur de développement

```bash
python manage.py runserver 0.0.0.0:8000
```

### Accéder à l'admin Django

```
http://localhost:8000/admin/
```

### Logs

Vérifier les logs pour voir les événements publiés et les erreurs :

```bash
docker compose logs -f document-service
```

## Tâches Celery

Les tâches asynchrones suivantes sont disponibles :

```python
# Nettoyer les documents supprimés définitivement
cleanup_soft_deleted_documents()

# Scan antivirus (optionnel)
scan_document_for_viruses.delay(document_id)

# Générer miniatures PDF
generate_pdf_thumbnail.delay(version_id)
```

## Performance

- **Indexes** sur owner_id, status, deleted_at, category pour requêtes rapides
- **Pagination** (20 documents par défaut)
- **Filtrage** par DjangoFilterBackend
- **Select_related** pour eager loading des versions
- **Cache** recommandé pour le Search Service après indexation

## Production

### Checklist
- [ ] `DEBUG=False` dans .env
- [ ] `SECRET_KEY` robuste
- [ ] ALLOWED_HOSTS configuré
- [ ] CORS restreint
- [ ] HTTPS/SSL activé
- [ ] Base de données sécurisée
- [ ] RabbitMQ sécurisé
- [ ] Backups réguliers
- [ ] Monitoring et alertes configurés
- [ ] Logs centralisés (ELK, Datadog, etc.)

### Scaling

- Déployer avec plusieurs workers Gunicorn
- Utiliser Celery avec plusieurs workers pour tâches async
- Cacher les réponses API fréquentes
- Optimiser les requêtes BD (N+1 queries)
- CDN pour fichiers statiques

## Licence

MIT
