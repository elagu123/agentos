"""
Data Encryption Manager for AgentOS
Advanced encryption for sensitive data with field-level encryption and key management
"""

from cryptography.fernet import Fernet, MultiFernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend
import base64
import os
import json
import hashlib
import hmac
import secrets
from typing import Any, Dict, Optional, Tuple, List, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class EncryptionAlgorithm(Enum):
    FERNET = "fernet"
    MULTI_FERNET = "multi_fernet"
    RSA = "rsa"
    HYBRID = "hybrid"

class KeyDerivationFunction(Enum):
    PBKDF2 = "pbkdf2"
    SCRYPT = "scrypt"

@dataclass
class EncryptionKey:
    key_id: str
    algorithm: EncryptionAlgorithm
    key_data: bytes
    created_at: datetime
    expires_at: Optional[datetime] = None
    is_active: bool = True
    usage_count: int = 0
    max_usage: Optional[int] = None

@dataclass
class EncryptedData:
    data: str  # Base64 encoded encrypted data
    key_id: str
    algorithm: EncryptionAlgorithm
    iv: Optional[str] = None  # Initialization vector if applicable
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

class EncryptionManager:
    def __init__(self, master_key: Optional[str] = None, key_rotation_days: int = 30):
        """
        Initialize encryption manager with optional master key

        Args:
            master_key: Base64 encoded master key or None to generate
            key_rotation_days: Number of days after which keys should be rotated
        """

        self.key_rotation_days = key_rotation_days
        self.backend = default_backend()

        # Master key for key encryption
        if master_key:
            self.master_key = base64.urlsafe_b64decode(master_key.encode())
        else:
            self.master_key = Fernet.generate_key()

        self.master_fernet = Fernet(self.master_key)

        # Key storage (in production, use secure key management service)
        self.keys: Dict[str, EncryptionKey] = {}
        self.field_keys: Dict[str, str] = {}  # field_name -> key_id mapping

        # Initialize default keys
        self._initialize_default_keys()

        # Encryption statistics
        self.stats = {
            "encryptions": 0,
            "decryptions": 0,
            "key_generations": 0,
            "key_rotations": 0,
            "errors": 0
        }

    def _initialize_default_keys(self):
        """Initialize default encryption keys"""

        # Create default Fernet key
        default_key = self._generate_encryption_key(
            key_id="default_fernet",
            algorithm=EncryptionAlgorithm.FERNET
        )

        # Create multi-key setup for enhanced security
        multi_keys = []
        for i in range(3):
            key = self._generate_encryption_key(
                key_id=f"multi_key_{i}",
                algorithm=EncryptionAlgorithm.FERNET
            )
            multi_keys.append(key.key_data)

        # Store multi-fernet key
        multi_fernet_key = EncryptionKey(
            key_id="default_multi_fernet",
            algorithm=EncryptionAlgorithm.MULTI_FERNET,
            key_data=b"|".join(multi_keys),  # Store as concatenated keys
            created_at=datetime.utcnow()
        )
        self.keys[multi_fernet_key.key_id] = multi_fernet_key

        # Generate RSA key pair for asymmetric encryption
        self._generate_rsa_key_pair("default_rsa")

    def _generate_encryption_key(
        self,
        key_id: str,
        algorithm: EncryptionAlgorithm,
        expires_days: Optional[int] = None
    ) -> EncryptionKey:
        """Generate new encryption key"""

        if algorithm == EncryptionAlgorithm.FERNET:
            key_data = Fernet.generate_key()
        else:
            raise ValueError(f"Unsupported algorithm for key generation: {algorithm}")

        expires_at = None
        if expires_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_days)

        key = EncryptionKey(
            key_id=key_id,
            algorithm=algorithm,
            key_data=key_data,
            created_at=datetime.utcnow(),
            expires_at=expires_at
        )

        self.keys[key_id] = key
        self.stats["key_generations"] += 1

        logger.info(f"Generated new {algorithm.value} key: {key_id}")

        return key

    def _generate_rsa_key_pair(self, key_id: str) -> Tuple[EncryptionKey, EncryptionKey]:
        """Generate RSA key pair for asymmetric encryption"""

        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=self.backend
        )

        # Get public key
        public_key = private_key.public_key()

        # Serialize keys
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )

        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

        # Create key objects
        private_key_obj = EncryptionKey(
            key_id=f"{key_id}_private",
            algorithm=EncryptionAlgorithm.RSA,
            key_data=private_pem,
            created_at=datetime.utcnow()
        )

        public_key_obj = EncryptionKey(
            key_id=f"{key_id}_public",
            algorithm=EncryptionAlgorithm.RSA,
            key_data=public_pem,
            created_at=datetime.utcnow()
        )

        self.keys[private_key_obj.key_id] = private_key_obj
        self.keys[public_key_obj.key_id] = public_key_obj

        self.stats["key_generations"] += 2

        logger.info(f"Generated RSA key pair: {key_id}")

        return private_key_obj, public_key_obj

    def get_master_key_string(self) -> str:
        """Get base64 encoded master key for storage"""
        return base64.urlsafe_b64encode(self.master_key).decode()

    def derive_key_from_password(
        self,
        password: str,
        salt: Optional[bytes] = None,
        kdf: KeyDerivationFunction = KeyDerivationFunction.PBKDF2
    ) -> Tuple[bytes, bytes]:
        """Derive encryption key from password"""

        if salt is None:
            salt = os.urandom(16)

        if kdf == KeyDerivationFunction.PBKDF2:
            kdf_instance = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
                backend=self.backend
            )
        elif kdf == KeyDerivationFunction.SCRYPT:
            kdf_instance = Scrypt(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                n=2**14,
                r=8,
                p=1,
                backend=self.backend
            )
        else:
            raise ValueError(f"Unsupported KDF: {kdf}")

        key = kdf_instance.derive(password.encode())
        return base64.urlsafe_b64encode(key), salt

    # === Basic Encryption/Decryption ===

    def encrypt(
        self,
        data: str,
        key_id: str = "default_fernet",
        algorithm: Optional[EncryptionAlgorithm] = None
    ) -> EncryptedData:
        """Encrypt string data"""

        if not data:
            return EncryptedData(
                data="",
                key_id=key_id,
                algorithm=algorithm or EncryptionAlgorithm.FERNET
            )

        key = self.keys.get(key_id)
        if not key or not key.is_active:
            raise ValueError(f"Key not found or inactive: {key_id}")

        # Check key expiration
        if key.expires_at and datetime.utcnow() > key.expires_at:
            raise ValueError(f"Key expired: {key_id}")

        # Check usage limits
        if key.max_usage and key.usage_count >= key.max_usage:
            raise ValueError(f"Key usage limit exceeded: {key_id}")

        try:
            if key.algorithm == EncryptionAlgorithm.FERNET:
                fernet = Fernet(key.key_data)
                encrypted = fernet.encrypt(data.encode())

            elif key.algorithm == EncryptionAlgorithm.MULTI_FERNET:
                # Split the concatenated keys
                key_parts = key.key_data.split(b"|")
                fernets = [Fernet(k) for k in key_parts]
                multi_fernet = MultiFernet(fernets)
                encrypted = multi_fernet.encrypt(data.encode())

            elif key.algorithm == EncryptionAlgorithm.RSA:
                # For RSA, use hybrid encryption for large data
                return self._encrypt_hybrid(data, key_id)

            else:
                raise ValueError(f"Unsupported algorithm: {key.algorithm}")

            # Update usage count
            key.usage_count += 1
            self.stats["encryptions"] += 1

            return EncryptedData(
                data=base64.urlsafe_b64encode(encrypted).decode(),
                key_id=key_id,
                algorithm=key.algorithm,
                timestamp=datetime.utcnow()
            )

        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Encryption failed for key {key_id}: {e}")
            raise

    def decrypt(self, encrypted_data: EncryptedData) -> str:
        """Decrypt data"""

        if not encrypted_data.data:
            return ""

        key = self.keys.get(encrypted_data.key_id)
        if not key:
            raise ValueError(f"Key not found: {encrypted_data.key_id}")

        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.data)

            if key.algorithm == EncryptionAlgorithm.FERNET:
                fernet = Fernet(key.key_data)
                decrypted = fernet.decrypt(encrypted_bytes)

            elif key.algorithm == EncryptionAlgorithm.MULTI_FERNET:
                key_parts = key.key_data.split(b"|")
                fernets = [Fernet(k) for k in key_parts]
                multi_fernet = MultiFernet(fernets)
                decrypted = multi_fernet.decrypt(encrypted_bytes)

            elif key.algorithm == EncryptionAlgorithm.RSA:
                return self._decrypt_hybrid(encrypted_data)

            else:
                raise ValueError(f"Unsupported algorithm: {key.algorithm}")

            self.stats["decryptions"] += 1

            return decrypted.decode()

        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Decryption failed for key {encrypted_data.key_id}: {e}")
            raise

    def _encrypt_hybrid(self, data: str, key_id: str) -> EncryptedData:
        """Hybrid encryption using RSA + Fernet for large data"""

        # Generate temporary Fernet key
        temp_key = Fernet.generate_key()
        fernet = Fernet(temp_key)

        # Encrypt data with Fernet
        encrypted_data = fernet.encrypt(data.encode())

        # Encrypt Fernet key with RSA public key
        public_key_obj = self.keys.get(f"{key_id.replace('_private', '')}_public")
        if not public_key_obj:
            raise ValueError(f"Public key not found for: {key_id}")

        public_key = serialization.load_pem_public_key(
            public_key_obj.key_data,
            backend=self.backend
        )

        encrypted_key = public_key.encrypt(
            temp_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )

        # Combine encrypted key and data
        combined = encrypted_key + b"|" + encrypted_data

        return EncryptedData(
            data=base64.urlsafe_b64encode(combined).decode(),
            key_id=key_id,
            algorithm=EncryptionAlgorithm.HYBRID,
            timestamp=datetime.utcnow()
        )

    def _decrypt_hybrid(self, encrypted_data: EncryptedData) -> str:
        """Decrypt hybrid encrypted data"""

        combined = base64.urlsafe_b64decode(encrypted_data.data)

        # Split encrypted key and data
        parts = combined.split(b"|", 1)
        if len(parts) != 2:
            raise ValueError("Invalid hybrid encrypted data format")

        encrypted_key, encrypted_content = parts

        # Decrypt Fernet key with RSA private key
        private_key_obj = self.keys.get(encrypted_data.key_id)
        if not private_key_obj:
            raise ValueError(f"Private key not found: {encrypted_data.key_id}")

        private_key = serialization.load_pem_private_key(
            private_key_obj.key_data,
            password=None,
            backend=self.backend
        )

        temp_key = private_key.decrypt(
            encrypted_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )

        # Decrypt data with Fernet
        fernet = Fernet(temp_key)
        decrypted = fernet.decrypt(encrypted_content)

        return decrypted.decode()

    # === Field-Level Encryption ===

    def encrypt_field(
        self,
        field_name: str,
        value: Any,
        user_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> EncryptedData:
        """Encrypt specific field with user-specific key"""

        # Generate field-specific key ID
        key_id = self._get_field_key_id(field_name, user_id)

        # Generate key if it doesn't exist
        if key_id not in self.keys:
            self._generate_field_key(field_name, user_id)

        # Convert value to string
        if not isinstance(value, str):
            value = json.dumps(value, default=str)

        encrypted = self.encrypt(value, key_id)

        # Add field-specific metadata
        encrypted.metadata.update({
            "field_name": field_name,
            "user_id": user_id,
            "context": context or {}
        })

        return encrypted

    def decrypt_field(
        self,
        field_name: str,
        encrypted_data: EncryptedData,
        user_id: str
    ) -> Any:
        """Decrypt field-level encrypted data"""

        # Verify field ownership
        if encrypted_data.metadata.get("user_id") != user_id:
            raise ValueError("Field access denied: user mismatch")

        if encrypted_data.metadata.get("field_name") != field_name:
            raise ValueError("Field access denied: field name mismatch")

        decrypted = self.decrypt(encrypted_data)

        # Try to parse as JSON
        try:
            return json.loads(decrypted)
        except (json.JSONDecodeError, TypeError):
            return decrypted

    def _get_field_key_id(self, field_name: str, user_id: str) -> str:
        """Get field-specific key ID"""
        return f"field_{field_name}_{user_id}"

    def _generate_field_key(self, field_name: str, user_id: str) -> EncryptionKey:
        """Generate field-specific encryption key"""

        key_id = self._get_field_key_id(field_name, user_id)

        # Use KDF to derive key from master key + field info
        salt_data = f"{field_name}:{user_id}".encode()
        salt = hashlib.sha256(salt_data).digest()[:16]

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=self.backend
        )

        derived_key = kdf.derive(self.master_key)
        fernet_key = base64.urlsafe_b64encode(derived_key)

        key = EncryptionKey(
            key_id=key_id,
            algorithm=EncryptionAlgorithm.FERNET,
            key_data=fernet_key,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=self.key_rotation_days)
        )

        self.keys[key_id] = key
        self.field_keys[f"{field_name}:{user_id}"] = key_id

        return key

    # === Dictionary Encryption ===

    def encrypt_dict(
        self,
        data: Dict[str, Any],
        key_id: str = "default_fernet",
        selective_fields: Optional[List[str]] = None
    ) -> EncryptedData:
        """Encrypt dictionary as JSON with optional selective field encryption"""

        if selective_fields:
            # Encrypt only specific fields
            encrypted_dict = data.copy()

            for field in selective_fields:
                if field in encrypted_dict:
                    field_data = self.encrypt_field(
                        field,
                        encrypted_dict[field],
                        "system"  # Use system as default user for dict encryption
                    )
                    encrypted_dict[field] = {
                        "_encrypted": True,
                        "_data": field_data.data,
                        "_key_id": field_data.key_id,
                        "_algorithm": field_data.algorithm.value
                    }

            json_str = json.dumps(encrypted_dict, default=str)
        else:
            # Encrypt entire dictionary
            json_str = json.dumps(data, default=str)

        return self.encrypt(json_str, key_id)

    def decrypt_dict(self, encrypted_data: EncryptedData) -> Dict[str, Any]:
        """Decrypt JSON to dictionary with selective field decryption"""

        decrypted = self.decrypt(encrypted_data)

        if not decrypted:
            return {}

        data = json.loads(decrypted)

        # Check for selectively encrypted fields
        for key, value in data.items():
            if isinstance(value, dict) and value.get("_encrypted"):
                field_encrypted_data = EncryptedData(
                    data=value["_data"],
                    key_id=value["_key_id"],
                    algorithm=EncryptionAlgorithm(value["_algorithm"])
                )
                data[key] = self.decrypt_field(key, field_encrypted_data, "system")

        return data

    # === File Encryption ===

    def encrypt_file(
        self,
        file_path: str,
        output_path: Optional[str] = None,
        key_id: str = "default_fernet"
    ) -> str:
        """Encrypt file"""

        if output_path is None:
            output_path = f"{file_path}.encrypted"

        key = self.keys.get(key_id)
        if not key or not key.is_active:
            raise ValueError(f"Key not found or inactive: {key_id}")

        fernet = Fernet(key.key_data)

        with open(file_path, 'rb') as f:
            file_data = f.read()

        # Add metadata header
        metadata = {
            "original_filename": os.path.basename(file_path),
            "encrypted_at": datetime.utcnow().isoformat(),
            "key_id": key_id,
            "algorithm": key.algorithm.value
        }

        metadata_json = json.dumps(metadata).encode()
        metadata_length = len(metadata_json).to_bytes(4, byteorder='big')

        # Encrypt file data
        encrypted_data = fernet.encrypt(file_data)

        # Write metadata + encrypted data
        with open(output_path, 'wb') as f:
            f.write(metadata_length)
            f.write(metadata_json)
            f.write(encrypted_data)

        key.usage_count += 1
        self.stats["encryptions"] += 1

        logger.info(f"Encrypted file: {file_path} -> {output_path}")

        return output_path

    def decrypt_file(
        self,
        encrypted_path: str,
        output_path: Optional[str] = None
    ) -> str:
        """Decrypt file"""

        with open(encrypted_path, 'rb') as f:
            # Read metadata length
            metadata_length_bytes = f.read(4)
            metadata_length = int.from_bytes(metadata_length_bytes, byteorder='big')

            # Read metadata
            metadata_json = f.read(metadata_length)
            metadata = json.loads(metadata_json.decode())

            # Read encrypted data
            encrypted_data = f.read()

        # Get key
        key_id = metadata["key_id"]
        key = self.keys.get(key_id)
        if not key:
            raise ValueError(f"Key not found: {key_id}")

        fernet = Fernet(key.key_data)
        decrypted_data = fernet.decrypt(encrypted_data)

        if output_path is None:
            output_path = metadata.get("original_filename", encrypted_path.replace('.encrypted', ''))

        with open(output_path, 'wb') as f:
            f.write(decrypted_data)

        self.stats["decryptions"] += 1

        logger.info(f"Decrypted file: {encrypted_path} -> {output_path}")

        return output_path

    # === Key Management ===

    def rotate_key(self, key_id: str) -> str:
        """Rotate encryption key"""

        old_key = self.keys.get(key_id)
        if not old_key:
            raise ValueError(f"Key not found: {key_id}")

        # Generate new key with same algorithm
        new_key_id = f"{key_id}_v{int(time.time())}"
        new_key = self._generate_encryption_key(
            new_key_id,
            old_key.algorithm,
            self.key_rotation_days
        )

        # Mark old key as inactive
        old_key.is_active = False

        self.stats["key_rotations"] += 1

        logger.info(f"Rotated key: {key_id} -> {new_key_id}")

        return new_key_id

    def get_key_info(self, key_id: str) -> Optional[Dict[str, Any]]:
        """Get key information"""

        key = self.keys.get(key_id)
        if not key:
            return None

        return {
            "key_id": key.key_id,
            "algorithm": key.algorithm.value,
            "created_at": key.created_at.isoformat(),
            "expires_at": key.expires_at.isoformat() if key.expires_at else None,
            "is_active": key.is_active,
            "usage_count": key.usage_count,
            "max_usage": key.max_usage
        }

    def list_keys(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        """List all keys"""

        keys = []
        for key in self.keys.values():
            if not include_inactive and not key.is_active:
                continue

            key_info = self.get_key_info(key.key_id)
            if key_info:
                keys.append(key_info)

        return keys

    def cleanup_expired_keys(self) -> int:
        """Remove expired keys"""

        now = datetime.utcnow()
        expired_keys = []

        for key_id, key in self.keys.items():
            if key.expires_at and now > key.expires_at and not key.is_active:
                expired_keys.append(key_id)

        for key_id in expired_keys:
            del self.keys[key_id]

        logger.info(f"Cleaned up {len(expired_keys)} expired keys")

        return len(expired_keys)

    # === Utility Methods ===

    def generate_salt(self, length: int = 16) -> bytes:
        """Generate random salt"""
        return os.urandom(length)

    def secure_compare(self, a: str, b: str) -> bool:
        """Secure string comparison to prevent timing attacks"""
        return hmac.compare_digest(a.encode(), b.encode())

    def get_encryption_stats(self) -> Dict[str, Any]:
        """Get encryption statistics"""

        active_keys = sum(1 for key in self.keys.values() if key.is_active)

        return {
            **self.stats,
            "total_keys": len(self.keys),
            "active_keys": active_keys,
            "field_keys": len(self.field_keys),
            "key_rotation_days": self.key_rotation_days
        }

    def create_encrypted_backup(self, data: Dict[str, Any], password: str) -> str:
        """Create password-encrypted backup of sensitive data"""

        # Derive key from password
        salt = self.generate_salt()
        key, _ = self.derive_key_from_password(password, salt, KeyDerivationFunction.SCRYPT)

        # Create temporary Fernet key
        temp_fernet = Fernet(key)

        # Encrypt data
        json_data = json.dumps(data, default=str)
        encrypted_data = temp_fernet.encrypt(json_data.encode())

        # Combine salt and encrypted data
        backup_data = {
            "salt": base64.b64encode(salt).decode(),
            "data": base64.b64encode(encrypted_data).decode(),
            "created_at": datetime.utcnow().isoformat(),
            "kdf": "scrypt"
        }

        return json.dumps(backup_data)

    def restore_from_backup(self, backup_str: str, password: str) -> Dict[str, Any]:
        """Restore data from password-encrypted backup"""

        backup_data = json.loads(backup_str)

        # Extract components
        salt = base64.b64decode(backup_data["salt"])
        encrypted_data = base64.b64decode(backup_data["data"])

        # Derive key from password
        key, _ = self.derive_key_from_password(password, salt, KeyDerivationFunction.SCRYPT)

        # Decrypt data
        fernet = Fernet(key)
        decrypted_json = fernet.decrypt(encrypted_data).decode()

        return json.loads(decrypted_json)

# Global instance
encryption_manager = EncryptionManager(
    master_key=os.getenv("ENCRYPTION_MASTER_KEY")
)

# Utility functions for easy encryption/decryption
def encrypt_sensitive_data(data: str, user_id: str = "system") -> str:
    """Quick encrypt for sensitive data"""
    encrypted = encryption_manager.encrypt(data)
    return json.dumps({
        "data": encrypted.data,
        "key_id": encrypted.key_id,
        "algorithm": encrypted.algorithm.value,
        "timestamp": encrypted.timestamp.isoformat()
    })

def decrypt_sensitive_data(encrypted_str: str) -> str:
    """Quick decrypt for sensitive data"""
    data = json.loads(encrypted_str)
    encrypted_data = EncryptedData(
        data=data["data"],
        key_id=data["key_id"],
        algorithm=EncryptionAlgorithm(data["algorithm"]),
        timestamp=datetime.fromisoformat(data["timestamp"])
    )
    return encryption_manager.decrypt(encrypted_data)

def encrypt_user_field(field_name: str, value: Any, user_id: str) -> str:
    """Encrypt user-specific field"""
    encrypted = encryption_manager.encrypt_field(field_name, value, user_id)
    return json.dumps({
        "data": encrypted.data,
        "key_id": encrypted.key_id,
        "algorithm": encrypted.algorithm.value,
        "metadata": encrypted.metadata,
        "timestamp": encrypted.timestamp.isoformat()
    })

def decrypt_user_field(field_name: str, encrypted_str: str, user_id: str) -> Any:
    """Decrypt user-specific field"""
    data = json.loads(encrypted_str)
    encrypted_data = EncryptedData(
        data=data["data"],
        key_id=data["key_id"],
        algorithm=EncryptionAlgorithm(data["algorithm"]),
        metadata=data["metadata"],
        timestamp=datetime.fromisoformat(data["timestamp"])
    )
    return encryption_manager.decrypt_field(field_name, encrypted_data, user_id)