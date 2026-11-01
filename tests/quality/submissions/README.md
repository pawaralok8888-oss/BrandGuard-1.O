# Labelled test submissions

30 submissions with the known problems listed in `manifest.json`:

| Kind | Count | Files |
|---|---|---|
| script | 6 | text (`files/S*.txt`) |
| marketing_idea | 6 | text (`files/M*.txt`) |
| design | 9 | PNG (`files/D*.png`) |
| image | 9 | PNG (`files/I*.png`) |

Three submissions (M3, D8, I9) contain a confidential term and must be held. The rest must not be held.

The PNG files are synthetic: printed text on plain panels. They are for testing the reader, not for judging real artwork.

To rebuild the files and the manifest:

```powershell
python build_dataset.py
```

Score a run with `backend/scripts/score_submissions.py`. See `docs/phase2_runbook.md`, section 6.
