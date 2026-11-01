# BrandGuard Phase 2: Team Runbook

For everyone working on phase 2. Read this before you start, and keep it up to date when something changes.

## 1. What phase 2 does

Creators can submit scripts, marketing ideas, product designs, and images, not only text posts. The system:

1. Checks every submission for confidential terms before any AI call. A match holds the submission and routes it to a manager.
2. Reads text with the existing text checks, and reads images and scanned PDF pages with OCR and a vision model.
3. Compares what it reads with the brand guidelines, and lists findings. Findings are suggestions. Nothing is blocked automatically.

Video and audio are out of scope.

## 2. Where things are

Everything for phase 2 lives in the `phase2` branch, `feature/phase2-start`. The planning documents are in `docs/` and `phase2_contract.md`.

| Area | File | Purpose |
|---|---|---|
| Contract | `phase2_contract.md` | Request and response shapes. The single source for the API. |
| Plan | `BrandGuard_Phase2_Plan_Rev1.pdf` | Decisions, pipeline, work split, tests. |
| Upload rules | `backend/app/services/attachments.py` | Allowed types, size, file count, page limit, safe names, duplicate detection. |
| OCR | `backend/app/services/ocr.py` | Cleans OCR output and marks watermarks. Watermarks stay in the confidential scan, but not in the text the model sees. |
| PDF | `backend/app/services/pdf_render.py`, `pdf_text.py` | Renders PDF pages to images, reads the text layer of text PDFs. |
| Confidential scan | `backend/app/services/prescan.py` | Holds a submission when a term matches. Reuses `app/pipeline/redact.py`. |
| Model call | `backend/app/ai/vision_client.py` | One image call to Gemini. Errors never include image or text content. |
| Prompt and schema | `backend/app/ai/vision_prompt.py`, `vision_schemas.py` | Model instructions and the reply shape. |
| Safeguards | `backend/app/services/vision_safeguards.py` | Drops findings that cite unknown guidelines, facts, or quotes. Holds the 10-call budget. |
| Visual read | `backend/app/services/vision_check.py` | Runs the pre-scan, batches images, enforces the budget, applies safeguards. |
| Findings rows | `backend/app/services/findings_mapper.py` | Turns findings into rows that match the database rules. |
| Model check | `backend/scripts/check_vision_model.py` | Lists the models your key can use and tests one image. |
| Scorer | `backend/scripts/score_submissions.py` | Scores a run against the labelled set. |
| Frontend API | `frontend/src/api/submissions.ts` | Calls to the submission endpoints. Uses the shared `client.ts`. |
| Frontend screens | `frontend/src/components/submissions/` | Drop zone, attachment list, status badge, hold notice, visual findings view. |
| Frontend mocks | `frontend/src/mocks/submissions.ts` | Sample data until the API is merged. |
| Evaluation set | `tests/quality/submissions/` | 30 labelled submissions and the gold answers in `manifest.json`. |

## 3. Setup

Work from the project folder with the project virtual environment active.

```powershell
cd "D:\Arya\Desktop\college work\hackatons\codex48-slim"
.\.venv312\Scripts\Activate.ps1
```

Check that the prompt shows `(.venv312)` before you run anything. If it doesn't, the commands use the wrong Python.

## 4. Running the checks

From `backend`, run the phase 2 tests:

```powershell
cd backend
python -m pytest tests/test_attachments.py tests/test_ocr_and_pdf_pure.py tests/test_vision_safeguards.py tests/test_vision_client.py tests/test_vision_schemas.py tests/test_prescan.py tests/test_vision_check.py tests/test_findings_mapper.py tests/test_score_submissions.py -q
```

The real OCR and PDF tests are skipped unless you set sample files:

```powershell
$env:BRANDGUARD_OCR_SAMPLE = "..\orange-sunscreen-tube-protecting-sun-260nw-2579651553.webp"
$env:BRANDGUARD_PDF_SAMPLE = "..\dot_and_key_spec_test.pdf"
python -m pytest tests/test_ocr_integration.py -m integration -v
```

From `frontend`, check the types:

```powershell
cd ..\frontend
npx tsc --noEmit
```

No output means the types check.

## 5. Checking the vision model

This needs a Gemini key. Set it for the current PowerShell session only. Never write it into a file that is committed, and never paste it into chat or a ticket:

```powershell
$env:GEMINI_API_KEY = "<key>"
cd backend
python scripts/check_vision_model.py ..\orange-sunscreen-tube-protecting-sun-260nw-2579651553.webp gemini-flash-latest
```

The script lists the models your key can use, then sends one image. It retries on timeouts and on 503 errors, which mean Google's servers are busy. A successful run prints the text it read from the image and the token counts. Put the model name that works in `backend\.env` as `BRANDGUARD_VISION_MODEL`.

## 6. Running the evaluation

The labelled set is generated once from `tests/quality/submissions/build_dataset.py`. Do not edit the files by hand. If a case is wrong, change the script and regenerate.

1. Run the pipeline on each submission in `manifest.json`. Save the results as `results.json`, in the format shown at the top of `backend/scripts/score_submissions.py`.
2. Score the run:

```powershell
cd backend
python scripts/score_submissions.py ..\tests\quality\submissions\manifest.json results.json
```

The report gives recall (expected problems found), precision (findings that were right), the holds that were correct and wrong, and the misses and false positives by name.

Targets from the plan are proposals until the first run: at least 70 percent recall on critical problems, and at most 30 percent of findings rejected by reviewers. Record each run's numbers in `tests/quality/submissions/RESULTS.md`, with the date and the model name.

The images are synthetic. A good score on them does not prove the system reads real packaging or real designs, so test with real files before any wider use.

## 7. Problems we have already hit

These came up during setup. Check here first.

| Symptom | Cause | Fix |
|---|---|---|
| `pytest` is not recognised | The venv is not active | Run `.\.venv312\Scripts\Activate.ps1`, or use `python -m pytest` |
| `ModuleNotFoundError: No module named 'app.services.X'` | The file is in `backend\services\` instead of `backend\app\services\` | Move it. The stray `backend\services\` folder is not part of the app |
| `Cannot find path ...` in PowerShell | Relative path used from the wrong folder | Run `cd` to the folder first, or use the full path |
| `400 Bad Request` from the model check | The key was pasted with angle brackets, or with a typo | Set the key again without brackets |
| `404` naming a model | The model has been retired | Use a name from the list the script prints |
| `503` or `read operation timed out` | Google's servers are busy | Wait 15 to 30 minutes and retry. The script already retries |
| Pip upgrades `numpy` to 2.x | The OCR package pulled in a newer numpy | `pip install "numpy==1.26.4"`. The pins are in `requirements.txt` |
| Two copies of OpenCV break `cv2` | Both `opencv-python` and `opencv-python-headless` are installed | Keep only `opencv-python==4.10.0.84` |
| A file downloaded as `name (1).ts` | The download folder already had that name | Rename it. Check it has the latest content before using it |
| Old code still runs after you copy a file | VS Code saved the old version back, or the copy never happened | Close the file in VS Code first. Check with `Select-String` for a line you know is new |

## 8. Rules for the team

- Work only on `feature/phase2-start`, or on branches cut from it. Never edit `develop` directly.
- Do not change files that phase 1 also changes until phase 1 has merged: `App.tsx`, `Sidebar.tsx`, `types/index.ts`, `data/schema.sql`, `config.py`, `ai/client.py`, and `requirements.txt`. Phase 2 adds new files next to them instead.
- Migrations start at `007`. Use the next number, and tell the team before you take one.
- Never commit API keys, `.env` files, or the backup SQL files. Check `git status` before each commit.
- Stage only the files for your change. Leave out the untracked phase 1 files and the stray copies.
- Do not add a dependency to `requirements.txt` without testing a clean install first, as we did for the OCR packages.
- If you change the contract, change `phase2_contract.md` first, and tell the team before you merge.

## 9. Decisions still open

These are not settled. Raise them before writing code that depends on them.

1. How findings link to the attachments they came from. The findings table has no column for this. Options: a link table, or one more column in migration 007.
2. A suggestion kind for confidential findings. The database only allows five kinds, and none fits a manager hold. Adding one needs a change to the database constraint.
3. Who sees a held submission beyond the creator and managers.
4. Whether creators may upload images that show people. Not decided.
5. The recall and precision targets in section 6, after the first real run.

## 10. Dependencies on phase 1

These cannot be finished until phase 1 has merged:

- Migration `007`, appended to `data/schema.sql`.
- The submission routes, `backend/app/routes/submissions.py`.
- The settings for the vision model and the limits in `config.py`.
- The Submit page and its sidebar entry in `App.tsx` and `Sidebar.tsx`.
- The final `requirements.txt` merge.

Everything else in this runbook can be done and tested now.
