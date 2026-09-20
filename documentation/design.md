# Defect Guard — Design System & Stitch UI/UX Brief

> **Status:** Iteration 01  
> **Purpose:** Visual and UX source of truth for generating the Defect Guard landing page and product frontend in Google Stitch.  
> **Primary references:** [Cluster](https://www.getcluster.ai), [ChatGPT](https://chatgpt.com), and future references added during iteration.  
> **Important:** References are inspiration for visual language and interaction quality, not templates to copy.

---

## 1. Design North Star

Defect Guard should feel like a **serious, quiet, highly polished document utility**.

It should not look like:

- a generic AI SaaS landing page
- a government portal
- a flashy startup dashboard
- a chatbot
- a finance/trading terminal
- an over-designed productivity app
- an “AI magic” product

It should feel like:

- a premium document-review tool
- trustworthy and precise
- editorial and understated
- extremely readable
- calm even when showing defects
- modern without chasing trends
- intelligent without advertising intelligence
- designed around evidence, not decoration

### Core design principle

> **Make a complicated verification process feel simple without hiding the evidence.**

The visual system should communicate:

**upload → understand → inspect → fix → re-check**

with as little cognitive overhead as possible.

---

# 2. Product Context

## Product

**Defect Guard**

## Product description

Defect Guard helps students check scholarship documents before submission.

A student uploads five documents:

1. Aadhaar
2. Caste Certificate
3. Income Certificate
4. Marksheet
5. Bank Proof

The system extracts information, compares the documents, identifies potential defects, explains why they matter, and gives the user concrete fixes.

The central product artifact is:

**Documents → Application Snapshot → Defect Report → Fix List → Re-check**

The product is advisory.

It does **not** submit scholarship applications, guarantee approval, or represent an official government authority.

---

# 3. Inspiration Direction

The current visual references are:

- Cluster — https://www.getcluster.ai
- ChatGPT — https://chatgpt.com

These references should influence the **quality bar**, not produce a visual clone.

## Cluster inspiration

Take inspiration from the following characteristics:

- confident, spacious layouts
- strong typographic hierarchy
- generous whitespace
- restrained visual decoration
- product-led storytelling
- clear CTA hierarchy
- structured sections
- polished product previews
- simple, high-contrast presentation
- a feeling that the software is doing complicated work behind a clean interface

Cluster's public site currently communicates its product through a concise hero, product workflow, visual product demonstrations, case studies, FAQ, and a strong closing CTA. Use this as inspiration for **clarity and pacing**, not literal layout duplication.

## ChatGPT inspiration

Take inspiration from:

- extremely restrained chrome
- clean white/neutral surfaces
- content-first hierarchy
- minimal borders
- compact controls
- simple interaction affordances
- calm empty states
- restrained use of color
- product UI that does not visually compete with the user's task

Do **not** copy ChatGPT's exact interface, branding, icons, navigation, or interaction patterns.

## Overall synthesis

The desired result is:

**Cluster's polished product storytelling + ChatGPT's calm interface discipline + Defect Guard's document/evidence-first identity.**

---

# 4. Brand Personality

Defect Guard is:

- precise
- calm
- trustworthy
- direct
- practical
- human
- editorial
- technically competent
- privacy-conscious

Defect Guard is not:

- loud
- playful
- futuristic
- cyberpunk
- overly corporate
- cartoonish
- “AI-first”
- gamified
- fear-driven

---

# 5. Color System

## Primary background

The default page background should be a **sophisticated warm white**.

Preferred:

```text
Warm White
#FCFBF8
```

Alternative surface:

```text
Soft Paper
#F7F6F2
```

Pure white may be used for elevated product surfaces:

```text
White
#FFFFFF
```

The background should never feel stark or sterile.

---

## Primary text

Use a warm black rather than absolute black.

```text
Warm Black
#171614
```

This is the primary text color.

Secondary text:

```text
Muted Warm Gray
#6F6B64
```

Tertiary text:

```text
Soft Gray
#96918A
```

Borders:

```text
Warm Border
#E6E2DB
```

Very subtle border:

```text
Faint Border
#EEECE7
```

---

## Accent color

The accent system should be restrained.

Use accent color primarily for:

- primary CTA
- active state
- links
- focus states
- selected controls
- key interactive affordances

Default accent:

```text
Deep Ink Blue
#3157D5
```

The blue should never dominate the visual identity.

The interface should remain predominantly warm white + warm black.

---

# 6. Semantic Status Colors

Color must **never be the only indicator** of status.

Every severity/status state must also contain:

- a written label
- an icon where appropriate
- clear supporting text

## RED — Important defect

```text
Text: #9F2F2F
Background: #FFF3F1
Border: #E7B8B2
```

Use for:

- blocking issues
- serious mismatch
- invalid/expired evidence
- critical missing information

Label example:

**RED · Needs attention**

---

## AMBER — Risk / warning

```text
Text: #8A5A14
Background: #FFF8E8
Border: #E8D29E
```

Use for:

- likely issue
- threshold concern
- ambiguous data
- potentially problematic formatting

Label example:

**AMBER · Review**

---

## INFO — Informational

```text
Text: #4B5E72
Background: #F3F6F9
Border: #D3DCE5
```

Use for:

- non-blocking observations
- useful context
- recommendations

Label example:

**INFO · Check**

---

## SUCCESS

Use sparingly.

```text
Text: #276749
Background: #F1F8F3
Border: #BFD9C5
```

Success should communicate completion, not celebration.

Avoid confetti, gradients, glowing green, or gamified success effects.

---

# 7. Typography

## Global rule

**Times New Roman is the default font for everything.**

This is intentional.

The product should have an editorial/documentary quality rather than the standard “modern SaaS sans-serif” appearance.

Use Times New Roman for:

- body copy
- navigation
- headings
- labels
- buttons
- tables
- findings
- metadata
- helper text
- score explanation
- landing-page copy
- footer
- empty states
- error messages

## Product title / wordmark

**Helvetica** is reserved for the product title:

> Defect Guard

Use Helvetica for:

- primary product title
- logo/wordmark treatment
- potentially the large product title in the hero

Do not use Helvetica as a general body font.

---

## Typography hierarchy

### Display

Large landing hero:

- Times New Roman
- large editorial serif treatment
- tight but comfortable line-height
- slightly negative tracking only if it improves rendering
- never excessively heavy

Suggested scale:

```text
Desktop: 72–88px
Tablet: 56–68px
Mobile: 42–52px
```

### Section heading

```text
Desktop: 42–56px
Mobile: 34–40px
```

### Product page heading

```text
32–44px
```

### Body

```text
16–18px
Line-height: 1.5–1.7
```

### Small UI text

```text
12–14px
```

Do not make important information tiny.

---

# 8. Layout Philosophy

The layout should feel **expensive because it is restrained**.

Prefer:

- generous whitespace
- strong alignment
- narrow readable text columns
- clear vertical rhythm
- deliberate grouping
- subtle separators

Avoid:

- excessive cards
- excessive rounded containers
- floating UI everywhere
- dense grids
- decorative blobs
- gradients
- random illustrations
- excessive shadows
- giant iconography

---

# 9. Grid & Spacing

Use a consistent spacing system based around:

```text
4
8
12
16
24
32
40
48
64
80
96
120
```

Landing page content:

```text
Max width: ~1200–1280px
```

Text-heavy sections:

```text
Max readable width: ~720–800px
```

Product interface:

```text
Desktop max width: ~1200–1280px
```

Mobile:

```text
Minimum supported width: 360px
```

There must be **no page-level horizontal scrolling** at 360px.

---

# 10. Shape Language

Use a restrained radius system.

Preferred:

```text
4px
6px
8px
10px
12px
```

Avoid:

- giant pill shapes
- excessively rounded cards
- “bubble UI”
- 24–32px corner radii everywhere

Buttons may use slightly rounded corners but should remain relatively rectangular.

The product should feel like a precise tool rather than a toy.

---

# 11. Borders & Shadows

## Borders

Borders are important.

Use subtle warm-gray borders to create structure.

Preferred:

```text
1px solid #E6E2DB
```

Use stronger borders only when necessary.

## Shadows

Use very little shadow.

Preferred:

```text
0 2px 10px rgba(23, 22, 20, 0.04)
```

Large floating shadows should be avoided.

Most hierarchy should come from:

**spacing + typography + borders + surface color**

rather than shadows.

---

# 12. Landing Page

The landing page should feel editorial, calm, and product-led.

Recommended structure:

1. Navigation
2. Hero
3. Trust / positioning line
4. “Before you submit” problem section
5. How it works
6. Product preview
7. Defect examples
8. Privacy / trust
9. Final CTA
10. Footer

---

# 13. Landing Navigation

Keep navigation extremely simple.

Left:

**Defect Guard**

Right:

- How it works
- Privacy
- Start check →

On smaller screens:

- product title
- compact menu

Do not overpopulate navigation.

No pricing navigation is necessary for the current prototype.

---

# 14. Hero

## Primary headline

> **Check your scholarship documents before you submit.**

Supporting copy:

> Upload your documents, compare the important details, and catch issues before they become submission problems.

Primary CTA:

> **Start check →**

Secondary action may be:

> See how it works

The hero should communicate the product in seconds.

---

## Hero visual

The hero product visual should be a **quiet application snapshot**, not an abstract AI graphic.

Show:

- five document rows
- extracted values
- a small number of statuses
- one or two subtle discrepancies
- a compact readiness indicator

The preview should look like a real useful product.

Avoid:

- floating holograms
- glowing AI interfaces
- robot imagery
- generic dashboard charts
- decorative 3D objects

---

# 15. “Before You Submit” Section

Use this section to establish the problem.

Suggested headline:

> **Small document mistakes can become big submission problems.**

Show examples such as:

- Name mismatch
- Income above the applicable ceiling
- Missing information
- Unsupported file
- Oversized document

Keep examples concrete.

Avoid fear-based copy.

---

# 16. How It Works

Use a simple 3–4 step structure.

### 01 — Upload

Add the five scholarship documents.

### 02 — Review

Defect Guard extracts and compares important information.

### 03 — Fix

Review issues and follow the specific fix instructions.

### 04 — Re-check

Replace a document and run the check again.

This section should visually communicate a process, not a feature list.

---

# 17. Product Preview

The product preview should be one of the strongest visual sections on the landing page.

Show the actual product language:

```text
Application Snapshot
↓
Defect Report
↓
Readiness Score
↓
Fix List
```

The landing page should make the actual product feel tangible.

---

# 18. Start Check Experience

The primary product flow is:

```text
Start
↓
Upload five documents
↓
Extraction
↓
Run check
↓
Application Snapshot
↓
Defect Report
↓
Readiness Score
↓
Fix documents
↓
Re-check
```

The UI must make progress obvious.

---

# 19. Upload Experience

Create five clearly identifiable upload slots.

Required document types:

1. Aadhaar
2. Caste Certificate
3. Income Certificate
4. Marksheet
5. Bank Proof

Each slot should support these states:

- Empty
- Uploading
- Extracting
- Ready
- Extraction failed
- Error with retry

---

## Upload slot visual treatment

The upload component should feel like a document intake tool.

Do not make it look like a giant drag-and-drop marketing box.

Preferred:

- compact document icon
- document title
- short description
- status
- filename when uploaded
- replace/remove action
- progress only when meaningful

Desktop can use a grid/list hybrid.

Mobile should become a clean vertical list.

---

# 20. Upload State Copy

### Empty

**Income Certificate**

Upload your income certificate.

`Choose file`

### Uploading

**Uploading…**

Keep the state visually calm.

### Extracting

**Reading document…**

Do not imply magic.

### Ready

**Income Certificate**

`income_certificate.pdf`

**Ready to check**

### Failed

**Couldn’t read this document**

Try uploading a clearer file.

`Try again`

---

# 21. Extraction Animation

Extraction should be subtle.

Use:

- a restrained progress indicator
- changing status text
- gentle opacity/position transitions

Do not use:

- scanning lasers
- flashy AI animations
- glowing effects
- fake terminal output

The user should feel that the system is working, not performing.

---

# 22. Run Check CTA

Once all required documents are ready:

Primary CTA:

> **Check my application →**

The CTA should be visually prominent but not oversized.

Before all documents are ready:

> **Add remaining documents**

The UI should explain what is missing.

---

# 23. Application Snapshot

This is the **central product artifact**.

It should feel like a document review sheet.

Title:

> **Application Snapshot**

Supporting line:

> The important details we found across your documents.

---

## Snapshot structure

Desktop:

| Field | Aadhaar | Caste | Income | Marksheet | Bank |
|---|---|---|---|---|---|

Rows may include:

- Name
- Date of Birth
- Parent/Guardian Name
- Income
- Category
- Institution
- Account holder
- Other relevant extracted fields

Only show fields relevant to the product.

Do not create a fake data warehouse.

---

# 24. Snapshot Visual Rules

The table should be:

- highly readable
- border-light
- compact but breathable
- aligned
- evidence-focused

When values disagree:

- highlight the disagreement
- show a small status indicator
- explain the issue elsewhere in the defect report

Do not rely on red cell backgrounds everywhere.

---

# 25. Mobile Snapshot

At 360px, do not force the entire table into the viewport.

The snapshot table may scroll **inside its own container**.

The page itself must not horizontally scroll.

Alternative mobile treatment:

```text
Field
Name

Aadhaar
Rahul Kumar

Marksheet
Rahul K.

⚠ Mismatch
```

Use whichever is more readable.

---

# 26. Canonical Value

When multiple documents provide the same field, the interface may show a canonical value.

Example:

```text
Name

Canonical
Rahul Kumar

Found in:
Aadhaar
Income Certificate
Marksheet
```

If there is disagreement, the evidence should remain visible.

Do not hide conflicting values behind an AI-generated summary.

---

# 27. Defect Report

Title:

> **Defect Report**

Supporting line:

> Issues worth fixing before you submit.

Findings should be ordered by severity.

Primary hierarchy:

**Severity → Problem → Evidence → Fix → Rule/source**

---

# 28. Finding Card

Each finding card should include:

### Severity

Examples:

**RED · Needs attention**

**AMBER · Review**

**INFO · Check**

### Problem

Short, concrete statement.

Example:

> Your name is written differently across two documents.

### Evidence

Example:

```text
Aadhaar
Rahul Kumar

Marksheet
Rahul K.
```

### Why it matters

One concise explanation.

### Fix

Concrete action.

Example:

> Replace or correct the document so the name matches the canonical spelling.

### Rule / source

If applicable, show the relevant rule or source in small text.

---

# 29. Finding Card Visual Hierarchy

Do not make finding cards giant colorful alert boxes.

Preferred structure:

```text
[RED] Needs attention

Name mismatch
────────────────────────

Aadhaar
Rahul Kumar

Marksheet
Rahul K.

Why this matters
The application may require consistent identity details.

Fix
Use the same full name across the relevant documents.

Rule / source
...
```

Severity should be visible immediately.

---

# 30. Example Demo Findings

The canonical demo should contain three planted findings:

### Finding 1

**Name mismatch**

Example:

```text
Aadhaar: Rahul Kumar
Marksheet: Rahul K.
```

### Finding 2

**Income exceeds the applicable ceiling**

Demo value:

```text
₹2.6 lakh
```

Example ceiling:

```text
₹2.5 lakh
```

This should be shown as an example/demo rule, not as a universal claim for every scholarship.

### Finding 3

**File is too large**

Show the actual file-size issue clearly.

---

# 31. Readiness Score

The score should support the findings.

It should **not dominate the interface**.

Example:

```text
Readiness

40 / 100

RISKY
```

Then show arithmetic/evidence.

Example:

```text
Starting score                 100
Name mismatch                  -25
Income threshold issue         -25
File-size issue                -10
────────────────────────────────
Readiness                       40
```

The score is explanatory, not gamified.

---

# 32. Score Bands

Use:

```text
0–49     NOT READY
50–79    RISKY
80–100   READY
```

These labels should be treated as product-state language, not an official scholarship authority classification.

---

# 33. Score Advisory

Place an advisory statement near the score:

> **This is a document-readiness check, not an approval prediction.**

Do not bury this clarification.

---

# 34. Re-check Experience

When a user replaces a problematic document:

1. Show the replacement
2. Show extraction again
3. Allow re-check
4. Re-run relevant checks
5. Show what changed

The key interaction should communicate progress.

Example:

```text
Before

40 / 100

↓

Income certificate replaced

↓

Re-checking…

↓

After

50 / 100

1 issue fixed
```

Do not use confetti.

A quiet confirmation is more appropriate.

---

# 35. Fix List

Provide a concise action list.

Example:

```text
Fix before submitting

1. Replace the income certificate
2. Make the name consistent across documents
3. Upload a smaller file
```

Each action may link back to the relevant document.

Primary action:

> **Fix this →**

---

# 36. Empty States

Empty states should be helpful, not decorative.

Example:

> **No documents yet**
>
> Add your five scholarship documents to start the check.

CTA:

> **Start uploading →**

---

# 37. Loading States

Loading states should explain what is happening.

Prefer:

> Reading your documents…

> Comparing important details…

> Checking for mismatches…

Avoid:

> AI is thinking…

> Magic is happening…

> Our neural engine is working…

---

# 38. Error States

Errors should always tell the user what to do next.

Structure:

```text
Something went wrong.

We couldn't finish checking your documents.

Try again.
```

If only one document failed:

```text
We couldn't read the income certificate.

Try uploading a clearer PDF or image.
```

Always provide a retry/replacement path.

---

# 39. Privacy / Trust Section

The privacy section should be calm and factual.

Key points:

- Documents are used for the check.
- Aadhaar numbers and bank/account numbers should be masked in the interface.
- Documents are automatically deleted after 24 hours.
- Defect Guard does not submit the application to NSP.
- Demo data is synthetic.

Avoid exaggerated privacy claims.

Do not use “military-grade security” or similar marketing language unless explicitly verified.

---

# 40. Document Masking

Sensitive identifiers should never be unnecessarily exposed.

Example:

```text
Aadhaar
XXXX XXXX 4821
```

Account number:

```text
••••••4821
```

Use the same masking principle throughout the product.

---

# 41. Demo Documents

The prototype should use synthetic documents/data.

Never imply that demo documents are real government records.

The UI can label examples:

```text
DEMO DOCUMENT
```

Use realistic structure but fictional identities.

---

# 42. Responsive Design

The design must work from:

```text
360px
```

upwards.

## Mobile principles

On mobile:

- stack sections vertically
- reduce decorative whitespace
- preserve generous internal spacing
- keep buttons easy to tap
- make primary actions full-width where useful
- allow tables to scroll inside their own containers
- avoid tiny typography
- preserve severity labels
- keep evidence readable

## Desktop principles

Desktop can use:

- two-column sections
- wider product previews
- larger snapshot tables
- side-by-side score/findings where appropriate

Do not create separate visual languages for desktop and mobile.

---

# 43. Navigation in Product

The product experience should have minimal navigation.

Possible product header:

```text
Defect Guard

Application
Privacy

[Start check]
```

If the current flow is a single-session public demo, avoid unnecessary dashboard navigation.

---

# 44. Buttons

Primary button:

- warm black or restrained deep ink
- white text
- compact
- clear
- slightly rounded

Example:

**Start check →**

Secondary button:

- transparent / warm-white
- warm-black text
- subtle border

Example:

**See how it works**

Tertiary:

- text link
- minimal decoration

Avoid giant pill buttons.

---

# 45. Icons

Use icons sparingly.

Icons should clarify:

- upload
- file
- warning
- information
- check
- retry
- arrow
- privacy

Do not use icons as decoration.

Use a consistent simple line-icon language.

---

# 46. Motion

Motion should be subtle and purposeful.

Use motion for:

- page transitions
- upload progress
- extraction state
- expanding evidence
- re-check state
- score update

Suggested timing:

```text
150–250ms
```

Use ease-out style transitions.

Avoid:

- bounce
- spring-heavy UI
- exaggerated scale
- parallax
- continuous animation
- decorative motion

---

# 47. Accessibility

Accessibility is part of the design.

Requirements:

- keyboard accessible controls
- visible focus states
- sufficient text contrast
- status conveyed by text + color
- buttons with clear labels
- inputs with labels
- no hover-only critical information
- touch targets suitable for mobile
- reduced-motion support

---

# 48. Component Language

The frontend should use a small, coherent component vocabulary.

Core components:

```text
Header
Hero
PrimaryButton
SecondaryButton
UploadSlot
UploadProgress
ExtractionState
DocumentStatus
SnapshotTable
SnapshotCell
FindingCard
SeverityBadge
EvidenceBlock
ReadinessScore
ScoreBreakdown
FixList
FixListItem
RecheckBanner
PrivacyNote
EmptyState
ErrorState
Footer
```

Components should feel like parts of the same product.

Avoid building every section as a visually unique component.

---

# 49. Landing Page Visual Rhythm

The landing page should alternate between:

**large editorial statement**

and

**concrete product evidence**

For example:

```text
Headline
↓
Whitespace
↓
Product preview
↓
Problem statement
↓
Evidence examples
↓
How it works
↓
Product preview
↓
Trust
↓
CTA
```

Do not create a page where every section is just:

```text
Icon
Heading
Paragraph
Card
```

That pattern is too generic.

---

# 50. Copy Style

Copy should be:

- short
- human
- direct
- concrete
- calm
- useful

Prefer:

> Check your scholarship documents before you submit.

Over:

> Harness the power of intelligent AI to revolutionize your scholarship application workflow.

Prefer:

> Your name is different across two documents.

Over:

> We detected a potentially significant identity inconsistency.

Prefer:

> Replace the income certificate and run the check again.

Over:

> Take corrective action to optimize your application readiness score.

---

# 51. Language to Avoid

Avoid marketing language such as:

- AI-powered
- revolutionary
- next-generation
- intelligent automation
- cutting-edge
- seamless
- frictionless
- magic
- supercharge
- unlock
- transform
- game-changing
- powered by advanced AI

The product can be technically sophisticated without saying so.

---

# 52. Landing Page CTA Language

Preferred:

**Start check →**

Secondary:

**See how it works**

After upload:

**Check my application →**

After an issue:

**Fix this →**

After replacement:

**Re-check →**

Avoid:

- Get started with AI
- Analyze now
- Generate insights
- Optimize my application

---

# 53. Trust Language

Use factual statements.

Examples:

> Your documents are automatically deleted after 24 hours.

> Aadhaar and account numbers are masked in the interface.

> Defect Guard does not submit your scholarship application.

> This check is advisory and does not guarantee approval.

---

# 54. Design Tokens

Use these as the initial design foundation.

```css
--background: #FCFBF8;
--surface: #FFFFFF;
--surface-muted: #F7F6F2;

--text-primary: #171614;
--text-secondary: #6F6B64;
--text-tertiary: #96918A;

--border: #E6E2DB;
--border-subtle: #EEECE7;

--accent: #3157D5;

--danger-text: #9F2F2F;
--danger-bg: #FFF3F1;
--danger-border: #E7B8B2;

--warning-text: #8A5A14;
--warning-bg: #FFF8E8;
--warning-border: #E8D29E;

--info-text: #4B5E72;
--info-bg: #F3F6F9;
--info-border: #D3DCE5;

--success-text: #276749;
--success-bg: #F1F8F3;
--success-border: #BFD9C5;

--font-body: "Times New Roman", Times, serif;
--font-product-title: Helvetica, Arial, sans-serif;

--radius-sm: 4px;
--radius-md: 8px;
--radius-lg: 12px;

--shadow-subtle: 0 2px 10px rgba(23, 22, 20, 0.04);
```

---

# 55. Stitch Instructions

This section is specifically for Google Stitch.

## Stitch should treat this document as the visual/UX source of truth.

The product requirements in `PROJECT.md` and `IMPLEMENTATION.md` remain the source of truth for functionality and implementation constraints.

Stitch should **synthesize** the design rather than reproduce any reference website.

### Important

Do not copy:

- Cluster's exact page layout
- ChatGPT's exact navigation
- ChatGPT's branding
- ChatGPT's icons
- Cluster's illustrations
- Cluster's wording
- proprietary visual details

Instead, combine the underlying qualities:

**editorial restraint + premium whitespace + calm software UI + evidence-first document review**

---

# 56. Stitch Visual Priority

If there is a conflict, prioritize in this order:

1. Readability
2. Product clarity
3. Evidence hierarchy
4. Trust
5. Accessibility
6. Responsive behavior
7. Visual sophistication
8. Decorative detail

Never sacrifice clarity for aesthetics.

---

# 57. Stitch Must Not Invent

Do not invent:

- additional product features
- accounts/authentication
- payments
- dashboards unrelated to the core flow
- AI chat
- document submission
- government affiliation
- approval prediction
- unsupported scholarship rules
- extra document types
- fake statistics
- testimonials presented as real
- security certifications
- official government branding

If something is not defined in the project materials, keep it visually neutral or omit it.

---

# 58. Stitch Should Build

At minimum, create:

## Landing page

- Header
- Hero
- Primary CTA
- Problem section
- How it works
- Product preview
- Defect examples
- Privacy/trust
- Final CTA
- Footer

## Product flow

- Start check
- Upload five documents
- Extraction state
- Ready state
- Check CTA
- Application Snapshot
- Defect Report
- Readiness Score
- Fix List
- Re-check state
- Updated score

## State coverage

Include designs for:

- empty
- uploading
- extracting
- extraction failed
- ready
- checking
- checked
- error
- re-checking
- issue fixed

---

# 59. Primary Demo Narrative

The UI should support this exact demo story:

1. User opens Defect Guard.
2. User sees a calm landing page.
3. User clicks **Start check →**.
4. User uploads five documents.
5. Documents move through extraction.
6. User clicks **Check my application →**.
7. Application Snapshot appears.
8. Three planted findings appear:
   - name mismatch
   - income ₹2.6 lakh vs example ₹2.5 lakh ceiling
   - oversized file
9. Readiness score is:

```text
40 / 100
RISKY
```

10. User replaces the income certificate.
11. User re-checks.
12. Score changes:

```text
40 → 50
```

13. UI says:

> **1 issue fixed**

This sequence should be visually obvious.

---

# 60. Product Page Information Architecture

Recommended desktop structure:

```text
┌──────────────────────────────────────────────┐
│ Header                                       │
├──────────────────────────────────────────────┤
│ Application Snapshot                         │
│                                              │
│ Document comparison / extracted values       │
├──────────────────────────────────────────────┤
│ Defect Report                                │
│                                              │
│ Finding 1                                    │
│ Finding 2                                    │
│ Finding 3                                    │
├───────────────────────────┬──────────────────┤
│ Fix List                  │ Readiness Score  │
│                           │                  │
│ Action 1                  │ 40 / 100        │
│ Action 2                  │ RISKY            │
│ Action 3                  │ breakdown        │
└───────────────────────────┴──────────────────┘
```

Mobile:

```text
Header
↓
Application Snapshot
↓
Defect Report
↓
Readiness Score
↓
Fix List
↓
Re-check
```

---

# 61. Visual Density

The product should have **medium information density**.

Do not make it feel empty just because the visual style is minimalist.

The user needs to see:

- what was uploaded
- what was extracted
- what is wrong
- why it matters
- what to fix
- what changed

Minimalism means removing unnecessary decoration, not removing useful information.

---

# 62. Evidence Over Decoration

Whenever there is a choice between:

**another visual element**

and

**more useful evidence**

choose the evidence.

The interface should feel trustworthy because the user can understand why a finding exists.

---

# 63. Responsive Priority

At 360px, preserve these above everything:

1. Current document status
2. Primary CTA
3. Finding severity
4. Finding explanation
5. Evidence
6. Fix action
7. Score
8. Privacy/advisory information

Decorative visuals may be reduced or removed on mobile.

---

# 64. Final Art Direction

The finished product should feel like:

> **A beautifully typeset document-review instrument living inside a modern web application.**

The visual impression should be:

**warm white paper + warm black typography + subtle borders + editorial Times New Roman + Helvetica product title + restrained ink-blue interaction color + precise document UI.**

The product should feel sophisticated without looking expensive for the sake of looking expensive.

It should feel calm when the user is anxious.

It should make errors understandable rather than alarming.

It should make the next action obvious.

---

# 65. Final Principle

> **Defect Guard is not trying to impress the user with software.**
>
> **It is trying to help the user trust what they are seeing.**

Every visual decision should support that.

---

## Iteration Notes

This document is intentionally a **strong first visual direction**, not a frozen design system.

Future iterations should refine:

- exact typography sizes
- spacing
- button geometry
- landing-page composition
- snapshot table treatment
- mobile interaction patterns
- score presentation
- severity styling
- upload component
- motion
- iconography
- exact accent color
- Stitch-generated screens

When new references are added, extract their **design principles** rather than copying their UI literally.

