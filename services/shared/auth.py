from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import jwt
from passlib.context import CryptContext
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import structlog

logger = structlog.get_logger()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT token handling
security = HTTPBearer()


class AuthManager:
    """JWT token management and user authentication."""
    
    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        self.secret_key = secret_key
        self.algorithm = algorithm
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return pwd_context.verify(plain_password, hashed_password)
    
    def get_password_hash(self, password: str) -> str:
        """Hash a password."""
        return pwd_context.hash(password)
    
    def create_access_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Create a JWT access token."""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=15)
        
        to_encode.update({"exp": expire, "iat": datetime.utcnow()})
        
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def decode_access_token(self, token: str) -> Dict[str, Any]:
        """Decode and validate a JWT access token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    def get_current_user(self, credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
        """Get current user from JWT token."""
        payload = self.decode_access_token(credentials.credentials)
        
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return {
            "user_id": user_id,
            "email": payload.get("email"),
            "roles": payload.get("roles", []),
            "permissions": payload.get("permissions", []),
        }


class RoleBasedAuth:
    """Role-based authorization."""
    
    def __init__(self, auth_manager: AuthManager):
        self.auth_manager = auth_manager
    
    def require_role(self, required_role: str):
        """Decorator to require a specific role."""
        def decorator(current_user: Dict[str, Any] = Depends(self.auth_manager.get_current_user)):
            user_roles = current_user.get("roles", [])
            if required_role not in user_roles:
                logger.warning(
                    "Access denied - insufficient role",
                    user_id=current_user.get("user_id"),
                    required_role=required_role,
                    user_roles=user_roles
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions. Required role: {required_role}"
                )
            return current_user
        return decorator
    
    def require_permission(self, required_permission: str):
        """Decorator to require a specific permission."""
        def decorator(current_user: Dict[str, Any] = Depends(self.auth_manager.get_current_user)):
            user_permissions = current_user.get("permissions", [])
            if required_permission not in user_permissions:
                logger.warning(
                    "Access denied - insufficient permission",
                    user_id=current_user.get("user_id"),
                    required_permission=required_permission,
                    user_permissions=user_permissions
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions. Required permission: {required_permission}"
                )
            return current_user
        return decorator
    
    def require_any_role(self, required_roles: list[str]):
        """Decorator to require any of the specified roles."""
        def decorator(current_user: Dict[str, Any] = Depends(self.auth_manager.get_current_user)):
            user_roles = current_user.get("roles", [])
            if not any(role in user_roles for role in required_roles):
                logger.warning(
                    "Access denied - insufficient roles",
                    user_id=current_user.get("user_id"),
                    required_roles=required_roles,
                    user_roles=user_roles
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions. Required roles: {required_roles}"
                )
            return current_user
        return decorator


# Global auth manager instance
auth_manager: Optional[AuthManager] = None
role_based_auth: Optional[RoleBasedAuth] = None


def init_auth(secret_key: str) -> tuple[AuthManager, RoleBasedAuth]:
    """Initialize authentication managers."""
    global auth_manager, role_based_auth
    auth_manager = AuthManager(secret_key)
    role_based_auth = RoleBasedAuth(auth_manager)
    return auth_manager, role_based_auth


def get_auth_manager() -> AuthManager:
    """Get the global auth manager instance."""
    if auth_manager is None:
        raise RuntimeError("Auth not initialized. Call init_auth() first.")
    return auth_manager


def get_role_based_auth() -> RoleBasedAuth:
    """Get the global role-based auth instance."""
    if role_based_auth is None:
        raise RuntimeError("Auth not initialized. Call init_auth() first.")
    return role_based_auth


# Common permission constants
class Permissions:
    # CRM permissions
    CRM_READ = "crm:read"
    CRM_WRITE = "crm:write"
    CRM_DELETE = "crm:delete"
    CRM_ADMIN = "crm:admin"
    
    # ERP permissions
    ERP_READ = "erp:read"
    ERP_WRITE = "erp:write"
    ERP_DELETE = "erp:delete"
    ERP_ADMIN = "erp:admin"
    
    # Notification permissions
    NOTIFICATION_SEND = "notification:send"
    NOTIFICATION_ADMIN = "notification:admin"
    
    # System permissions
    SYSTEM_ADMIN = "system:admin"


# Common role constants
class Roles:
    SUPER_ADMIN = "super_admin"
    CRM_ADMIN = "crm_admin"
    ERP_ADMIN = "erp_admin"
    SALES_MANAGER = "sales_manager"
    SALES_REP = "sales_rep"
    INVENTORY_MANAGER = "inventory_manager"
    WAREHOUSE_STAFF = "warehouse_staff"
    CUSTOMER_SERVICE = "customer_service"
    USER = "user"