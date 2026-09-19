// Defect Guard Runtime Configuration

// 1. Live AWS Backend Endpoint (when DEFECT_GUARD_MOCK is false)
window.DEFECT_GUARD_API_URL = "https://6p4hzc5ahf.execute-api.ap-south-1.amazonaws.com/v1";

// 2. Mock Mode Flag
// Set to true for offline evaluation, hackathon judging, and demo recordings.
// Can also be toggled via URL (?mock=1 or ?mock=0) or UI landing cards.
window.DEFECT_GUARD_MOCK = true;

// 3. Centralized Deterministic Timing Configuration (in milliseconds)
// Tuned for natural, believable video recording without wasted wait time.
window.DEFECT_GUARD_TIMINGS = {
  CREATE_PACKET_DELAY: 250,
  UPLOAD_STEP_DELAY: 75,   // ~300ms total upload progress simulation
  EXTRACT_DELAY: 650,      // ~650ms extraction simulation
  CHECK_DELAY: 1200        // ~1.2s rule adjudication and scoring simulation
};
