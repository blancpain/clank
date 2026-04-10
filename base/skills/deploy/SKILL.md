---
name: deploy
description: "Deploy the current branch to production. Scaffold — edit this file to add your deploy command. Invoke via /deploy."
disable-model-invocation: true
---

# Deploy to Production

Deploy the current branch to production.

## Pre-Flight Checks

Before deploying, verify ALL of the following:

1. **Clean working tree** — confirm there are no uncommitted changes:
   ```bash
   git status
   ```
   If the output is not clean, stop and report. Do not deploy with uncommitted changes.

2. **Branch is pushed to origin** — confirm local commits match the remote:
   ```bash
   git log origin/HEAD..HEAD --oneline
   ```
   If any commits appear (not pushed yet), stop and report.

3. **CI is green** — check that the latest commit on the remote passed CI:
   ```bash
   git log --oneline -1 origin/HEAD
   ```
   Then verify the CI status for that commit (ask the user if unsure — check your CI dashboard or use a CLI tool like `gh run list`).

If any pre-flight check fails, **stop and report** — do not deploy.

## Deploy Command

```
# TODO: Fill in your project's deploy command here.
# Examples:
#   ssh user@host "cd /app && git pull && systemctl restart svc"
#   kubectl rollout restart deployment/foo
#   vercel --prod
#   fly deploy
#   git push heroku main
#   railway up
```

## Post-Deploy Verification

```
# TODO: Fill in your service health check here.
# Examples:
#   curl -sSf https://your-domain/health
#   ssh user@host "systemctl status svc --no-pager -l"
#   kubectl get pods -l app=foo
#   fly status
```

Report the result of the health check to the user: service status, any errors from the deploy output.

## Rollback

If the deploy fails or the service won't start:

1. Show the user the full error output — do not summarize or hide it.
2. Identify the last good commit:
   ```bash
   git log --oneline -10
   ```
3. Do **NOT** roll back automatically — let the user decide which commit to revert to and how.
