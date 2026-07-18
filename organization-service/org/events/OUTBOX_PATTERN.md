# Outbox Pattern — Garantie de livraison des événements

## Vue d'ensemble

Le pattern **Outbox** garantit que les événements sont toujours livrés à RabbitMQ, même en cas d'indisponibilité du service de message. Au lieu de publier directement sur RabbitMQ dans la requête HTTP (risque de perte), les événements sont d'abord persécurisés dans la base de données locale, puis un process dédié les envoie à RabbitMQ en arrière-plan.

## Architecture

```
Microservice Organisation
├── API Request (POST /api/services/)
│   └── save() → OutboxEvent.create() [transaction DB]
│       ✓ Garantie : événement persécurisé dans la DB
│       ✗ RabbitMQ n'est PAS interrogé ici
│
└── Consumer Outbox (processus dédié)
    └── process_outbox command
        └── OutboxEvent.objects.filter(is_published=False)
            └── _publish_to_rabbitmq()
                ├── Succès → mark_as_published()
                └── Erreur → retry avec backoff exponentiel
```

## Étapes de mise en place

### 1. Appliquer la migration

```bash
python manage.py migrate org
```

Cela crée la table `org_outboxevent` avec les colonnes :
- `id` : UUID unique
- `routing_key` : ex. "service.created"
- `payload` : données JSON
- `is_published` : booléen
- `created_at` : timestamp création
- `published_at` : timestamp publication (null avant succès)
- `attempt_count` : nombre de tentatives
- `last_error` : message d'erreur dernière tentative

### 2. Démarrer le consumer outbox

En production, lancer ce command dans un process dédié (systemd, supervisor, Docker, etc.) :

```bash
python manage.py process_outbox \
    --batch-size 10 \
    --poll-interval 5
```

**Options** :
- `--batch-size` : nombre d'événements traités par iteration (défaut: 10)
- `--poll-interval` : intervalle d'interrogation DB en secondes (défaut: 5)

**Exemple avec systemd** :
```ini
[Unit]
Description=Organisation Service - Outbox Consumer
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/organisation-service
ExecStart=/opt/organisation-service/venv/bin/python manage.py process_outbox
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 3. Vérifier le fonctionnement

Les événements enregistrés mais non publiés :
```bash
python manage.py shell
>>> from org.models import OutboxEvent
>>> OutboxEvent.objects.filter(is_published=False)
<QuerySet [<OutboxEvent: service.created (⏳ En attente) — 2026-07-17 14:30:45.123456+00:00>]>
```

Les événements publiés avec succès :
```bash
>>> OutboxEvent.objects.filter(is_published=True)
```

Les événements en erreur après plusieurs tentatives :
```bash
>>> OutboxEvent.objects.filter(attempt_count__gte=5)
```

## Configuration du retry

Le consumer utilise un **backoff exponentiel** configurable dans `process_outbox.py` :

```python
MAX_ATTEMPTS = 5              # Abandon après 5 tentatives
INITIAL_DELAY = 1             # 1 seconde au premier retry
MAX_DELAY = 60                # Plafonné à 60 secondes
```

**Délais** : 1s, 2s, 4s, 8s, 16s, ..., max 60s + jitter ±20%

## Logs et monitoring

### Logs du consumer
```
🚀 Démarrage du consumer outbox (batch=10, interval=5s)
📨 Traitement de 3 événement(s)...
✓ Événement 'service.created' publié avec succès (tentative 1)
⏳ Attente 2.1s avant nouvelle tentative...
✗ Événement 'responsibility.assigned' abandonné après 5 tentatives
```

### Requête de monitoring
```sql
SELECT 
  routing_key,
  COUNT(*) as total,
  SUM(CASE WHEN is_published THEN 1 ELSE 0 END) as published,
  MAX(attempt_count) as max_attempts,
  MIN(created_at) as oldest
FROM org_outboxevent
GROUP BY routing_key
ORDER BY created_at DESC;
```

## Migration depuis l'ancienne architecture

Si des événements ont été perdus avec l'ancienne implémentation synchrone, **aucune action n'est requise** — les événements futurs seront garantis avec l'outbox.

Pour rejouer des événements historiques, créer manuellement les `OutboxEvent` :
```python
OutboxEvent.objects.create(
    routing_key="service.created",
    payload={"id": "...", "name": "..."}
)
```

## Flux complet : création d'un service

### Avant (synchrone best-effort)
```
1. POST /api/services/
2. service.save()
3. publish_event() → RabbitMQ (synchrone)
   ├─ Succès : Event reçu
   └─ RabbitMQ down : Erreur loggée, Event PERDU ✗
```

### Après (outbox pattern)
```
1. POST /api/services/
2. service.save()
3. OutboxEvent.create(routing_key, payload) → DB (tx atomique) ✓
   └─ Retour 201 immédiatement
4. [process_outbox background]
   ├─ Récupère OutboxEvent.filter(is_published=False)
   ├─ publish_to_rabbitmq()
   ├─ Succès : mark_as_published() ✓
   └─ Erreur : retry avec backoff ⚠️
5. Rabitmq redevient dispo : Event livré automatiquement ✓
```

## Points importants

✅ **Atomicité** : OutboxEvent créé dans la même transaction que service.save()  
✅ **Pas de perte** : Événements persécurisés en DB avant tentative RabbitMQ  
✅ **Retry automatique** : Backoff exponentiel jusqu'à 5 tentatives  
✅ **Monitoring** : Requêtes SQL pour auditer état des events  
✅ **Haute disponibilité** : Consumer peut être redémarré sans perte d'état  

⚠️ **Délai de livraison** : Événements livrés avec latence (poll_interval), pas temps-réel  
⚠️ **Doublons possibles** : Consumer peut republier si crash après succès RabbitMQ — idempotence requise  

## Dépannage

### Events en attente depuis longtemps
```sql
SELECT * FROM org_outboxevent
WHERE is_published = FALSE
AND created_at < NOW() - INTERVAL '1 hour';
```

**Causes** :
- Consumer pas lancé
- RabbitMQ de manière prolongée
- Permission manquante sur l'exchange

### Events en erreur
```sql
SELECT routing_key, last_error, attempt_count
FROM org_outboxevent
WHERE attempt_count >= 5;
```

**Actions** :
- Vérifier les logs du consumer
- Retenter manuellement si RabbitMQ fixed :
  ```python
  event.attempt_count = 0
  event.last_error = None
  event.save()
  ```

## Voir aussi

- [process_outbox.py](../management/commands/process_outbox.py) — Implémentation
- [publisher.py](publisher.py) — Fonction publish_event()
- [models.py](../models.py) — Modèle OutboxEvent
