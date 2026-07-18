"""
Utility functions for Document Service
"""
import json
import logging
from datetime import datetime, timedelta
from django.conf import settings
import pika

logger = logging.getLogger(__name__)


def publish_event(event_type, payload):
    """
    Publish event to RabbitMQ for other services to consume
    
    Events:
    - document.created
    - document.modified
    - document.deleted
    - document.restored
    - document.version_restored
    - document.downloaded
    - document.validated
    - document.rejected
    """
    try:
        connection_params = pika.ConnectionParameters(
            host=settings.RABBITMQ_HOST,
            port=settings.RABBITMQ_PORT,
            credentials=pika.PlainCredentials(
                settings.RABBITMQ_USER,
                settings.RABBITMQ_PASSWORD
            )
        )
        
        connection = pika.BlockingConnection(connection_params)
        channel = connection.channel()
        
        # Declare exchange
        channel.exchange_declare(
            exchange='documents',
            exchange_type='topic',
            durable=True
        )
        
        # Publish message
        message = {
            'event_type': event_type,
            'timestamp': datetime.utcnow().isoformat(),
            'payload': payload
        }
        
        channel.basic_publish(
            exchange='documents',
            routing_key=event_type,
            body=json.dumps(message),
            properties=pika.BasicProperties(
                content_type='application/json',
                delivery_mode=2  # Persistent
            )
        )
        
        connection.close()
        logger.info(f"Event published: {event_type}")
        
    except Exception as e:
        logger.error(f"Failed to publish event {event_type}: {str(e)}")
        # In production, might want to retry or use a queue


def generate_signed_url(file_path, expires_in=900):
    """
    Generate a signed URL for file download
    
    Args:
        file_path: Path to file in storage
        expires_in: Expiration time in seconds (default 15 minutes)
    
    Returns:
        Signed URL string
    """
    storage_type = getattr(settings, 'STORAGE_TYPE', 'local')
    
    if storage_type == 's3':
        return _generate_s3_signed_url(file_path, expires_in)
    elif storage_type == 'minio':
        return _generate_minio_signed_url(file_path, expires_in)
    else:
        return _generate_local_signed_url(file_path, expires_in)


def _generate_s3_signed_url(file_path, expires_in):
    """Generate AWS S3 signed URL"""
    try:
        import boto3
        
        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME
        )
        
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
                'Key': file_path
            },
            ExpiresIn=expires_in
        )
        
        return url
    except Exception as e:
        logger.error(f"Failed to generate S3 signed URL: {str(e)}")
        return None


def _generate_minio_signed_url(file_path, expires_in):
    """Generate MinIO signed URL"""
    try:
        from minio import Minio
        
        minio_client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_USE_SSL
        )
        
        url = minio_client.get_presigned_download_link(
            settings.MINIO_BUCKET,
            file_path,
            expires=timedelta(seconds=expires_in)
        )
        
        return url
    except Exception as e:
        logger.error(f"Failed to generate MinIO signed URL: {str(e)}")
        return None


def _generate_local_signed_url(file_path, expires_in):
    """Generate local file URL"""
    # In local storage, generate a simple URL
    # In production with local storage, would use a view to serve files securely
    return f"/api/documents/download/{file_path}"


def consume_events():
    """
    Consumer for events from other services
    This would be run in a separate worker/celery task
    """
    try:
        connection_params = pika.ConnectionParameters(
            host=settings.RABBITMQ_HOST,
            port=settings.RABBITMQ_PORT,
            credentials=pika.PlainCredentials(
                settings.RABBITMQ_USER,
                settings.RABBITMQ_PASSWORD
            )
        )
        
        connection = pika.BlockingConnection(connection_params)
        channel = connection.channel()
        
        # Subscribe to validation and rejection events
        channel.exchange_declare(
            exchange='documents',
            exchange_type='topic',
            durable=True
        )
        
        queue_name = channel.queue_declare(queue='', exclusive=True).method.queue
        
        channel.queue_bind(
            exchange='documents',
            queue=queue_name,
            routing_key='validation.*'
        )
        
        channel.queue_bind(
            exchange='documents',
            queue=queue_name,
            routing_key='document.status.*'
        )
        
        def callback(ch, method, properties, body):
            try:
                message = json.loads(body)
                logger.info(f"Received event: {message}")
                # Process event and update document status
            except Exception as e:
                logger.error(f"Error processing event: {str(e)}")
        
        channel.basic_consume(queue=queue_name, on_message_callback=callback)
        
        logger.info("Starting event consumer...")
        channel.start_consuming()
        
    except Exception as e:
        logger.error(f"Error in event consumer: {str(e)}")
