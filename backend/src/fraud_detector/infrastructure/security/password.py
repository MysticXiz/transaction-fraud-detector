from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

# Usados apenas para bloquear e migrar contas criadas pelo bootstrap antigo.
LEGACY_ADMIN_EMAIL = "admin@admin.com"
LEGACY_ADMIN_PASSWORD = "admin123"


# Somente o hash é persistido; a senha original nunca deve chegar ao modelo ou ao banco.
def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)
