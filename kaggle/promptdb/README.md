# ComfyUI PromptDB on Kaggle

The Kaggle notebook is deployed to `davis1233798/comfyui-promptdb-kaggle` by
`.github/workflows/deploy-kaggle-promptdb.yml` when this branch changes.

## Required secrets

1. Add the Kaggle personal API token as the GitHub Actions repository secret
   `KAGGLE_API_TOKEN`. The workflow never prints the token.
2. In the Kaggle notebook editor, open **Add-ons → Secrets**, attach the
   existing `RCLONE_CONFIG_TEXT` secret, and keep its value in Kaggle Secrets.
   It must contain a valid rclone config with a Google Drive OAuth remote,
   custom `client_id` and `client_secret`, a refreshable token, and full Drive
   scope. The notebook normalizes a single Drive remote to `gdrive:` and
   rejects read-only or app-created-files-only OAuth scopes. It does not print
   or persist the secret in the repo.

The Drive remote is `gdrive:ComfyUI-PromptDB`. Prompt databases, workflows,
models, output images, and runtime diagnostics are copied to/from that Drive
folder. Output and other writable data are backed up every two minutes; backup
uses `rclone copy`, so existing Drive files are not deleted.

The notebook enables Drive synchronization, Krea2 model downloads, a
Cloudflare quick tunnel, and output backup by default. A quick-tunnel URL is
public and temporary. Keep the notebook running while using ComfyUI; stopping
the Kaggle runtime ends the tunnel. Kaggle may recycle or time out a runtime,
so periodic backups are used in addition to a final backup on normal stop.

## Execution logs

The GitHub Actions run pushes the notebook, checks Kaggle status for five
minutes, and collects the current Kaggle execution log. If the notebook is
still running, use the Kaggle notebook page or rerun the workflow to collect
later logs. The notebook stores ComfyUI, Cloudflare, and queue-monitor logs in
`gdrive:ComfyUI-PromptDB/logs`.
