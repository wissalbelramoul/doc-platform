# Microservice Organisation — code

Implémentation du microservice décrit dans le rapport `microservice-organisation-v2.md`
(hiérarchie à 4 niveaux : DOS/DES → DO/DE → DA → CS).

## 🚀 Démarrage rapide (Docker)

```bash
# Copier la configuration
cp .env.example .env

# Démarrer les conteneurs
docker-compose up -d

# Initialiser la BD
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py createsuperuser

# Accès
# - API : http://localhost:8000/api/
# - Admin : http://localhost:8000/admin/
# - RabbitMQ : http://localhost:15672/ (guest/guest)
```

**Voir [DOCKER.md](DOCKER.md) pour la documentation complète.**

## Installation locale

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # puis éditer les valeurs (DB, RabbitMQ, JWT_SHARED_SECRET)
```

Un PostgreSQL et un RabbitMQ doivent être accessibles (voir `.env`).

```bash
python manage.py migrate
python manage.py createsuperuser   # pour accéder à /admin/
python manage.py runserver
```

En parallèle, deux processes dédié doivent tourner :

**Terminal 2 — Consumer d'événements (document.created/deleted, user.service_changed)**
```bash
python manage.py consume_events
```

**Terminal 3 — Consumer d'outbox (publication garantie des événements)**
```bash
python manage.py process_outbox
```

## Tests

```bash
python manage.py test org
```

## Déploiement avec Docker

### Configuration rapide

```bash
# 1. Copier le fichier d'environnement
cp .env.example .env

# 2. Lancer les conteneurs
docker-compose up -d

# 3. Vérifier que tout fonctionne
docker-compose logs web
docker-compose ps
```

Puis accéder à :
- **API** : http://localhost:8000/api/
- **Admin** : http://localhost:8000/admin/
- **RabbitMQ Management** : http://localhost:15672/ (guest/guest)

### Commandes utiles

```bash
# Afficher les logs en temps réel
docker-compose logs -f web

# Exécuter les migrations
docker-compose exec web python manage.py migrate

# Créer un superuser
docker-compose exec web python manage.py createsuperuser

# Lancer les tests
docker-compose exec web python manage.py test org

# Arrêter tous les conteneurs
docker-compose down

# Supprimer les volumes (réinitialiser la BD)
docker-compose down -v
```

### Structure des conteneurs

| Service | Port | Description |
|---------|------|-------------|
| **web** | 8000 | Application Django (API + Admin) |
| **postgres** | 5432 | Base de données |
| **rabbitmq** | 5672/15672 | Message broker + UI |
| **consumer_events** | — | Consumer d'événements externes |
| **consumer_outbox** | — | Consumer d'outbox (retry des événements) |

### Configuration personnalisée

Éditer `.env` pour modifier :

```bash
# Sécurité
DEBUG=False                              # Production
SECRET_KEY=your-production-secret-key
ALLOWED_HOSTS=api.example.com,localhost

# Base de données
POSTGRES_USER=org_prod
POSTGRES_PASSWORD=strong-password

# JWT (partagé avec Auth-service)
JWT_SHARED_SECRET=your-shared-secret
```

Puis relancer : `docker-compose up -d`

### Monitoring

Voir les métriques des conteneurs :
```bash
docker stats
```

Voir l'état des outbox events (événements à publier) :
```bash
docker-compose exec web python manage.py shell
>>> from org.models import OutboxEvent
>>> OutboxEvent.objects.filter(is_published=False).count()
```

### Dépannage

**RabbitMQ refuse la connexion** :
```bash
docker-compose logs rabbitmq
```

**Migration échouée** :
```bash
docker-compose exec web python manage.py migrate --fake-initial
```

**Réinitialiser complètement** :
```bash
docker-compose down -v          # Supprimer volumes
docker-compose up --build -d    # Reconstruire et relancer
docker-compose exec web python manage.py createsuperuser
```

### Production

Pour la production, adapter la configuration :

1. **Utiliser un reverse proxy** (nginx) : Voir [docker-compose.prod.yml](docker-compose.prod.yml) et [nginx.conf](nginx.conf)
2. **Augmenter les workers Gunicorn** : Modifiable dans [docker-compose.prod.yml](docker-compose.prod.yml)
3. **Utiliser des secrets** : Copier [.env.prod.example](.env.prod.example) en `.env.prod` et remplir les vraies valeurs
4. **Activer HTTPS** : Certificats SSL/TLS dans le nginx.conf
5. **Configurer les backups** : Scripts pour PostgreSQL

**Lancer la production** :
```bash
cp .env.prod.example .env
# Éditer .env avec les vraies valeurs
docker-compose -f docker-compose.prod.yml up -d
```

### 1. Outbox Pattern pour la livraison garantie des événements

**Problème** : Publication RabbitMQ synchrone et best-effort perdait les événements
en cas d'indisponibilité du broker.

**Solution** : Implémentation du pattern Outbox avec persistence locale et retry
automatique avec backoff exponentiel.

**Fichiers** :
- `org/models.py` — Modèle `OutboxEvent`
- `org/events/publisher.py` — Fonction `publish_event()` modifiée
- `org/management/commands/process_outbox.py` — Consumer avec retry
- `org/migrations/0001_add_outbox_event_model.py` — Migration Django

**Utilisation** :
```bash
# Terminal 1
python manage.py runserver

# Terminal 2
python manage.py process_outbox --batch-size 10 --poll-interval 5
```

**Documentation** : Voir [org/events/OUTBOX_PATTERN.md](org/events/OUTBOX_PATTERN.md)

### 2. Droits implicites pour DOS/DES sur leur branche

**Changement** : Les DOS/DES ont maintenant le droit de créer/modifier les services
dans toutes les Directions de leur branche (OPERATIONNEL pour DOS, ENGINEERING pour DES),
même réparties sur plusieurs Pôles. C'est cohérent avec la hiérarchie organisationnelle.

**Fichiers modifiés** :
- `org/permissions.py` — Logique `_is_branch_manager()` étendue

**Impact** : Comportement attendu sur le plan métier, politique d'accès plus cohérente

### 3. Optimisation N+1 queries

**Problème** : Le serializer `OrganizationalUnitSerializer` appelait `get_parent()`
pour chaque nœud lors d'une liste, causant une requête supplémentaire par ligne.

**Solution** : Pré-charge des parents en une seule requête, passage via le contexte
du serializer.

**Fichiers modifiés** :
- `org/views.py` — Override `get_serializer_context()`
- `org/serializers.py` — Utilisation du cache de contexte

**Impact** : Pour une liste de 50 unités, passe de ~50 queries à ~2 queries


Le document décrit le modèle de données et les règles métier, mais pas le
mécanisme d'authentification. Pour que le code soit exécutable, j'ai ajouté :

- **`org/authentication.py`** — authentification par JWT partagé avec le
  microservice Auth (`Authorization: Bearer <token>`, claim `sub` = UUID
  utilisateur, claim `roles` optionnelle). Ce microservice ne possédant pas
  de table utilisateurs, c'est le choix le plus cohérent avec l'architecture
  décrite (§4.9 : "Auth : validation du `service_id` des utilisateurs").
- **`org/management/commands/consume_events.py`** — commande pour lancer le
  consumer RabbitMQ (`org/events/consumer.py`) en process séparé du serveur
  web, comme il se doit.
- **`PyJWT`** et **`python-dotenv`** dans `requirements.txt`, nécessaires
  aux deux ajouts ci-dessus.

## Points laissés ouverts (à trancher)

1. **Rattachement DOS/DES à la racine Technology.** Aucune unité de l'arbre
   ne représente "toute la branche Opérationnel" ou "toute la branche
   Engineering" — un DOS supervise des DO répartis sur plusieurs Pôles. Le
   code rattache donc les responsabilités DOS/DES à l'unique unité racine
   (`Technology`), plutôt que d'ajouter un niveau d'unité virtuel ou de
   rendre `unit_id` nullable. C'est un choix de ma part (recommandé mais
   pas explicitement validé) — voir le rapport, §4.1, pour les alternatives
   écartées et leurs compromis.

---

## Points résolus

✅ **DOS/DES ont désormais le droit de gestion des services** (résolu dans la section
"Améliorations appliquées" ci-dessus). Un DOS peut créer/modifier les services
dans toutes les Directions OPERATIONNEL, un DES dans toutes les Directions
ENGINEERING. Cela reflète la hiérarchie organisationnelle et améliore la cohérence
de la politique d'accès.

✅ **Livraison des événements RabbitMQ est garantie** (via le pattern Outbox).
Plus de perte d'événements en cas d'indisponibilité du broker. Voir
[org/events/OUTBOX_PATTERN.md](org/events/OUTBOX_PATTERN.md) pour la documentation
complète.

✅ **N+1 queries sur les listes d'unités optimisé**. Les parents sont pré-chargés
en une seule requête au lieu de causer une requête par ligne.

