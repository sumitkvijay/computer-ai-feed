# computer-ai-feed

Weekly AI-tips content feed for a Hindi-first Android app that teaches computer basics. Sources live in
`content/`, and `tools/build.py` builds `dist/v1/{hi,en}.json`, which the app downloads.

- `EDITORIAL.md`: editorial rules and voice guide.
- `ROUTINE.md`: the prompt for the weekly Claude routine.
- `tools/validate.py`, `tools/build.py`, `tools/preview.py`, `tools/prune.py`: Python 3, standard library only.
- Tests: `python3 -m unittest discover -s tests`

## How it works

1. Monday 09:00 IST, a Claude routine drafts 5-7 items and opens a PR (`feed/week-YYYY-MM-DD`).
2. `pr.yml` validates the PR and posts a preview comment (Hindi first, then English).
3. You review the preview on your phone and merge. To request changes, comment on the PR and re-run the routine.
4. `publish.yml` archives expired items, builds `dist/`, commits it, purges the jsDelivr cache and deploys Pages.

If nothing is merged, nothing changes: the app keeps showing items that are still live.

## Owner setup (one time)

1. Create the public repo `sumitkvijay/computer-ai-feed` and push this code to it.
2. Settings, Pages, Source: **GitHub Actions**.
3. At claude.ai, create a routine with a weekly schedule of **Monday 09:00 IST**, give it GitHub access to this
   repo, and paste the contents of `ROUTINE.md` as its prompt.
4. Optional: set the Firebase Remote Config parameter `ai_feed_base_urls` (a JSON array of base URLs).
   Without it the app uses the built-in defaults below.

URLs the app uses:
- primary: `https://cdn.jsdelivr.net/gh/sumitkvijay/computer-ai-feed@main/dist/v1/{lang}.json`
- fallback: `https://sumitkvijay.github.io/computer-ai-feed/v1/{lang}.json`

Pages serves the `dist/` folder, so `/v1/{lang}.json` and `/v1/images/...` both resolve.

## Fallback: Gemini drafting (documented, not built)

If the Claude routine becomes unavailable, add a `draft.yml` workflow on a weekly cron that calls the Gemini API
free tier with Search grounding, writes the items, then runs the same validate and PR steps as `ROUTINE.md`.
Use it only as a fallback.
