# Demo Video Script — Defect Guard Demo Mock Mode

**Target Runtime:** 3 to 4 minutes  
**Mode:** Deterministic Demo Mock Mode (100% offline, zero cloud latency)  
**Scheme:** Mukhya Mantrir Nijut Babu Aasoni (MMNBA 2026-27), Govt of Assam  
**Demo Student:** Antarjit Das (synthetic specimen)  
**Sample Document Location:** `samples/demo-pack/`

---

## Pre-Recording Checklist

1. Start the local server:
   ```bash
   npm run serve
   ```
2. Open `http://localhost:3000` in Google Chrome.
3. Have the 5 synthetic PDFs ready in a convenient folder or use the **"Quick-load Demo Pack"** button.
   - `samples/demo-pack/Aadhar.pdf`
   - `samples/demo-pack/HS Marksheet.pdf`
   - `samples/demo-pack/Income 450k.pdf` (Defective, ₹4.50L)
   - `samples/demo-pack/Bank Statement.pdf`
   - `samples/demo-pack/Income 250k.pdf` (Compliant Replacement, ₹2.50L)

---

## Scene-by-Scene Script

### Scene 1: Landing & Mode Selection (0:00 - 0:35)
* **Visual:** Browser displays the Defect Guard Landing Page.
* **Action:** Hover over the two cards:
  - Highlight the **Live AWS Mode** card: show the badge *"BUILD IN PROGRESS — NOT DEMOABLE"* and explain that AWS cloud integration is undergoing infrastructure validation.
  - Click **"Enter Demo Mode (Hackathon Evaluation)"**.
* **Voiceover:**
  > *"Scholarship applications in India are rejected overwhelmingly due to clerical cross-document discrepancies rather than genuine eligibility issues. Defect Guard is an intelligent pre-flight checker for Assam's Mukhya Mantrir Nijut Babu Aasoni 2026 scheme. We provide a complete, deterministic offline demo mode that lets evaluators review the full product experience without cloud credential barriers."*

---

### Scene 2: Uploading 4 Mandatory Documents (0:35 - 1:15)
* **Visual:** The studio interface opens with 4 document slots.
* **Action:**
  - Click **"Quick-load Demo Pack"** (or drag and drop `Aadhar.pdf`, `HS Marksheet.pdf`, `Income 450k.pdf`, and `Bank Statement.pdf` into their slots).
  - Watch the realistic progress bar transition from `Uploading...` $\rightarrow$ `Processing & Extracting...` $\rightarrow$ `✅ Extracted & Verified`.
* **Voiceover:**
  > *"The student uploads the four mandatory documents: Aadhaar card, HS Marksheet, Circle Officer Income Certificate, and Bank Proof. Defect Guard extracts each document independently, validating check digits and normalizing names and dates."*

---

### Scene 3: Running the Cross-Document Defect Check (1:15 - 2:00)
* **Visual:** All 4 slots show `Extracted & Verified`. The button **"2. Run Defect Check"** is active.
* **Action:** Click **"2. Run Defect Check"**. Watch the status badge change to `CHECKING` for ~1.2 seconds, then transition to `CHECKED`.
* **Voiceover:**
  > *"Once all documents land, we trigger the cross-document check. In less than two seconds, Defect Guard builds a unified Application Snapshot matrix and evaluates 11 deterministic scheme rules."*

---

### Scene 4: Explaining Snapshot, Defects & Score (2:00 - 2:50)
* **Visual:**
  - Focus on **Readiness Score Card**: Shows **40 / 100 [NOT READY]**, Arithmetic: `100 - 25x2 red - 10x1 amber = 40`.
  - Focus on **Application Snapshot Matrix**: Show the highlighted red warning row on **Student Name** (`ANTARJIT DAS` on Aadhaar vs `ANTARJEET DASS` on Marksheet).
  - Focus on **Defect Report**:
    - `[R-01] RED`: Student name mismatch across documents.
    - `[R-07] RED`: Declared annual family income of ₹4,50,000 exceeds the scheme ceiling of ₹4,00,000.
    - `[R-04] AMBER`: Institution enrollment verification (`Cotton University`).
* **Voiceover:**
  > *"The student receives a transparent Application Document Readiness score of 40 out of 100, placing them in the NOT READY band. Every point deduction is mathematically traceable: 25 points per RED defect, 10 points per AMBER warning. In the Snapshot table, we immediately spot the name spelling discrepancy. In the Defect Report, Rule R-07 flags that their declared income of ₹4,50,000 breaches the statutory ₹4.00 Lakh scheme ceiling."*

---

### Scene 5: Document Replacement & Re-Check (2:50 - 3:35)
* **Visual:**
  - Drag and drop `Income 250k.pdf` onto the Income Certificate slot (or click *"🔄 Replace with Compliant Income Cert"*).
  - The dropzone turns green: `✅ Income 250k.pdf (Compliant ₹2.50L — Ready for Re-check)`.
  - The primary action button updates to: **"3. Re-check Application (Updated Documents)"**.
  - Click **"3. Re-check Application"**.
  - Check executes $\rightarrow$ Score dynamically updates from **40 → 65 [RISKY]**!
  - Finding R-07 is resolved and disappears.
* **Voiceover:**
  > *"Instead of waiting weeks for an official portal rejection, the student can fix the defect immediately. They upload their updated, compliant income certificate showing ₹2,50,000. Defect Guard supersedes the old document and enables a instant Re-check. Notice what happens: Rule R-07 completely clears, and the readiness score dynamically jumps from 40 to 65, bringing the application into the manageable RISKY band. The student now knows exactly what to correct before hitting final submit on the state portal."*

---

### Scene 6: Conclusion (3:35 - 3:55)
* **Visual:** Wide view of the verified report and score meter.
* **Voiceover:**
  > *"Defect Guard bridges the gap between student preparation and government scrutiny. Thank you."*
