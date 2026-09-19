/**
 * api.js — Unified Defect Guard API Client
 *
 * Implements the gateway/adapter pattern:
 * When DEFECT_GUARD_MOCK=true (or ?mock=1), routes calls to the deterministic
 * local MockEngine (frontend/lib/mock.js).
 * When DEFECT_GUARD_MOCK=false, calls the live AWS API Gateway + S3.
 */

(function (root, factory) {
  if (typeof module !== 'undefined' && module.exports) {
    const mock = require('./mock');
    module.exports = factory(mock);
  } else {
    root.DefectGuardAPI = factory(root.DefectGuardMock);
  }
})(typeof self !== 'undefined' ? self : this, function (mockEngine) {
  'use strict';

  function getBaseUrl() {
    if (typeof window !== 'undefined' && window.DEFECT_GUARD_API_URL) {
      return window.DEFECT_GUARD_API_URL.replace(/\/+$/, '');
    }
    return '';
  }

  function isMockMode() {
    if (typeof window === 'undefined') return true;

    // Check URL query parameter: ?mock=1 or ?mock=0
    const params = new URLSearchParams(window.location.search);
    if (params.has('mock')) {
      return params.get('mock') === '1' || params.get('mock') === 'true';
    }

    // Check sessionStorage override
    const stored = sessionStorage.getItem('DEFECT_GUARD_MOCK_OVERRIDE');
    if (stored !== null) {
      return stored === 'true';
    }

    // Default to window.DEFECT_GUARD_MOCK (or true for standalone offline safety)
    return window.DEFECT_GUARD_MOCK !== false;
  }

  function setMockMode(enabled) {
    if (typeof sessionStorage !== 'undefined') {
      sessionStorage.setItem('DEFECT_GUARD_MOCK_OVERRIDE', String(enabled));
    }
    if (typeof window !== 'undefined') {
      window.DEFECT_GUARD_MOCK = enabled;
    }
  }

  const API = {
    isMockMode,
    setMockMode,

    async createPacket() {
      if (isMockMode()) {
        return await mockEngine.createPacket();
      }

      const api = getBaseUrl();
      if (!api) throw new Error("AWS API URL not configured.");

      const res = await fetch(`${api}/packets`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}: Failed creating packet`);
      return await res.json();
    },

    async requestUploadUrl(packetId, role, file) {
      if (isMockMode()) {
        return await mockEngine.requestUploadUrl(packetId, role, file);
      }

      const api = getBaseUrl();
      const res = await fetch(`${api}/packets/${packetId}/documents`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          role: role,
          fileName: file.name,
          contentType: file.type || 'application/pdf',
          sizeBytes: file.size
        })
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}: Failed requesting upload URL`);
      return await res.json();
    },

    async uploadFile(uploadUrl, file, onProgress) {
      if (isMockMode()) {
        return await mockEngine.uploadFile(uploadUrl, file, onProgress);
      }

      const res = await fetch(uploadUrl, {
        method: 'PUT',
        headers: { 'Content-Type': file.type || 'application/pdf' },
        body: file
      });
      if (!res.ok) throw new Error(`S3 direct upload failed with status ${res.status}`);
      return { ok: true, status: res.status };
    },

    async markUploaded(packetId, documentId) {
      if (isMockMode()) {
        return await mockEngine.markUploaded(packetId, documentId);
      }

      const api = getBaseUrl();
      const res = await fetch(`${api}/packets/${packetId}/documents/${documentId}/uploaded`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}: Failed starting extraction`);
      return await res.json();
    },

    async runCheck(packetId) {
      if (isMockMode()) {
        return await mockEngine.runCheck(packetId);
      }

      const api = getBaseUrl();
      const res = await fetch(`${api}/packets/${packetId}/check`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}: Failed starting check`);
      return await res.json();
    },

    async getPacket(packetId) {
      if (isMockMode()) {
        return await mockEngine.getPacket(packetId);
      }

      const api = getBaseUrl();
      const res = await fetch(`${api}/packets/${packetId}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}: Failed fetching packet`);
      return await res.json();
    },

    resetSession() {
      if (isMockMode()) {
        mockEngine.reset();
      }
    }
  };

  return API;
});
