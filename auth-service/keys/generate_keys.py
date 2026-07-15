from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

# Génération de la clé privée RSA (2048 bits, équivalent à openssl genrsa)
private_key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
)

# Écriture de la clé privée au format PEM
with open("private.pem", "wb") as f:
    f.write(private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ))

# Dérivation et écriture de la clé publique correspondante
public_key = private_key.public_key()
with open("public.pem", "wb") as f:
    f.write(public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ))

print("Clés générées avec succès : private.pem et public.pem")