# Build BGT Studio — Brand Governance Technology

Act as a senior full-stack developer, UI/UX designer, and product architect. Build a complete, functional MVP website called **BGT Studio (Brand Governance Technology)** from scratch.

The project is for **Team Optimus Prime**.

Your goal is to create a modern, professional, simple, intuitive, and interactive SaaS application that looks like a carefully designed real product—not a generic AI-generated dashboard.

Do not just explain how to build it. Actually create the project files, implement the frontend and backend, connect the APIs and database, and make the application runnable.

---

## 1. Product overview

BGT helps content creators check whether their content follows their company's brand guidelines before publishing.

Companies often store their brand rules in PDFs, presentations, documents, folders, and employees' memories. This leads to:

- Inconsistent brand tone.
- Use of outdated or unapproved terminology.
- Unsupported product claims.
- Repeated manual checking.
- Delays in content approval.

BGT provides one central place to store brand rules, check draft content, explain possible issues, and help human reviewers make decisions.

**Important principle:** BGT should assist human reviewers, not replace them. A flagged phrase is a prompt for review, not automatic proof of a violation.

## 2. Technology stack

Use this stack unless there is a strong technical reason not to:

Frontend:
- HTML5
- CSS3
- Vanilla JavaScript
- Responsive layouts

Backend:
- Python
- FastAPI
- REST APIs

Database:
- SQLite for the MVP

Document processing:
- PyMuPDF for PDF extraction
- python-docx for DOCX extraction

Compliance engine:
- Python-based deterministic rule checks
- Optional LLM integration for tone review, only if configured securely

Development:
- VS Code
- Git and GitHub

Keep the architecture simple and suitable for a one-day hackathon MVP.

## 3. Design direction

Create a premium, restrained, modern B2B SaaS design.

The website should feel like a real product designed by a professional product design team.

Visual direction:
- Warm off-white background: #F7F8F5
- Deep navy: #18334A
- White surfaces
- Muted green for approved or positive states
- Muted amber for warnings
- Muted red for important issues
- Thin, subtle borders
- Consistent spacing
- Soft, restrained shadows
- Rounded corners, but not excessive
- Excellent typography using DM Sans or Manrope

Design principles:
- Minimal and clean.
- Strong visual hierarchy.
- Readable typography.
- Spacious layouts.
- Consistent buttons and form fields.
- Purposeful micro-interactions.
- Smooth but subtle transitions.
- Responsive on desktop, tablet, and mobile.
- Accessible color contrast and keyboard interaction.

Avoid:
- Purple gradients.
- Excessive gradients.
- Glassmorphism.
- Floating glowing cards.
- Random decorative blobs.
- Excessive rounded pills.
- Fake analytics.
- Unnecessary charts.
- AI sparkles everywhere.
- Generic template-style dashboards.
- Excessive animations.

Do not sacrifice usability for visual effects.

## 4. Application navigation

Create a fixed sidebar containing:

1. Overview
2. Brand Guidelines
3. New Review
4. Review History

Include:
- BGT logo and product name.
- Workspace selector.
- User profile area.
- Help or quick-guide link.

The main content area should have a top navigation bar with breadcrumbs and a small workspace status indicator.

## 5. Dashboard

Create an overview dashboard with:

- Welcome heading.
- Start a Review button.
- Reviews This Month metric.
- Awaiting Review metric.
- Brand Guidelines metric.
- Recent Reviews section.
- Quick Start section.

The dashboard must display real information retrieved from the backend.

Do not use fake analytics or hardcoded activity after the application starts.

For an empty database, display a thoughtful empty state with a clear call to action.

## 6. Brand Guidelines

Create a functional brand knowledge management page.

Users must be able to add, edit, and save:

### Brand profile
- Brand name.
- Brand voice.
- Tone characteristics.

### Restricted terms
Words and phrases that should be flagged.

### Preferred terms
Words and phrases that should be recommended where appropriate.

### Verified product facts
Store:
- Product name.
- Approved fact.
- Numeric value where applicable.
- Unit where applicable.

All information must be saved in SQLite and loaded again when the page is reopened.

Provide:
- Add fact.
- Edit fact.
- Delete fact.
- Save changes.
- Success and error feedback.

## 7. New Review

Create a content submission page with two modes:

### Mode A: Paste text
- Large text editor.
- Word count.
- Character count.
- Clear button.
- Run Brand Check button.

### Mode B: Upload document
Support:
- PDF.
- DOCX.

Show:
- File name.
- File size.
- Upload progress or processing state.
- Validation errors.

Extract document text using the appropriate Python library.

Reject unsupported file formats and oversized uploads with understandable error messages.

## 8. Brand compliance engine

When a user submits a draft, send the content to the backend for checking.

Implement these checks:

### A. Restricted term detection
Find exact or case-insensitive occurrences of restricted phrases.

Show:
- Matched phrase.
- Location in the draft.
- Relevant brand rule.
- Explanation.

### B. Preferred term suggestions
Check whether preferred terminology is used.

If a relevant preferred term is missing, provide a suggestion.

Do not claim that every missing preferred term is a violation.

### C. Product fact verification
Compare numeric claims in the draft against verified product facts.

For example:

Approved fact:
AURA Energy contains 80mg caffeine per serving.

Draft:
AURA Energy contains 100mg caffeine per serving.

Finding:
The draft contains a numeric claim that conflicts with the saved product fact.

Show the draft claim and the approved fact as evidence.

Avoid claiming to understand product context when the simple rule engine cannot reliably establish it.

### D. Tone review
Provide basic tone prompts using transparent heuristics.

If an LLM is configured, it may provide additional tone analysis based on the saved brand voice.

LLM findings must be clearly distinguished from deterministic rule matches.

Never expose API keys in frontend code.

## 9. Review results page

Create a clear review report.

Include:

- Review title.
- Date and time.
- Number of findings.
- Findings needing attention.
- Suggestions.
- Checks passed.
- Review status.

Each finding should show:
- Finding title.
- Severity.
- Matched text, when available.
- Explanation.
- Supporting evidence.
- Relevant brand guideline.
- Suggested correction.

Clicking a finding should open its details.

Allow users to:
- Inspect evidence.
- Edit a suggested correction.
- Copy a suggestion.
- Dismiss a finding.

Use clear visual states for:
- Needs attention.
- Suggestion.
- Informational prompt.

Do not make findings look like confirmed legal or compliance violations.

## 10. Human review

Create a human decision section with:

- Approve Review.
- Request Changes.
- Dismiss or resolve findings where appropriate.

Save the review decision to SQLite.

The final decision always belongs to the human reviewer.

Do not automatically approve content just because no issues were found.

## 11. Review history

Create a history page showing saved reviews.

Display:
- Review title.
- Source file or pasted text.
- Date.
- Finding count.
- Review status.

Allow users to open an earlier review and inspect its findings and decision.

Store review records persistently in SQLite.

## 12. Database design

Create suitable SQLite tables for:

- Brand settings.
- Restricted terms and preferred terms, or an equivalent structured settings model.
- Product facts.
- Reviews.
- Review findings.
- Human review decisions.

Use appropriate relationships and timestamps.

Do not store important application state only in browser memory.

## 13. API endpoints

Implement clean REST endpoints, including:

- GET /api/brand-rules
- PUT /api/brand-rules
- POST /api/reviews
- GET /api/reviews
- GET /api/reviews/{id}
- PATCH /api/reviews/{id}
- GET /api/health

Add input validation and useful error responses.

## 14. Demo brand data

Use this fictional brand for the initial demonstration:

Brand: AURA Beverages

Brand voice:
- Friendly
- Confident
- Clear

Restricted terms:
- Guaranteed results
- Cures fatigue

Preferred term:
- Refreshing drink

Verified facts:
- AURA Energy: 80mg caffeine per serving.
- AURA Energy: 250ml per can.
- AURA Zero: zero added sugar.

Create a sample draft:

"AURA Energy has 100mg caffeine per can and guaranteed results that cure fatigue all day. Try it NOW for an AMAZING boost!"

The review should flag:
- The restricted phrase "guaranteed results".
- The restricted phrase "cure fatigue" or the relevant matching restricted phrase, according to the exact configured wording.
- The conflicting caffeine quantity.
- A possible tone concern about excessive capitalization.

Explain every finding using the saved brand rules or clearly identified heuristic.

## 15. Project structure

Use a clean project structure similar to:

bgt-studio/
  backend/
    main.py
    database.py
    models.py
    schemas.py
    compliance.py
    document_parser.py
    requirements.txt
  frontend/
    index.html
    styles.css
    app.js
  README.md
  .gitignore

You may adjust the structure if it improves maintainability.

## 16. Quality requirements

The application must:

- Run locally without complicated setup.
- Have working navigation.
- Have working buttons.
- Have connected frontend and backend.
- Persist data in SQLite.
- Validate user inputs.
- Display useful loading and error states.
- Support PDF and DOCX extraction.
- Work on mobile and desktop.
- Avoid broken links and dead controls.
- Contain no fake functionality.
- Avoid placeholder sections that pretend to be implemented.

Test the complete workflow:
1. Open the dashboard.
2. Edit brand guidelines.
3. Save them.
4. Create a review using pasted text.
5. Create a review using a PDF or DOCX.
6. Inspect findings and evidence.
7. Edit or dismiss a suggestion.
8. Approve a review or request changes.
9. Open review history.
10. Reopen a previous review.

Fix any errors discovered during testing.

## 17. Final deliverables

Provide:

1. Complete working source code.
2. All required project files.
3. requirements.txt.
4. README with setup instructions.
5. Database initialization.
6. Demo brand data.
7. Local run commands.
8. Clear explanation of implemented features and known limitations.

Do not stop after creating a visual mockup.

Do not return only code snippets.

Build the complete working MVP, run it, test it, and improve the UI until it feels polished and production-inspired.

**Final product goal:** BGT should feel like a simple, trustworthy, modern brand governance tool that a real marketing team could understand and use immediately.