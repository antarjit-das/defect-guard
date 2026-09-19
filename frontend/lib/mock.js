/**
 * mock.js — Deterministic Defect Guard Mock Engine
 *
 * Implements an offline-first state machine that faithfully mirrors
 * the backend Pydantic contracts and API behavior without requiring AWS.
 */

(function (root, factory) {
  if (typeof module !== 'undefined' && module.exports) {
    const types = require('./types');
    const mockData = require('./mock-data');
    module.exports = factory(types, mockData);
  } else {
    root.DefectGuardMock = factory(root.DefectGuardTypes, root.DefectGuardMockData);
  }
})(typeof self !== 'undefined' ? self : this, function (types, mockData) {
  'use strict';

  const STORAGE_KEY = 'defect_guard_mock_session';

  // Configurable deterministic timings (can be overridden by config.js)
  const defaultTimings = {
    CREATE_PACKET_DELAY: 200,
    UPLOAD_STEP_DELAY: 80,   // 5 steps = ~400ms
    EXTRACT_DELAY: 700,
    CHECK_DELAY: 1200,
  };

  function getTimings() {
    if (typeof window !== 'undefined' && window.DEFECT_GUARD_TIMINGS) {
      return Object.assign({}, defaultTimings, window.DEFECT_GUARD_TIMINGS);
    }
    return defaultTimings;
  }

  function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  class MockEngine {
    constructor() {
      this.currentPacket = this._loadSession();
    }

    _loadSession() {
      if (typeof sessionStorage === 'undefined') return null;
      try {
        const raw = sessionStorage.getItem(STORAGE_KEY);
        return raw ? JSON.parse(raw) : null;
      } catch (e) {
        return null;
      }
    }

    _saveSession() {
      if (typeof sessionStorage === 'undefined' || !this.currentPacket) return;
      try {
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify(this.currentPacket));
      } catch (e) {}
    }

    reset() {
      this.currentPacket = null;
      if (typeof sessionStorage !== 'undefined') {
        try { sessionStorage.removeItem(STORAGE_KEY); } catch (e) {}
      }
    }

    async createPacket() {
      const timings = getTimings();
      await sleep(timings.CREATE_PACKET_DELAY);

      const now = new Date().toISOString();
      this.currentPacket = {
        packetId: "pkt-demo-2026-0918",
        schemeId: "NIJUT_BABU_2026",
        status: types.PacketStatus.DRAFT,
        createdAt: now,
        updatedAt: now,
        documents: [],
        verdict: null,
        previousScore: null,
        expiresAt: Math.floor(Date.now() / 1000) + 86400
      };
      this._saveSession();

      return {
        packetId: this.currentPacket.packetId,
        schemeId: this.currentPacket.schemeId,
        status: this.currentPacket.status,
        createdAt: this.currentPacket.createdAt
      };
    }

    async requestUploadUrl(packetId, role, file) {
      if (!this.currentPacket) {
        await this.createPacket();
      }

      const roleEnum = types.DocumentRole[role] || role;
      if (!types.REQUIRED_ROLES.includes(roleEnum)) {
        throw new Error(`Invalid document role: ${role}`);
      }

      // Check for replacement: if an active doc with same role exists
      const existingDoc = this.currentPacket.documents.find(
        d => d.role === roleEnum && !d.supersededBy
      );

      const docIndex = this.currentPacket.documents.length + 1;
      const docId = `doc-${role.toLowerCase().replace(/_/g, '-')}-${docIndex}`;

      const docItem = {
        documentId: docId,
        role: roleEnum,
        fileName: file ? file.name : `${role.toLowerCase()}.pdf`,
        contentType: file ? (file.type || 'application/pdf') : 'application/pdf',
        sizeBytes: file ? file.size : 150000,
        pageCount: 1,
        status: types.DocumentStatus.PENDING_UPLOAD,
        objectKey: `packets/${this.currentPacket.packetId}/${docId}.pdf`,
        supersededBy: null,
        extraction: null,
        error: null,
        expiresAt: Math.floor(Date.now() / 1000) + 86400,
        _isReplacement: Boolean(existingDoc),
        _supersedesId: existingDoc ? existingDoc.documentId : null
      };

      this.currentPacket.documents.push(docItem);
      this._saveSession();

      return {
        documentId: docId,
        uploadUrl: `mock-s3://${this.currentPacket.packetId}/${docId}`,
        expiresInSeconds: 300,
        objectKey: docItem.objectKey
      };
    }

    async uploadFile(uploadUrl, file, onProgress) {
      const timings = getTimings();
      const steps = 4;
      for (let i = 1; i <= steps; i++) {
        await sleep(timings.UPLOAD_STEP_DELAY);
        if (typeof onProgress === 'function') {
          onProgress({ percent: Math.round((i / steps) * 100) });
        }
      }
      return { ok: true, status: 200 };
    }

    async markUploaded(packetId, documentId) {
      if (!this.currentPacket) throw new Error("No active packet session");

      const doc = this.currentPacket.documents.find(d => d.documentId === documentId);
      if (!doc) throw new Error(`Document ${documentId} not found`);

      doc.status = types.DocumentStatus.UPLOADED;
      this.currentPacket.status = types.PacketStatus.EXTRACTING;
      this._saveSession();

      // Trigger async extraction simulation in background
      this._runAsyncExtraction(doc);

      return {
        documentId: doc.documentId,
        status: types.DocumentStatus.EXTRACTING
      };
    }

    async _runAsyncExtraction(doc) {
      const timings = getTimings();

      // Stage 1: Transition to EXTRACTING
      await sleep(timings.EXTRACT_DELAY / 2);
      doc.status = types.DocumentStatus.EXTRACTING;
      this._saveSession();

      // Stage 2: Complete Extraction
      await sleep(timings.EXTRACT_DELAY / 2);
      doc.status = types.DocumentStatus.EXTRACTED;

      // Attach appropriate extraction based on role and filename
      if (doc.role === types.DocumentRole.AADHAAR) {
        doc.extraction = JSON.parse(JSON.stringify(mockData.DEMO_EXTRACTIONS.AADHAAR));
      } else if (doc.role === types.DocumentRole.MARKSHEET) {
        doc.extraction = JSON.parse(JSON.stringify(mockData.DEMO_EXTRACTIONS.MARKSHEET));
      } else if (doc.role === types.DocumentRole.BANK_PROOF) {
        doc.extraction = JSON.parse(JSON.stringify(mockData.DEMO_EXTRACTIONS.BANK_PROOF));
      } else if (doc.role === types.DocumentRole.INCOME_CERTIFICATE) {
        // If filename has 250 or it is a replacement, use compliant extraction
        const isCompliant = doc.fileName.includes('250') || doc._isReplacement;
        doc.extraction = JSON.parse(JSON.stringify(
          isCompliant ? mockData.DEMO_EXTRACTIONS.INCOME_COMPLIANT : mockData.DEMO_EXTRACTIONS.INCOME_DEFECTIVE
        ));

        // If this doc supersedes an earlier income doc, mark the old one superseded
        if (doc._supersedesId) {
          const oldDoc = this.currentPacket.documents.find(d => d.documentId === doc._supersedesId);
          if (oldDoc) oldDoc.supersededBy = doc.documentId;
        }
      }

      // Check if all 4 mandatory roles now have an EXTRACTED non-superseded document
      const activeDocs = this.currentPacket.documents.filter(d => !d.supersededBy);
      const extractedRoles = new Set(activeDocs.filter(d => d.status === types.DocumentStatus.EXTRACTED).map(d => d.role));
      const allExtracted = types.REQUIRED_ROLES.every(r => extractedRoles.has(r));

      if (allExtracted) {
        this.currentPacket.status = types.PacketStatus.READY_TO_CHECK;
      }
      this.currentPacket.updatedAt = new Date().toISOString();
      this._saveSession();
    }

    async runCheck(packetId) {
      if (!this.currentPacket) throw new Error("No active packet session");

      const activeDocs = this.currentPacket.documents.filter(d => !d.supersededBy);
      const extractedRoles = new Set(activeDocs.filter(d => d.status === types.DocumentStatus.EXTRACTED).map(d => d.role));
      const hasAll = types.REQUIRED_ROLES.every(r => extractedRoles.has(r));
      if (!hasAll) {
        throw new Error("Cannot run check: not all mandatory documents are extracted");
      }

      this.currentPacket.status = types.PacketStatus.CHECKING;
      this.currentPacket.updatedAt = new Date().toISOString();
      this._saveSession();

      // Trigger async check simulation
      this._runAsyncCheck();

      return {
        checkRunId: `chk-run-${Date.now()}`,
        status: types.PacketStatus.CHECKING
      };
    }

    async _runAsyncCheck() {
      const timings = getTimings();
      await sleep(timings.CHECK_DELAY);

      const activeDocs = this.currentPacket.documents.filter(d => !d.supersededBy);
      const activeIncome = activeDocs.find(d => d.role === types.DocumentRole.INCOME_CERTIFICATE);

      // Check if income is compliant (<= ₹4,00,000)
      let isCompliant = false;
      if (activeIncome && activeIncome.extraction) {
        const incomeField = activeIncome.extraction.fields.find(f => f.fieldKey === 'annual_income');
        if (incomeField && Number(incomeField.normalizedValue) <= 400000) {
          isCompliant = true;
        }
      }

      const now = new Date().toISOString();
      const checkRunId = `chk-run-mock-${Date.now()}`;

      if (isCompliant) {
        // Rechecked Verdict: Score 65 (R-07 resolved)
        const previousScore = (this.currentPacket.verdict && this.currentPacket.verdict.score) || 40;
        this.currentPacket.previousScore = previousScore;
        this.currentPacket.verdict = {
          checkRunId: checkRunId,
          snapshot: {
            rows: mockData.buildSnapshotRows(250000)
          },
          findings: JSON.parse(JSON.stringify(mockData.RECHECK_FINDINGS)),
          score: 65,
          band: types.VerdictBand.RISKY,
          scoreArithmetic: "100 - 25x1 red - 10x1 amber = 65",
          ruleSetVersion: "NIJUT_BABU_2026@1",
          modelId: "mock-engine-v1",
          aiStatus: "OK",
          createdAt: now,
          expiresAt: Math.floor(Date.now() / 1000) + 86400
        };
      } else {
        // Initial Verdict: Score 40 (3 defects: R-01, R-07, R-04)
        this.currentPacket.previousScore = null;
        this.currentPacket.verdict = {
          checkRunId: checkRunId,
          snapshot: {
            rows: mockData.buildSnapshotRows(450000)
          },
          findings: JSON.parse(JSON.stringify(mockData.INITIAL_FINDINGS)),
          score: 40,
          band: types.VerdictBand.NOT_READY,
          scoreArithmetic: "100 - 25x2 red - 10x1 amber = 40",
          ruleSetVersion: "NIJUT_BABU_2026@1",
          modelId: "mock-engine-v1",
          aiStatus: "OK",
          createdAt: now,
          expiresAt: Math.floor(Date.now() / 1000) + 86400
        };
      }

      this.currentPacket.status = types.PacketStatus.CHECKED;
      this.currentPacket.updatedAt = now;
      this._saveSession();
    }

    async getPacket(packetId) {
      if (!this.currentPacket) return null;
      // Return a deep copy to prevent external mutation
      return JSON.parse(JSON.stringify(this.currentPacket));
    }
  }

  return new MockEngine();
});
