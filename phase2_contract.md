# BrandGuard Phase 2: API Contract

This is the single source for request and response shapes in phase 2. The frontend types live in `frontend/src/api/submissions.ts`. The backend Pydantic models must match this document exactly. If anything here changes, change this document first and tell everyone.

Conventions match phase 1: camelCase in JSON, errors as `{"detail": "..."}`, ids as text (`ATT-0001`), timestamps in ISO 8601 UTC.

## 1. Submission

A submission is a `content` row with a `kind`. Existing content endpoints still work for text posts.

```json
{
  "id": "CNT-0142",
  "title": "Summer SPF launch script",
  "kind": "script",
  "channel": "General",
  "team": "Marketing",
  "status": "Draft",
  "bodyText": "Hook: Protect your skin all day...",
  "ownerId": "user-creator",
  "ownerName": "Sam Creator",
  "readSummary": {
    "attachments": 2,
    "pending": 0,
    "reading": 0,
    "ready": 1,
    "held": 1,
    "failed": 0,
    "partial": 0
  },
  "hold": null,
  "createdAt": "2026-11-02T09:14:00Z",
  "updatedAt": "2026-11-02T09:20:00Z"
}
```

`kind` is one of `post`, `script`, `marketing_idea`, `design`, `image`.
`channel` is one of `Website`, `Instagram`, `Email`, `Ad`, `General`.
`status` uses the existing workflow values unchanged.

`hold` is `null` unless an attachment is held. When it is set, it is exactly:

```json
{
  "reason": "confidential_term",
  "routedTo": "manager",
  "message": "This file was held for manager review because it may contain internal information. A manager will contact you."
}
```

For creators and reviewers, `hold` never includes the term or the term list. For managers and admins, the same shape is returned, and no term text is added in phase 2.

## 2. Attachment

```json
{
  "id": "ATT-0007",
  "contentId": "CNT-0142",
  "filename": "spf_banner_v3.png",
  "mimeType": "image/png",
  "kind": "image",
  "sizeBytes": 412300,
  "sha256": "9f2c...e41a",
  "pageCount": 1,
  "readStatus": "ready",
  "readMessage": "",
  "uploadedBy": "Sam Creator",
  "uploadedAt": "2026-11-02T09:15:10Z"
}
```

`kind` is one of `image`, `pdf`, `docx`, `text`.
`readStatus` is one of `pending`, `reading`, `ready`, `held`, `failed`, `partial`.
`readMessage` is empty unless the status is `failed`, `partial`, or `held`. For `held`, the message is the same warning text as in `hold.message`. It never contains the term.

The attachment list never includes `extractedText`, `visualFacts`, or the file bytes. Those are internal.

## 3. Findings

Phase 2 reuses the existing `Finding` type in `frontend/src/types/index.ts` unchanged, and the existing endpoint `GET /api/content/{id}/findings`. Field rules for phase 2:

| Field | Text finding | Visual finding | Confidential finding |
|---|---|---|---|
| `type` | `claim`, `tone`, `rule` | `image` | `security` |
| `start`, `end` | set | `null` | `null` |
| `bbox` | `null` | `[x, y, w, h]`, each 0 to 1, or `null` for a whole-image finding | `null` |
| `severity` | as today | as today | `critical` |
| `sourceId` | guideline id | guideline id | `"confidential-terms"` |
| `sourceVersion` | guideline version | guideline version | `1` |
| `originalText` | quoted text | `""` | `""` |
| `needsHumanReview` | as today | always `true` | always `true` |
| `aiGenerated` | `true` | `true` | `false` |
| `title` | short label | short label | "Confidential term detected" |
| `reason` | explanation | explanation | "This file may contain internal information. A manager will review it." |

The confidential finding never stores the term itself.

## 4. Endpoints

All endpoints need a logged-in user. Errors use `{"detail": "..."}`.

### 4.1 Create a submission

`POST /api/submissions` · roles: creator, manager, admin

Request:

```json
{ "title": "Summer SPF launch script", "kind": "script", "team": "Marketing", "channel": "General", "bodyText": "" }
```

Response `201`: a submission object (section 1).

Errors: `422` for an unknown kind, team, or channel, or an empty title.

### 4.2 Get a submission

`GET /api/submissions/{id}` · roles: owner, reviewer, manager, admin

Response `200`: a submission object. `404` if not found or not visible to the caller.

### 4.3 Upload an attachment

`POST /api/submissions/{id}/attachments` · roles: owner, manager, admin
Content type: `multipart/form-data`, field name `file`.

Response `201`: an attachment object with `readStatus: "pending"`.

If the same file (same SHA-256) is already attached to this submission, response `200` with the existing attachment.

| Status | When |
|---|---|
| 415 | Extension is not `.png`, `.jpg`, `.jpeg`, `.pdf`, `.docx`, or `.txt` |
| 413 | Larger than 10 MB |
| 409 | Already 10 attachments on this submission |
| 422 | File is empty |
| 404 | Submission not found or not visible |

### 4.4 List attachments

`GET /api/submissions/{id}/attachments` · roles: owner, reviewer, manager, admin

Response `200`: an array of attachment objects, oldest first, excluding deleted ones.

### 4.5 Delete an attachment

`DELETE /api/submissions/{id}/attachments/{attachmentId}` · roles: owner, manager, admin

Response `204`. Soft delete. `404` if not found.

### 4.6 Submit for checking

`POST /api/submissions/{id}/submit` · roles: owner, manager, admin

Starts the reading pipeline in the background.

Response `202`:

```json
{ "submissionId": "CNT-0142", "checkRunId": "CR-0093", "queued": 2 }
```

| Status | When |
|---|---|
| 409 | No attachments and no body text |
| 409 | Already being checked (a check is running) |

Results appear through the existing findings endpoint and the attachment list. The frontend polls the attachment list while any attachment is `reading` or `pending`.

### 4.7 Findings

`GET /api/content/{id}/findings` · unchanged from phase 1. Returns `Finding[]`.

## 5. Roles

| Action | Creator | Reviewer | Manager | Admin |
|---|---|---|---|---|
| Create submission | yes | no | yes | yes |
| Upload, delete attachment | own only | no | yes | yes |
| Submit for checking | own only | no | yes | yes |
| See submission and attachments | own only | yes | yes | yes |
| See findings | own only | yes | yes | yes |
| See held reason text | warning only | no | yes | yes |

"Own only" means `ownerId` is the caller.

## 6. Internal only (not returned by the API)

These are used by the backend and never sent to the frontend.

Vision model output, one JSON object per call:

```json
{
  "facts": [
    { "id": "F1", "kind": "text", "value": "SPF 50", "bbox": [0.1, 0.2, 0.3, 0.05], "confidence": 0.92 }
  ],
  "findings": [
    { "factIds": ["F1"], "type": "claim", "severity": "critical", "title": "Absolute protection claim",
      "quote": "Protect your skin all day", "reason": "...", "guidelineId": "G-012",
      "suggestedFix": "...", "confidence": 0.8 }
  ],
  "notFound": []
}
```

Fact `kind`: `text`, `logo`, `product`, `person`, `colour`, `layout`, `other`.

Finding `quote`: required for text types (`claim`, `disclaimer`, `tone`, `terminology`). It must appear exactly in the extracted text, or the finding is dropped. Visual types do not need a quote.

Finding `type` from the model is mapped to the stored type as follows (this mapping is fixed in `backend/app/services/vision_safeguards.py`):

| Model type | Stored type |
|---|---|
| `claim` | `claim` |
| `disclaimer` | `claim` |
| `tone` | `tone` |
| `terminology` | `rule` |
| `visual` | `image` |
| `accessibility` | `accessibility` |

## 7. Safeguard thresholds

Proposed values, shared by the backend and the tests:

| Name | Value | Meaning |
|---|---|---|
| `MIN_CONFIDENCE` | 0.30 | Findings below this are dropped |
| `REVIEW_BELOW` | 0.60 | Findings below this are saved as suggestions (`needsHumanReview = true`) |
| `MAX_CALLS_PER_SUBMISSION` | 10 | Model calls before the submission is marked `partial` |

## 8. Mock data

`frontend/src/mocks/submissions.ts` contains one submission, two attachments (one ready, one held), and three findings (one text, one visual, one confidential). The frontend uses these until the API is merged. Switch imports to `api/submissions.ts` functions when the backend is ready.

## 9. Versioning

Phase 2 contract version: 1. Any change that removes or renames a field bumps the version and is announced to the team before merging.
