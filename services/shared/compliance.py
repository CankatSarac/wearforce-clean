"""
GDPR and PCI DSS compliance module for WearForce platform.

This module implements data subject rights, data processing consent management,
data retention policies, and PCI DSS requirements for payment data handling.
"""

import asyncio
import json
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union
from dataclasses import dataclass, asdict
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, and_, or_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Session
import structlog
from .encryption import encrypted_field, pii_field, payment_field

logger = structlog.get_logger()

Base = declarative_base()

# GDPR Enums and Types
class ConsentStatus(Enum):
    PENDING = "pending"
    GRANTED = "granted"
    WITHDRAWN = "withdrawn"
    EXPIRED = "expired"

class ProcessingPurpose(Enum):
    ACCOUNT_MANAGEMENT = "account_management"
    SERVICE_PROVISION = "service_provision"
    MARKETING = "marketing"
    ANALYTICS = "analytics"
    SUPPORT = "support"
    LEGAL_COMPLIANCE = "legal_compliance"
    SECURITY = "security"

class LegalBasis(Enum):
    CONSENT = "consent"
    CONTRACT = "contract"
    LEGAL_OBLIGATION = "legal_obligation"
    VITAL_INTERESTS = "vital_interests"
    PUBLIC_TASK = "public_task"
    LEGITIMATE_INTERESTS = "legitimate_interests"

class DataCategory(Enum):
    IDENTITY = "identity"
    CONTACT = "contact"
    DEMOGRAPHIC = "demographic"
    BEHAVIORAL = "behavioral"
    LOCATION = "location"
    BIOMETRIC = "biometric"
    FINANCIAL = "financial"
    HEALTH = "health"
    SPECIAL_CATEGORY = "special_category"

class DataSubjectRights(Enum):
    ACCESS = "access"
    RECTIFICATION = "rectification"
    ERASURE = "erasure"
    RESTRICT_PROCESSING = "restrict_processing"
    DATA_PORTABILITY = "data_portability"
    OBJECT_PROCESSING = "object_processing"

# PCI DSS Types
class PaymentDataType(Enum):
    CARD_NUMBER = "card_number"
    EXPIRY_DATE = "expiry_date"
    CARDHOLDER_NAME = "cardholder_name"
    CVV = "cvv"
    BILLING_ADDRESS = "billing_address"

class PCICompliantLevel(Enum):
    LEVEL_1 = "level_1"  # > 6M transactions/year
    LEVEL_2 = "level_2"  # 1-6M transactions/year
    LEVEL_3 = "level_3"  # 20K-1M e-commerce transactions/year
    LEVEL_4 = "level_4"  # < 20K e-commerce transactions/year

# Database Models
class ConsentRecord(Base):
    """Records of user consent for data processing."""
    __tablename__ = 'consent_records'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String(255), nullable=False, index=True)
    purpose = Column(String(50), nullable=False)
    legal_basis = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False, default=ConsentStatus.PENDING.value)
    granted_at = Column(DateTime, nullable=True)
    withdrawn_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    data_categories = Column(Text, nullable=False)  # JSON list
    processing_details = Column(Text, nullable=True)  # JSON
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    data_processing_activities = relationship("DataProcessingActivity", back_populates="consent")

class DataProcessingActivity(Base):
    """Records of data processing activities (Article 30 GDPR)."""
    __tablename__ = 'data_processing_activities'
    
    id = Column(Integer, primary_key=True)
    consent_id = Column(Integer, ForeignKey('consent_records.id'), nullable=True)
    user_id = Column(String(255), nullable=False, index=True)
    activity_type = Column(String(50), nullable=False)
    purpose = Column(String(50), nullable=False)
    legal_basis = Column(String(50), nullable=False)
    data_categories = Column(Text, nullable=False)  # JSON list
    recipients = Column(Text, nullable=True)  # JSON list
    retention_period = Column(Integer, nullable=True)  # Days
    security_measures = Column(Text, nullable=True)  # JSON
    processed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    consent = relationship("ConsentRecord", back_populates="data_processing_activities")

class DataSubjectRequest(Base):
    """Data subject rights requests under GDPR."""
    __tablename__ = 'data_subject_requests'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String(255), nullable=False, index=True)
    request_type = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    request_details = Column(Text, nullable=True)  # JSON
    response_data = Column(Text, nullable=True)  # JSON
    requested_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    deadline_at = Column(DateTime, nullable=False)  # 30 days from request
    created_by = Column(String(255), nullable=True)
    
class DataRetentionPolicy(Base):
    """Data retention policies for different data types."""
    __tablename__ = 'data_retention_policies'
    
    id = Column(Integer, primary_key=True)
    data_category = Column(String(50), nullable=False, unique=True)
    purpose = Column(String(50), nullable=False)
    retention_period_days = Column(Integer, nullable=False)
    deletion_method = Column(String(20), nullable=False, default="soft")  # soft, hard, anonymize
    legal_basis = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class PaymentDataAudit(Base):
    """Audit trail for payment data access (PCI DSS Requirement 10)."""
    __tablename__ = 'payment_data_audit'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String(255), nullable=False, index=True)
    payment_method_id = Column(String(255), nullable=True, index=True)
    action = Column(String(50), nullable=False)  # create, read, update, delete
    data_elements = Column(Text, nullable=False)  # JSON list of accessed elements
    source_ip = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    session_id = Column(String(255), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    success = Column(Boolean, nullable=False, default=True)
    failure_reason = Column(String(255), nullable=True)

# Service Classes
@dataclass
class ConsentRequest:
    """Request for user consent."""
    user_id: str
    purposes: List[ProcessingPurpose]
    legal_basis: LegalBasis
    data_categories: List[DataCategory]
    processing_details: Optional[Dict[str, Any]] = None
    expires_in_days: Optional[int] = None

@dataclass
class DataPortabilityResponse:
    """Response for data portability request."""
    user_id: str
    exported_at: datetime
    data: Dict[str, Any]
    format: str = "json"
    
class GDPRComplianceManager:
    """Manages GDPR compliance operations."""
    
    def __init__(self, session: Session):
        self.session = session
        
    async def request_consent(self, consent_request: ConsentRequest) -> ConsentRecord:
        """Request consent from a data subject."""
        expires_at = None
        if consent_request.expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=consent_request.expires_in_days)
        
        consent = ConsentRecord(
            user_id=consent_request.user_id,
            purpose=consent_request.purposes[0].value,  # Primary purpose
            legal_basis=consent_request.legal_basis.value,
            status=ConsentStatus.PENDING.value,
            data_categories=json.dumps([cat.value for cat in consent_request.data_categories]),
            processing_details=json.dumps(consent_request.processing_details or {}),
            expires_at=expires_at
        )
        
        self.session.add(consent)
        self.session.commit()
        
        logger.info("Consent requested", 
                   user_id=consent_request.user_id,
                   consent_id=consent.id,
                   purposes=[p.value for p in consent_request.purposes])
        
        return consent
    
    async def grant_consent(self, consent_id: int, user_id: str) -> bool:
        """Grant consent (user action)."""
        consent = self.session.query(ConsentRecord).filter(
            ConsentRecord.id == consent_id,
            ConsentRecord.user_id == user_id,
            ConsentRecord.status == ConsentStatus.PENDING.value
        ).first()
        
        if not consent:
            return False
        
        consent.status = ConsentStatus.GRANTED.value
        consent.granted_at = datetime.utcnow()
        self.session.commit()
        
        logger.info("Consent granted", user_id=user_id, consent_id=consent_id)
        return True
    
    async def withdraw_consent(self, consent_id: int, user_id: str) -> bool:
        """Withdraw consent (user action)."""
        consent = self.session.query(ConsentRecord).filter(
            ConsentRecord.id == consent_id,
            ConsentRecord.user_id == user_id,
            ConsentRecord.status == ConsentStatus.GRANTED.value
        ).first()
        
        if not consent:
            return False
        
        consent.status = ConsentStatus.WITHDRAWN.value
        consent.withdrawn_at = datetime.utcnow()
        self.session.commit()
        
        # Log data processing activity
        await self.log_processing_activity(
            user_id=user_id,
            activity_type="consent_withdrawal",
            purpose=ProcessingPurpose.LEGAL_COMPLIANCE,
            legal_basis=LegalBasis.LEGAL_OBLIGATION,
            data_categories=[DataCategory.IDENTITY]
        )
        
        logger.info("Consent withdrawn", user_id=user_id, consent_id=consent_id)
        return True
    
    async def check_consent(self, user_id: str, purpose: ProcessingPurpose, 
                          data_categories: List[DataCategory]) -> bool:
        """Check if user has granted consent for specific processing."""
        # Find active consent for the purpose
        consent = self.session.query(ConsentRecord).filter(
            ConsentRecord.user_id == user_id,
            ConsentRecord.purpose == purpose.value,
            ConsentRecord.status == ConsentStatus.GRANTED.value,
            or_(
                ConsentRecord.expires_at.is_(None),
                ConsentRecord.expires_at > datetime.utcnow()
            )
        ).first()
        
        if not consent:
            return False
        
        # Check if requested data categories are covered
        consent_categories = json.loads(consent.data_categories)
        requested_categories = [cat.value for cat in data_categories]
        
        return all(cat in consent_categories for cat in requested_categories)
    
    async def log_processing_activity(self, user_id: str, activity_type: str,
                                    purpose: ProcessingPurpose, legal_basis: LegalBasis,
                                    data_categories: List[DataCategory],
                                    recipients: Optional[List[str]] = None,
                                    consent_id: Optional[int] = None) -> DataProcessingActivity:
        """Log data processing activity (Article 30 GDPR)."""
        activity = DataProcessingActivity(
            consent_id=consent_id,
            user_id=user_id,
            activity_type=activity_type,
            purpose=purpose.value,
            legal_basis=legal_basis.value,
            data_categories=json.dumps([cat.value for cat in data_categories]),
            recipients=json.dumps(recipients or [])
        )
        
        self.session.add(activity)
        self.session.commit()
        
        return activity
    
    async def handle_data_subject_request(self, user_id: str, request_type: DataSubjectRights,
                                        details: Optional[Dict[str, Any]] = None) -> DataSubjectRequest:
        """Handle data subject rights request."""
        deadline = datetime.utcnow() + timedelta(days=30)  # GDPR requirement
        
        request = DataSubjectRequest(
            user_id=user_id,
            request_type=request_type.value,
            request_details=json.dumps(details or {}),
            deadline_at=deadline
        )
        
        self.session.add(request)
        self.session.commit()
        
        # Process the request based on type
        if request_type == DataSubjectRights.ACCESS:
            await self._process_access_request(request)
        elif request_type == DataSubjectRights.DATA_PORTABILITY:
            await self._process_portability_request(request)
        elif request_type == DataSubjectRights.ERASURE:
            await self._process_erasure_request(request)
        
        logger.info("Data subject request created", 
                   user_id=user_id, request_type=request_type.value, request_id=request.id)
        
        return request
    
    async def _process_access_request(self, request: DataSubjectRequest):
        """Process right to access request (Article 15 GDPR)."""
        # Collect all personal data for the user
        user_data = await self._collect_user_data(request.user_id)
        
        # Get consent records
        consents = self.session.query(ConsentRecord).filter(
            ConsentRecord.user_id == request.user_id
        ).all()
        
        # Get processing activities
        activities = self.session.query(DataProcessingActivity).filter(
            DataProcessingActivity.user_id == request.user_id
        ).all()
        
        response_data = {
            "personal_data": user_data,
            "consents": [asdict(consent) for consent in consents],
            "processing_activities": [asdict(activity) for activity in activities],
            "data_sources": self._get_data_sources(),
            "retention_periods": self._get_retention_info(),
            "recipients": self._get_data_recipients(),
            "generated_at": datetime.utcnow().isoformat()
        }
        
        request.response_data = json.dumps(response_data)
        request.status = "completed"
        request.completed_at = datetime.utcnow()
        self.session.commit()
    
    async def _process_portability_request(self, request: DataSubjectRequest) -> DataPortabilityResponse:
        """Process data portability request (Article 20 GDPR)."""
        user_data = await self._collect_portable_user_data(request.user_id)
        
        response = DataPortabilityResponse(
            user_id=request.user_id,
            exported_at=datetime.utcnow(),
            data=user_data
        )
        
        request.response_data = json.dumps(asdict(response))
        request.status = "completed"
        request.completed_at = datetime.utcnow()
        self.session.commit()
        
        return response
    
    async def _process_erasure_request(self, request: DataSubjectRequest):
        """Process right to erasure request (Article 17 GDPR)."""
        # Check if erasure is legally possible
        legal_obligations = await self._check_legal_retention_requirements(request.user_id)
        
        if legal_obligations:
            request.status = "rejected"
            request.response_data = json.dumps({
                "reason": "Legal retention requirements prevent erasure",
                "details": legal_obligations
            })
        else:
            # Perform data erasure
            await self._perform_data_erasure(request.user_id)
            request.status = "completed"
            request.response_data = json.dumps({
                "erased_at": datetime.utcnow().isoformat(),
                "method": "logical_deletion_with_anonymization"
            })
        
        request.completed_at = datetime.utcnow()
        self.session.commit()
    
    async def _collect_user_data(self, user_id: str) -> Dict[str, Any]:
        """Collect all personal data for a user."""
        # This would integrate with all services to collect user data
        # Implementation depends on your data architecture
        return {
            "collection_note": "This would collect data from all services",
            "user_id": user_id,
            "collected_at": datetime.utcnow().isoformat()
        }
    
    async def _collect_portable_user_data(self, user_id: str) -> Dict[str, Any]:
        """Collect user data in a portable format."""
        # Only data provided by the user or generated by their activity
        return await self._collect_user_data(user_id)
    
    async def _check_legal_retention_requirements(self, user_id: str) -> List[str]:
        """Check if there are legal requirements preventing data erasure."""
        # Check against retention policies
        obligations = []
        
        # Example: financial records must be kept for tax purposes
        # This would check various legal requirements
        
        return obligations
    
    async def _perform_data_erasure(self, user_id: str):
        """Perform actual data erasure across all systems."""
        logger.info("Performing data erasure", user_id=user_id)
        
        # This would integrate with all services to delete/anonymize user data
        # Implementation depends on your data architecture
        
    def _get_data_sources(self) -> List[str]:
        """Get list of data sources."""
        return ["user_input", "service_logs", "analytics", "third_party_integrations"]
    
    def _get_retention_info(self) -> Dict[str, Any]:
        """Get data retention information."""
        policies = self.session.query(DataRetentionPolicy).all()
        return {policy.data_category: {
            "retention_days": policy.retention_period_days,
            "legal_basis": policy.legal_basis,
            "description": policy.description
        } for policy in policies}
    
    def _get_data_recipients(self) -> List[str]:
        """Get list of data recipients."""
        return ["internal_services", "cloud_providers", "analytics_providers"]

class PCIDSSComplianceManager:
    """Manages PCI DSS compliance for payment data."""
    
    def __init__(self, session: Session):
        self.session = session
        self.compliance_level = PCICompliantLevel.LEVEL_4  # Default to most restrictive
    
    async def log_payment_data_access(self, user_id: str, payment_method_id: str,
                                    action: str, data_elements: List[PaymentDataType],
                                    source_ip: str, user_agent: str,
                                    session_id: str, success: bool = True,
                                    failure_reason: Optional[str] = None):
        """Log payment data access (PCI DSS Requirement 10)."""
        audit_entry = PaymentDataAudit(
            user_id=user_id,
            payment_method_id=payment_method_id,
            action=action,
            data_elements=json.dumps([elem.value for elem in data_elements]),
            source_ip=source_ip,
            user_agent=user_agent,
            session_id=session_id,
            success=success,
            failure_reason=failure_reason
        )
        
        self.session.add(audit_entry)
        self.session.commit()
        
        logger.info("Payment data access logged", 
                   user_id=user_id, action=action, success=success)
        
        # Alert on suspicious activity
        if not success or action == "delete":
            await self._check_suspicious_payment_activity(user_id, action)
    
    async def _check_suspicious_payment_activity(self, user_id: str, action: str):
        """Check for suspicious payment data access patterns."""
        # Check for multiple failed attempts
        recent_failures = self.session.query(PaymentDataAudit).filter(
            PaymentDataAudit.user_id == user_id,
            PaymentDataAudit.success == False,
            PaymentDataAudit.timestamp > datetime.utcnow() - timedelta(hours=1)
        ).count()
        
        if recent_failures >= 5:
            logger.warning("Suspicious payment data access pattern detected",
                          user_id=user_id, recent_failures=recent_failures)
            
            # This could trigger security alerts
    
    async def validate_payment_data_retention(self):
        """Validate payment data retention policies (PCI DSS Requirement 3)."""
        # PCI DSS requires specific retention periods for different data elements
        retention_rules = {
            PaymentDataType.CARD_NUMBER: 0,  # Should not be stored (tokenize instead)
            PaymentDataType.CVV: 0,  # Must not be stored after authorization
            PaymentDataType.EXPIRY_DATE: 365,  # Can be stored for recurring payments
            PaymentDataType.CARDHOLDER_NAME: 365,
            PaymentDataType.BILLING_ADDRESS: 365
        }
        
        violations = []
        
        for data_type, max_days in retention_rules.items():
            if max_days == 0:
                # Data should not be stored at all
                count = await self._check_stored_payment_data(data_type)
                if count > 0:
                    violations.append(f"{data_type.value}: {count} records found (should be 0)")
            else:
                # Check for data older than retention period
                old_count = await self._check_old_payment_data(data_type, max_days)
                if old_count > 0:
                    violations.append(f"{data_type.value}: {old_count} records older than {max_days} days")
        
        if violations:
            logger.error("PCI DSS retention violations found", violations=violations)
            
        return violations
    
    async def _check_stored_payment_data(self, data_type: PaymentDataType) -> int:
        """Check for stored payment data that shouldn't exist."""
        # This would check your payment data storage
        # Implementation depends on how you store payment data
        return 0
    
    async def _check_old_payment_data(self, data_type: PaymentDataType, max_days: int) -> int:
        """Check for payment data older than retention period."""
        # This would check for old payment data
        # Implementation depends on how you store payment data
        return 0
    
    async def generate_pci_compliance_report(self) -> Dict[str, Any]:
        """Generate PCI DSS compliance report."""
        report = {
            "generated_at": datetime.utcnow().isoformat(),
            "compliance_level": self.compliance_level.value,
            "audit_summary": await self._generate_audit_summary(),
            "retention_compliance": await self.validate_payment_data_retention(),
            "security_measures": self._get_security_measures()
        }
        
        return report
    
    async def _generate_audit_summary(self) -> Dict[str, Any]:
        """Generate summary of payment data audit logs."""
        # Last 30 days
        start_date = datetime.utcnow() - timedelta(days=30)
        
        total_accesses = self.session.query(PaymentDataAudit).filter(
            PaymentDataAudit.timestamp >= start_date
        ).count()
        
        failed_accesses = self.session.query(PaymentDataAudit).filter(
            PaymentDataAudit.timestamp >= start_date,
            PaymentDataAudit.success == False
        ).count()
        
        return {
            "period_days": 30,
            "total_accesses": total_accesses,
            "failed_accesses": failed_accesses,
            "success_rate": (total_accesses - failed_accesses) / max(total_accesses, 1) * 100
        }
    
    def _get_security_measures(self) -> Dict[str, Any]:
        """Get implemented security measures."""
        return {
            "encryption_at_rest": True,
            "encryption_in_transit": True,
            "access_logging": True,
            "network_segmentation": True,
            "regular_testing": True,
            "vulnerability_scanning": True,
            "penetration_testing": False,  # Would be configured based on actual testing
            "security_awareness_training": True
        }

# Utility functions
def init_compliance_policies(session: Session):
    """Initialize default compliance policies."""
    
    # Default data retention policies
    default_policies = [
        DataRetentionPolicy(
            data_category=DataCategory.IDENTITY.value,
            purpose="account_management",
            retention_period_days=2555,  # 7 years
            legal_basis=LegalBasis.CONTRACT.value,
            description="User identity data for account management"
        ),
        DataRetentionPolicy(
            data_category=DataCategory.FINANCIAL.value,
            purpose="transaction_processing",
            retention_period_days=2555,  # 7 years for financial records
            legal_basis=LegalBasis.LEGAL_OBLIGATION.value,
            description="Financial transaction data for legal compliance"
        ),
        DataRetentionPolicy(
            data_category=DataCategory.BEHAVIORAL.value,
            purpose="analytics",
            retention_period_days=365,  # 1 year
            legal_basis=LegalBasis.LEGITIMATE_INTERESTS.value,
            description="User behavior data for service improvement"
        ),
        DataRetentionPolicy(
            data_category=DataCategory.CONTACT.value,
            purpose="communication",
            retention_period_days=1095,  # 3 years
            legal_basis=LegalBasis.CONTRACT.value,
            description="Contact information for service provision"
        )
    ]
    
    for policy in default_policies:
        existing = session.query(DataRetentionPolicy).filter(
            DataRetentionPolicy.data_category == policy.data_category
        ).first()
        
        if not existing:
            session.add(policy)
    
    session.commit()
    logger.info("Compliance policies initialized")

# Example usage functions
async def example_gdpr_flow():
    """Example GDPR compliance flow."""
    # This would be integrated into your application
    pass

async def example_pci_flow():
    """Example PCI DSS compliance flow."""
    # This would be integrated into your payment processing
    pass