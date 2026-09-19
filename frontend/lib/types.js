/**
 * types.js — Defect Guard Domain Contracts and Enums
 *
 * Strictly mirrors backend/src/core/models.py.
 * Shared between Mock Mode and the presentation UI.
 */

const DocumentRole = Object.freeze({
  AADHAAR: 'AADHAAR',
  INCOME_CERTIFICATE: 'INCOME_CERTIFICATE',
  MARKSHEET: 'MARKSHEET',
  BANK_PROOF: 'BANK_PROOF',
});

const PacketStatus = Object.freeze({
  DRAFT: 'DRAFT',
  EXTRACTING: 'EXTRACTING',
  READY_TO_CHECK: 'READY_TO_CHECK',
  CHECKING: 'CHECKING',
  CHECKED: 'CHECKED',
});

const DocumentStatus = Object.freeze({
  PENDING_UPLOAD: 'PENDING_UPLOAD',
  UPLOADED: 'UPLOADED',
  EXTRACTING: 'EXTRACTING',
  EXTRACTED: 'EXTRACTED',
  EXTRACTION_FAILED: 'EXTRACTION_FAILED',
});

const Severity = Object.freeze({
  RED: 'RED',
  AMBER: 'AMBER',
  INFO: 'INFO',
});

const VerdictBand = Object.freeze({
  READY: 'READY',       // score >= 85
  RISKY: 'RISKY',       // 60 <= score < 85
  NOT_READY: 'NOT_READY' // score < 60
});

const REQUIRED_ROLES = Object.freeze([
  DocumentRole.AADHAAR,
  DocumentRole.MARKSHEET,
  DocumentRole.INCOME_CERTIFICATE,
  DocumentRole.BANK_PROOF,
]);

// Export for Node (tests) and Browser (window)
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    DocumentRole,
    PacketStatus,
    DocumentStatus,
    Severity,
    VerdictBand,
    REQUIRED_ROLES,
  };
} else {
  window.DefectGuardTypes = {
    DocumentRole,
    PacketStatus,
    DocumentStatus,
    Severity,
    VerdictBand,
    REQUIRED_ROLES,
  };
}
