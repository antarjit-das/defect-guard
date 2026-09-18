"""Core data models and contracts for Defect Guard.

Strictly adheres to IMPLEMENTATION.md §5 (Data Model) and §9 (Integration Contracts).
All models use Pydantic v2. Zero external AWS imports allowed.
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


# =====================================================================
# Enumerations (Integration Contract C3)
# =====================================================================

class DocumentRole(str, Enum):
    """The 4 mandatory scholarship document roles."""
    AADHAAR = "AADHAAR"
    INCOME_CERTIFICATE = "INCOME_CERTIFICATE"
    MARKSHEET = "MARKSHEET"
    BANK_PROOF = "BANK_PROOF"


class PacketStatus(str, Enum):
    """Lifecycle state of an evaluation packet."""
    DRAFT = "DRAFT"
    EXTRACTING = "EXTRACTING"
    READY_TO_CHECK = "READY_TO_CHECK"
    CHECKING = "CHECKING"
    CHECKED = "CHECKED"


class DocumentStatus(str, Enum):
    """Lifecycle state of an individual uploaded document."""
    PENDING_UPLOAD = "PENDING_UPLOAD"
    UPLOADED = "UPLOADED"
    EXTRACTING = "EXTRACTING"
    EXTRACTED = "EXTRACTED"
    EXTRACTION_FAILED = "EXTRACTION_FAILED"


class Severity(str, Enum):
    """Finding severity level."""
    RED = "RED"       # Definite defect or scheme rule breach (deducts 25 pts)
    AMBER = "AMBER"   # Warning, discrepancy, or unconfirmed detail (deducts 10 pts)
    INFO = "INFO"     # Informational note (deducts 0 pts)


class FindingCategory(str, Enum):
    """Categorization for reported defects."""
    IDENTITY = "IDENTITY"
    ELIGIBILITY = "ELIGIBILITY"
    BANK = "BANK"
    DOCUMENT_FORMAT = "DOCUMENT_FORMAT"
    COMPLETENESS = "COMPLETENESS"
    QUALITY = "QUALITY"


class VerdictBand(str, Enum):
    """Readiness rating band derived from the numerical score."""
    NOT_READY = "NOT_READY"  # Score < 60
    RISKY = "RISKY"          # Score 60 - 84
    READY = "READY"          # Score >= 85


class AIStatus(str, Enum):
    """Traceability of Bedrock adjudication outcome."""
    OK = "OK"
    FALLBACK_TEMPLATE = "FALLBACK_TEMPLATE"
    FALLBACK_AFTER_INVALID_JSON = "FALLBACK_AFTER_INVALID_JSON"


class DocumentQuality(str, Enum):
    """Document readability / image quality rating."""
    GOOD = "GOOD"
    POOR = "POOR"


# =====================================================================
# Document Extraction Models
# =====================================================================

class ExtractedField(BaseModel):
    """A typed field extracted from a single document."""
    model_config = ConfigDict(extra="forbid")

    fieldKey: str
    rawValue: Optional[str] = None
    normalizedValue: Optional[Any] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    evidence: Optional[str] = None
    source: str = "TEXTRACT_QUERY"
    needsConfirmation: bool = False


class DocumentExtraction(BaseModel):
    """Extracted payload stored in DynamoDB DOC# item."""
    model_config = ConfigDict(extra="forbid")

    roleConfirmed: bool = True
    documentQuality: DocumentQuality = DocumentQuality.GOOD
    fields: List[ExtractedField] = Field(default_factory=list)
    notes: Optional[str] = None


class DocumentItem(BaseModel):
    """Represents a document within a packet."""
    model_config = ConfigDict(extra="ignore")

    documentId: str
    role: DocumentRole
    fileName: str
    contentType: str
    sizeBytes: int
    pageCount: int = 1
    status: DocumentStatus = DocumentStatus.PENDING_UPLOAD
    objectKey: Optional[str] = None
    supersededBy: Optional[str] = None
    extraction: Optional[DocumentExtraction] = None
    error: Optional[str] = None
    expiresAt: Optional[int] = None


# =====================================================================
# Application Snapshot Models
# =====================================================================

class SnapshotRow(BaseModel):
    """One row in the cross-document snapshot table."""
    model_config = ConfigDict(extra="forbid")

    fieldKey: str
    label: str
    valuesByRole: Dict[str, Optional[str]] = Field(default_factory=dict)
    canonicalValue: Optional[str] = None
    canonicalSource: Optional[str] = None
    hasDisagreement: bool = False


class Snapshot(BaseModel):
    """Complete cross-document snapshot."""
    model_config = ConfigDict(extra="forbid")

    rows: List[SnapshotRow] = Field(default_factory=list)


# =====================================================================
# Finding & Verdict Models
# =====================================================================

class DocumentReference(BaseModel):
    """Reference to a document role and the conflicting value observed."""
    model_config = ConfigDict(extra="forbid")

    role: DocumentRole
    value: Optional[str] = None


class Finding(BaseModel):
    """A defect or discrepancy identified by the rule engine / AI."""
    model_config = ConfigDict(extra="forbid")

    findingId: str
    ruleId: str
    title: str
    severity: Severity
    category: FindingCategory
    documents: List[DocumentReference] = Field(default_factory=list)
    reason: str
    fixInstruction: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source: str
    needsAdjudication: bool = False


class Verdict(BaseModel):
    """Final assessment written to VERDICT#<ts> item."""
    model_config = ConfigDict(extra="ignore")

    checkRunId: str
    snapshot: Snapshot
    findings: List[Finding] = Field(default_factory=list)
    score: int = Field(ge=0, le=100)
    band: VerdictBand
    scoreArithmetic: str
    ruleSetVersion: str = "NIJUT_BABU_2026@1"
    modelId: Optional[str] = None
    aiStatus: AIStatus = AIStatus.OK
    createdAt: str
    expiresAt: Optional[int] = None


# =====================================================================
# Full Packet Envelope (GET /packets/{id})
# =====================================================================

class Packet(BaseModel):
    """Full packet payload returned to the UI client."""
    model_config = ConfigDict(extra="ignore")

    packetId: str
    schemeId: str = "NIJUT_BABU_2026"
    status: PacketStatus = PacketStatus.DRAFT
    createdAt: str
    updatedAt: str
    documents: List[DocumentItem] = Field(default_factory=list)
    verdict: Optional[Verdict] = None
    previousScore: Optional[int] = None
    expiresAt: Optional[int] = None


# =====================================================================
# API Request / Response Contracts (§6)
# =====================================================================

class CreatePacketResponse(BaseModel):
    packetId: str
    schemeId: str = "NIJUT_BABU_2026"
    status: PacketStatus = PacketStatus.DRAFT
    createdAt: str


class CreateUploadUrlRequest(BaseModel):
    role: DocumentRole
    fileName: str
    contentType: str
    sizeBytes: int


class CreateUploadUrlResponse(BaseModel):
    documentId: str
    uploadUrl: str
    expiresInSeconds: int = 300
    objectKey: str


class MarkUploadedResponse(BaseModel):
    documentId: str
    status: DocumentStatus = DocumentStatus.EXTRACTING


class RunCheckResponse(BaseModel):
    checkRunId: str
    status: PacketStatus = PacketStatus.CHECKING


class ApiErrorDetail(BaseModel):
    code: str
    message: str


class ApiErrorResponse(BaseModel):
    error: ApiErrorDetail
