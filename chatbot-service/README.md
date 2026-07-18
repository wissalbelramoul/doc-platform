# Chatbot Service

Service de chatbot RAG qui indexe uniquement des documents validés envoyés par le Document Service via RabbitMQ.

## Structure

- `app/main.py` : point d'entrée FastAPI
- `app/api/chat.py` : endpoint `/chat`
- `app/events/consumer.py` : consommateur RabbitMQ `document.validated`
- `app/rag/` : extraction, chunking, embeddings, retrieval
- `app/vectorstore/faiss_store.py` : stockage FAISS

## Principes

- Aucun accès direct aux fichiers du service
- Téléchargement via URL fournie par Document Service
- Extraction du texte, chunking, embeddings, stockage vectoriel
- Recherche limitée aux documents autorisés par permissions
