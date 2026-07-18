# smart-doc-platform

Plateforme de documentation intelligente avec plusieurs services microservices.

## Services disponibles

- organization-service : gestion des départements, services et blocs
- document-service : documents, versions, historique et téléchargement
- validation-service : workflow de validation et refus
- search-service : recherche et indexation de documents
- notification-service : notifications simples via API
- chatbot-service : pipeline RAG minimal basé sur des documents validés

## Structure

- frontend/
- api-gateway/
- auth-service/
- user-service/
- organization-service/
- document-service/
- validation-service/
- search-service/
- notification-service/
- chatbot-service/
- stats-service/

## Lancer

```bash
docker compose up --build -d
```

## Commandes utiles

```bash
docker compose ps
docker compose logs -f <service>
docker compose down
```

## Notes Docker

- Le fichier Compose racine définit les services d’infrastructure tels que PostgreSQL, RabbitMQ, Redis et MinIO.
- Chaque service applicatif possède son propre Dockerfile et peut être construit indépendamment.
- Le gateway est exposé sur le port 8080 et le frontend sur le port 3000.

## Fonctionnalités clés

- gestion de l’organisation
- workflow documentaire
- validation des documents
- recherche documentaire
- notifications
- chatbot RAG basé sur des documents validés
