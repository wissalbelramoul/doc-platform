# Document Service - API Documentation

## Authentification

Tous les endpoints nécessitent une authentification. Utiliser un token Bearer :

```bash
curl -H "Authorization: Bearer {token}" http://localhost:8001/api/documents/
```

## Endpoints

### Documents

#### 1. Lister les documents

```http
GET /api/documents/
```

**Paramètres de requête :**
- `status` (draft, pending, validated, rejected) - Filtrer par statut
- `category` - Filtrer par catégorie
- `block_id` - Filtrer par bloc
- `service_id` - Filtrer par service
- `department_id` - Filtrer par département
- `search` - Recherche texte (title, description, keywords)
- `ordering` - Tri (created_at, updated_at, title)
- `page` - Numéro de page
- `page_size` - Nombre d'éléments par page

**Exemple :**
```bash
curl http://localhost:8001/api/documents/?status=pending&category=finance&search=facture
```

**Réponse :**
```json
{
  "count": 42,
  "next": "http://localhost:8001/api/documents/?page=2",
  "previous": null,
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "Facture Q1 2024",
      "category": "finance",
      "status": "pending",
      "owner_id": 1,
      "is_deleted": false,
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-16T14:22:00Z"
    }
  ]
}
```

---

#### 2. Créer un document

```http
POST /api/documents/
Content-Type: multipart/form-data
```

**Champs :**
- `title` (string, requis) - Titre du document
- `description` (string, optionnel) - Description
- `category` (string, requis) - Catégorie
- `keywords_list` (array, optionnel) - Liste de mots-clés
- `owner_id` (integer, requis) - ID du propriétaire
- `block_id` (integer, optionnel) - ID du bloc
- `service_id` (integer, optionnel) - ID du service
- `department_id` (integer, optionnel) - ID du département
- `file` (file, requis) - Fichier à uploader
- `version_comment` (string, optionnel) - Commentaire pour la version

**Exemple :**
```bash
curl -X POST \
  -H "Authorization: Bearer {token}" \
  -F "title=Facture Q1" \
  -F "category=finance" \
  -F "keywords_list[]=invoice" \
  -F "keywords_list[]=quarterly" \
  -F "owner_id=1" \
  -F "file=@invoice.pdf" \
  http://localhost:8001/api/documents/
```

**Réponse (201 Created) :**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Facture Q1",
  "description": null,
  "category": "finance",
  "keywords": "invoice,quarterly",
  "keywords_list": ["invoice", "quarterly"],
  "owner_id": 1,
  "block_id": null,
  "service_id": null,
  "department_id": null,
  "status": "pending",
  "current_version": {
    "id": "660f9511-f3ac-52e5-b827-557766551111",
    "version_number": 1,
    "file_path": "invoices/invoice_550e8400.pdf",
    "file_size": 245120,
    "mime_type": "application/pdf",
    "file_hash": "abc123def456",
    "author_id": 1,
    "comment": "",
    "created_at": "2024-01-17T09:15:00Z"
  },
  "versions": [
    {
      "id": "660f9511-f3ac-52e5-b827-557766551111",
      "version_number": 1,
      "file_path": "invoices/invoice_550e8400.pdf",
      "file_size": 245120,
      "mime_type": "application/pdf",
      "file_hash": "abc123def456",
      "author_id": 1,
      "comment": "",
      "created_at": "2024-01-17T09:15:00Z"
    }
  ],
  "is_deleted": false,
  "created_at": "2024-01-17T09:15:00Z",
  "updated_at": "2024-01-17T09:15:00Z"
}
```

---

#### 3. Obtenir les détails d'un document

```http
GET /api/documents/{id}/
```

**Exemple :**
```bash
curl -H "Authorization: Bearer {token}" \
  http://localhost:8001/api/documents/550e8400-e29b-41d4-a716-446655440000/
```

**Réponse (200 OK) :** Voir réponse POST ci-dessus

**Erreurs :**
- `404 Not Found` - Document non trouvé
- `401 Unauthorized` - Non authentifié

---

#### 4. Modifier un document

```http
PUT /api/documents/{id}/
Content-Type: multipart/form-data
```

**Champs (tous optionnels) :**
- `title` - Titre
- `description` - Description
- `category` - Catégorie
- `keywords_list` - Liste de mots-clés
- `file` - Nouveau fichier (crée automatiquement une nouvelle version)
- `version_comment` - Commentaire pour la version

**Exemple :**
```bash
curl -X PUT \
  -H "Authorization: Bearer {token}" \
  -F "title=Facture Q1 2024 (Révisée)" \
  -F "description=Facture trimestrielle révisée" \
  -F "file=@invoice_revised.pdf" \
  -F "version_comment=Correction des montants" \
  http://localhost:8001/api/documents/550e8400-e29b-41d4-a716-446655440000/
```

**Réponse (200 OK) :** Même format que GET détails

---

#### 5. Modification partielle d'un document

```http
PATCH /api/documents/{id}/
Content-Type: multipart/form-data
```

Identique à PUT mais ne nécessite que les champs à modifier.

---

#### 6. Supprimer un document (soft delete)

```http
DELETE /api/documents/{id}/
```

**Exemple :**
```bash
curl -X DELETE \
  -H "Authorization: Bearer {token}" \
  http://localhost:8001/api/documents/550e8400-e29b-41d4-a716-446655440000/
```

**Réponse (204 No Content)**

Le document n'est pas supprimé physiquement mais marqué comme supprimé.

---

#### 7. Restaurer un document supprimé

```http
POST /api/documents/{id}/restore/
```

**Exemple :**
```bash
curl -X POST \
  -H "Authorization: Bearer {token}" \
  http://localhost:8001/api/documents/550e8400-e29b-41d4-a716-446655440000/restore/
```

**Réponse (200 OK) :** Données du document restauré

---

### Versions

#### 8. Lister toutes les versions d'un document

```http
GET /api/documents/{id}/versions/
```

**Exemple :**
```bash
curl -H "Authorization: Bearer {token}" \
  http://localhost:8001/api/documents/550e8400-e29b-41d4-a716-446655440000/versions/
```

**Réponse (200 OK) :**
```json
[
  {
    "id": "660f9511-f3ac-52e5-b827-557766551111",
    "version_number": 1,
    "file_path": "invoices/invoice_550e8400.pdf",
    "file_size": 245120,
    "mime_type": "application/pdf",
    "file_hash": "abc123def456",
    "author_id": 1,
    "comment": "Version initiale",
    "created_at": "2024-01-17T09:15:00Z"
  },
  {
    "id": "771g0622-g4bd-63f6-c938-668877662222",
    "version_number": 2,
    "file_path": "invoices/invoice_550e8400_v2.pdf",
    "file_size": 251240,
    "mime_type": "application/pdf",
    "file_hash": "def789ghi012",
    "author_id": 1,
    "comment": "Correction des montants",
    "created_at": "2024-01-17T14:22:00Z"
  }
]
```

---

#### 9. Restaurer une version précédente

```http
POST /api/documents/{id}/restore_version/
Content-Type: application/json
```

**Corps (JSON) :**
```json
{
  "version_id": "660f9511-f3ac-52e5-b827-557766551111"
}
```

**Exemple :**
```bash
curl -X POST \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{"version_id": "660f9511-f3ac-52e5-b827-557766551111"}' \
  http://localhost:8001/api/documents/550e8400-e29b-41d4-a716-446655440000/restore_version/
```

**Réponse (200 OK) :**
```json
{
  "id": "882h1733-h5ce-74g7-d049-779988773333",
  "version_number": 3,
  "file_path": "invoices/invoice_550e8400.pdf",
  "file_size": 245120,
  "mime_type": "application/pdf",
  "file_hash": "abc123def456",
  "author_id": 1,
  "comment": "Restored from version 1",
  "created_at": "2024-01-17T15:30:00Z"
}
```

---

#### 10. Lister les versions (global)

```http
GET /api/versions/
```

Paramètres :
- `document` - Filtrer par ID de document
- `page` - Numéro de page

**Exemple :**
```bash
curl -H "Authorization: Bearer {token}" \
  http://localhost:8001/api/versions/?document=550e8400-e29b-41d4-a716-446655440000
```

---

### Téléchargement & Historique

#### 11. Télécharger la version courante

```http
GET /api/documents/{id}/download/
```

**Exemple :**
```bash
curl -H "Authorization: Bearer {token}" \
  http://localhost:8001/api/documents/550e8400-e29b-41d4-a716-446655440000/download/
```

**Réponse (200 OK) :**
```json
{
  "download_url": "https://minio.example.com/documents/invoice_550e8400.pdf?X-Amz-Algorithm=AWS4-HMAC-SHA256&...",
  "filename": "invoice_550e8400.pdf",
  "file_size": 245120,
  "expires_in": 900
}
```

La `download_url` expire après 900 secondes (15 minutes).

---

#### 12. Obtenir l'historique d'un document

```http
GET /api/documents/{id}/history/
```

**Paramètres :**
- `page` - Numéro de page
- `page_size` - Nombre d'éléments par page (défaut: 20)

**Exemple :**
```bash
curl -H "Authorization: Bearer {token}" \
  http://localhost:8001/api/documents/550e8400-e29b-41d4-a716-446655440000/history/?page_size=10
```

**Réponse (200 OK) :**
```json
[
  {
    "id": "993i2844-i6df-85h8-e150-880099884444",
    "document": "550e8400-e29b-41d4-a716-446655440000",
    "user_id": 1,
    "action": "upload",
    "details": {
      "filename": "invoice.pdf"
    },
    "created_at": "2024-01-17T09:15:00Z"
  },
  {
    "id": "aa4j3955-j7eg-96i9-f261-991100995555",
    "document": "550e8400-e29b-41d4-a716-446655440000",
    "user_id": 1,
    "action": "modification",
    "details": {
      "fields": ["title", "description"]
    },
    "created_at": "2024-01-17T10:20:00Z"
  },
  {
    "id": "bb5k4066-k8fh-a7j0-g372-aa2211aa6666",
    "document": "550e8400-e29b-41d4-a716-446655440000",
    "user_id": 2,
    "action": "download",
    "details": {
      "version": 1
    },
    "created_at": "2024-01-17T14:45:00Z"
  }
]
```

**Actions disponibles :**
- `upload` - Création d'un document
- `modification` - Modification du fichier ou des métadonnées
- `deletion` - Suppression (soft delete)
- `download` - Téléchargement
- `view` - Consultation
- `validation` - Approbation
- `rejection` - Rejet
- `restore` - Restauration

---

## Erreurs courantes

### 400 Bad Request
```json
{
  "title": ["This field is required."],
  "category": ["This field is required."],
  "file": ["Extension .exe non autorisée. Extensions acceptées: pdf, doc, ..."]
}
```

### 401 Unauthorized
```json
{
  "detail": "Authentication credentials were not provided."
}
```

### 404 Not Found
```json
{
  "detail": "Not found."
}
```

### 413 Payload Too Large
```json
{
  "file": ["File too large. Max 20 MB"]
}
```

---

## Événements publiés (RabbitMQ)

Le service publie les événements suivants sur l'exchange `documents` :

```
document.created              → DocumentCreated
document.modified             → DocumentModified
document.deleted              → DocumentDeleted
document.restored             → DocumentRestored
document.version_restored     → VersionRestored
document.downloaded           → Downloaded
document.validated            → Validated (reçu d'autres services)
document.rejected             → Rejected (reçu d'autres services)
document.permanently_deleted  → PermanentlyDeleted
```

**Format d'un événement :**
```json
{
  "event_type": "document.created",
  "timestamp": "2024-01-17T09:15:00.123456Z",
  "payload": {
    "document_id": "550e8400-e29b-41d4-a716-446655440000",
    "title": "Facture Q1",
    "owner_id": 1,
    "status": "pending",
    "timestamp": "2024-01-17T09:15:00.123456Z"
  }
}
```

---

## Limitations de taille et extensions

**Taille maximale :** 20 Mo

**Extensions autorisées :**
- Documents: pdf, doc, docx, xls, xlsx, ppt, pptx
- Code: py, c, cpp, h, java, js, ts, html, css, sql, sh
- Texte: txt, md, csv, json, xml, yaml, yml
- Images: png, jpg, jpeg, gif, svg

**Types MIME valides :**
- text/* (pour code et texte)
- application/json, application/xml, application/pdf
- application/msword, application/vnd.ms-excel
- application/vnd.openxmlformats-officedocument.*
- image/* (pour images)

---

## Statuts de document

- `draft` - Brouillon (optionnel, non validé)
- `pending` - En attente de validation
- `validated` - Validé et approuvé
- `rejected` - Rejeté avec raison

---

## Rate Limiting

Aucune limite de taux (rate limiting) n'est actuellement appliquée.
En production, ajouter rate limiting par user/IP.

---

## Pagination

Par défaut, 20 documents par page.

```bash
curl -H "Authorization: Bearer {token}" \
  "http://localhost:8001/api/documents/?page=2&page_size=50"
```

---

## Support

Pour des questions ou problèmes, consulter le README.md du service.
