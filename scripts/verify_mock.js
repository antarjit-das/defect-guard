/**
 * verify_mock.js — Automated Verification Script for Defect Guard Demo Mock Mode
 *
 * Runs headless in Node.js to verify the complete mock state machine,
 * document upload simulations, extraction pipeline, defect checks,
 * replacement logic, and score transitions (40 -> 65).
 */

const assert = require('assert');
const path = require('path');

// Load Mock modules
const types = require('../frontend/lib/types');
const mockData = require('../frontend/lib/mock-data');
const mockEngine = require('../frontend/lib/mock');
const api = require('../frontend/lib/api');

async function runMockVerification() {
  console.log('='.repeat(60));
  console.log('STARTING DEFECT GUARD DEMO MOCK MODE VERIFICATION');
  console.log('='.repeat(60));

  // 1. Ensure mock mode is active
  assert.strictEqual(api.isMockMode(), true, 'API should default to mock mode in Node environment');
  console.log('✔ Test 1: Mock mode active without AWS credentials');

  // 2. Create packet
  api.resetSession();
  const initRes = await api.createPacket();
  assert.strictEqual(initRes.packetId, 'pkt-demo-2026-0918', 'Packet ID must be deterministic');
  assert.strictEqual(initRes.status, types.PacketStatus.DRAFT, 'Initial status must be DRAFT');
  assert.strictEqual(initRes.schemeId, 'NIJUT_BABU_2026', 'Scheme must be NIJUT_BABU_2026');
  console.log('✔ Test 2: Created deterministic mock packet:', initRes.packetId);

  // 3. Simulate Uploads for 4 Mandatory Roles
  const specimenDocs = [
    { role: types.DocumentRole.AADHAAR, name: 'Aadhar.pdf', size: 142331 },
    { role: types.DocumentRole.MARKSHEET, name: 'HS Marksheet.pdf', size: 104929 },
    { role: types.DocumentRole.INCOME_CERTIFICATE, name: 'Income 450k.pdf', size: 133444 },
    { role: types.DocumentRole.BANK_PROOF, name: 'Bank Statement.pdf', size: 97454 }
  ];

  console.log('\nSimulating upload and extraction of 4 mandatory documents...');
  for (const doc of specimenDocs) {
    const uploadMeta = await api.requestUploadUrl(initRes.packetId, doc.role, { name: doc.name, size: doc.size, type: 'application/pdf' });
    assert.ok(uploadMeta.uploadUrl, 'Must return presigned mock upload URL');
    assert.ok(uploadMeta.documentId, 'Must return documentId');

    let progressCalled = false;
    await api.uploadFile(uploadMeta.uploadUrl, { name: doc.name }, (p) => {
      progressCalled = true;
    });
    assert.strictEqual(progressCalled, true, 'Upload progress callback must be triggered');

    const markRes = await api.markUploaded(initRes.packetId, uploadMeta.documentId);
    assert.strictEqual(markRes.status, types.DocumentStatus.EXTRACTING);
    console.log(`  -> [${doc.role}] Uploaded ${doc.name} (documentId: ${uploadMeta.documentId})`);
  }

  // Wait for background extractions to complete (~1.5s)
  console.log('\nWaiting for deterministic extraction pipeline...');
  let packet;
  for (let i = 0; i < 20; i++) {
    await new Promise(r => setTimeout(r, 150));
    packet = await api.getPacket(initRes.packetId);
    if (packet.status === types.PacketStatus.READY_TO_CHECK) break;
  }

  assert.strictEqual(packet.status, types.PacketStatus.READY_TO_CHECK, 'Packet must transition to READY_TO_CHECK');
  assert.strictEqual(packet.documents.length, 4, 'Must contain 4 extracted documents');
  packet.documents.forEach(d => {
    assert.strictEqual(d.status, types.DocumentStatus.EXTRACTED, `Document ${d.role} must be EXTRACTED`);
    assert.ok(d.extraction, `Document ${d.role} must have extraction payload`);
  });
  console.log('✔ Test 3: All 4 documents transitioned to EXTRACTED and packet is READY_TO_CHECK');

  // 4. Run Defect Check (Initial Run)
  console.log('\nTriggering defect check on initial document set...');
  const checkRes = await api.runCheck(initRes.packetId);
  assert.strictEqual(checkRes.status, types.PacketStatus.CHECKING);

  // Wait for check to complete (~1.5s)
  for (let i = 0; i < 20; i++) {
    await new Promise(r => setTimeout(r, 150));
    packet = await api.getPacket(initRes.packetId);
    if (packet.status === types.PacketStatus.CHECKED) break;
  }

  assert.strictEqual(packet.status, types.PacketStatus.CHECKED, 'Packet must transition to CHECKED');
  assert.ok(packet.verdict, 'Packet must contain verdict');
  
  // Verify initial score: 40, band: NOT_READY
  assert.strictEqual(packet.verdict.score, 40, 'Initial score must be 40');
  assert.strictEqual(packet.verdict.band, types.VerdictBand.NOT_READY, 'Initial band must be NOT_READY');
  assert.strictEqual(packet.verdict.scoreArithmetic, '100 - 25x2 red - 10x1 amber = 40');
  assert.strictEqual(packet.previousScore, null, 'Initial previousScore must be null');

  // Verify 3 planted findings
  assert.strictEqual(packet.verdict.findings.length, 3, 'Must contain exactly 3 findings');
  const initialRuleIds = packet.verdict.findings.map(f => f.ruleId);
  assert.ok(initialRuleIds.includes('R-01'), 'Must include R-01 (name mismatch)');
  assert.ok(initialRuleIds.includes('R-07'), 'Must include R-07 (income breach)');
  assert.ok(initialRuleIds.includes('R-04'), 'Must include R-04 (institution verification)');
  console.log('✔ Test 4: Initial check produced score 40 and 3 planted defects (R-01, R-07, R-04)');

  // 5. Replace Income Certificate with Compliant Document (Income 250k.pdf)
  console.log('\nSimulating student replacing defective income certificate with Income 250k.pdf...');
  const replaceUploadMeta = await api.requestUploadUrl(initRes.packetId, types.DocumentRole.INCOME_CERTIFICATE, {
    name: 'Income 250k.pdf',
    size: 133453,
    type: 'application/pdf'
  });

  await api.uploadFile(replaceUploadMeta.uploadUrl, { name: 'Income 250k.pdf' });
  await api.markUploaded(initRes.packetId, replaceUploadMeta.documentId);

  // Wait for replacement extraction
  for (let i = 0; i < 20; i++) {
    await new Promise(r => setTimeout(r, 150));
    packet = await api.getPacket(initRes.packetId);
    const repDoc = packet.documents.find(d => d.documentId === replaceUploadMeta.documentId);
    if (repDoc && repDoc.status === types.DocumentStatus.EXTRACTED) break;
  }

  // Verify superseded linkage
  const oldIncomeDoc = packet.documents.find(d => d.fileName === 'Income 450k.pdf');
  assert.strictEqual(oldIncomeDoc.supersededBy, replaceUploadMeta.documentId, 'Old income doc must be supersededBy replacement doc');
  console.log('✔ Test 5: Replacement income certificate extracted and superseded linkage verified');

  // 6. Run Re-check
  console.log('\nTriggering re-check on updated document pack...');
  await api.runCheck(initRes.packetId);

  for (let i = 0; i < 20; i++) {
    await new Promise(r => setTimeout(r, 150));
    packet = await api.getPacket(initRes.packetId);
    if (packet.status === types.PacketStatus.CHECKED) break;
  }

  // 7. Verify Re-check Verdict & Score Transition (40 -> 65)
  assert.strictEqual(packet.verdict.score, 65, 'Rechecked score must be 65');
  assert.strictEqual(packet.verdict.band, types.VerdictBand.RISKY, 'Rechecked band must be RISKY');
  assert.strictEqual(packet.verdict.scoreArithmetic, '100 - 25x1 red - 10x1 amber = 65');
  assert.strictEqual(packet.previousScore, 40, 'previousScore must record 40');

  const recheckRuleIds = packet.verdict.findings.map(f => f.ruleId);
  assert.strictEqual(recheckRuleIds.includes('R-07'), false, 'R-07 MUST be cleared after replacement');
  assert.ok(recheckRuleIds.includes('R-01'), 'R-01 must remain');
  assert.ok(recheckRuleIds.includes('R-04'), 'R-04 must remain');
  assert.strictEqual(packet.verdict.findings.length, 2, 'Only 2 findings should remain');
  console.log('✔ Test 6: Re-check cleared R-07, score dynamically improved from 40 -> 65 (+25 pts)!');

  // 8. Test Uploading Ineligible 450k Income Certificate (Detect Exceeded Income Ceiling)
  console.log('\nTesting uploading Income 450k.pdf again to verify defect detection...');
  const ineligibleUploadMeta = await api.requestUploadUrl(initRes.packetId, types.DocumentRole.INCOME_CERTIFICATE, {
    name: 'Income 450k.pdf',
    size: 133444,
    type: 'application/pdf'
  });
  await api.uploadFile(ineligibleUploadMeta.uploadUrl, { name: 'Income 450k.pdf' });
  await api.markUploaded(initRes.packetId, ineligibleUploadMeta.documentId);

  for (let i = 0; i < 20; i++) {
    await new Promise(r => setTimeout(r, 150));
    packet = await api.getPacket(initRes.packetId);
    const ineligDoc = packet.documents.find(d => d.documentId === ineligibleUploadMeta.documentId);
    if (ineligDoc && ineligDoc.status === types.DocumentStatus.EXTRACTED) break;
  }

  // Verify extracted document has 450k
  const ineligDoc = packet.documents.find(d => d.documentId === ineligibleUploadMeta.documentId);
  const incField = ineligDoc.extraction.fields.find(f => f.fieldKey === 'annual_income');
  assert.strictEqual(Number(incField.normalizedValue), 450000, 'Income field must extract 450000');
  
  await api.runCheck(initRes.packetId);
  for (let i = 0; i < 20; i++) {
    await new Promise(r => setTimeout(r, 150));
    packet = await api.getPacket(initRes.packetId);
    if (packet.status === types.PacketStatus.CHECKED) break;
  }

  // Must detect R-07 and score must return to 40
  assert.strictEqual(packet.verdict.score, 40, 'Score must return to 40 when 450k income cert is uploaded');
  const defectRuleIds = packet.verdict.findings.map(f => f.ruleId);
  assert.ok(defectRuleIds.includes('R-07'), 'R-07 must be detected when 450k income certificate is uploaded');
  console.log('✔ Test 7: Income 450k.pdf correctly detected as exceeding ₹4.00L ceiling (R-07 triggered, score 40)!');

  // 9. Reset Verification
  api.resetSession();
  const clearedPacket = await api.getPacket(initRes.packetId);
  assert.strictEqual(clearedPacket, null, 'Session must be cleared after reset');
  console.log('✔ Test 8: Reset cleared session cleanly');

  console.log('\n' + '='.repeat(60));
  console.log('ALL MOCK MODE VERIFICATION TESTS PASSED FLAWLESSLY!');
  console.log('='.repeat(60));
}

runMockVerification().catch(err => {
  console.error('\n❌ VERIFICATION FAILURE:', err);
  process.exit(1);
});
