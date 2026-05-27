Place your reference paper PDFs in this folder.

At startup, brainstorm.py will:
  1. Scan docs/ for new PDFs (no matching .md in summaries/)
  2. Read the full paper and call Claude Sonnet to summarize
  3. Save the summary to docs/summaries/<name>.md

The literature_expert agent reads ONLY from docs/summaries/.
You can manually edit any summary .md file if needed.

To force re-summarize all papers:
  python brainstorm.py --resummarize

To view all summaries at startup:
  python brainstorm.py --show-summaries
