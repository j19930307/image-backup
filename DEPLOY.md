# Deploy

This repo supports automatic deployment to Cloud Run from GitHub Actions whenever code is pushed to `main`.

## One-time Google Cloud setup

1. Enable these APIs in project `image-backup-493507`:
   - `run.googleapis.com`
   - `artifactregistry.googleapis.com`
   - `cloudbuild.googleapis.com`
   - `iamcredentials.googleapis.com`
   - `sts.googleapis.com`
2. Create a deployment service account for GitHub Actions, for example `github-deploy@image-backup-493507.iam.gserviceaccount.com`.
3. Grant that service account these roles:
   - `roles/run.admin`
   - `roles/cloudbuild.builds.editor`
   - `roles/artifactregistry.writer`
   - `roles/iam.serviceAccountUser`
4. Create a Workload Identity Pool and Provider for GitHub Actions.
5. Allow the GitHub repository to impersonate the deployment service account via Workload Identity Federation.

## GitHub repository secrets

Add these repository secrets in GitHub:

- `GCP_PROJECT_ID`
  - `image-backup-493507`
- `GCP_REGION`
  - `asia-east1`
- `CLOUD_RUN_SERVICE`
  - `image-backup`
- `CLOUD_RUN_RUNTIME_SERVICE_ACCOUNT`
  - `image-backup-runtime@image-backup-493507.iam.gserviceaccount.com`
- `GCP_SERVICE_ACCOUNT`
  - `github-deploy@image-backup-493507.iam.gserviceaccount.com`
- `GCP_WORKLOAD_IDENTITY_PROVIDER`
  - Example:
    `projects/803663828198/locations/global/workloadIdentityPools/github/providers/github-actions`

The workflow uses `GCP_SERVICE_ACCOUNT` in two places:

- GitHub Actions authenticates as this service account through Workload Identity Federation.
- Cloud Run source deploy uses it as the explicit build service account via `--build-service-account`, which avoids relying on a deleted default Cloud Build service account.

## Runtime secrets

The workflow only redeploys source code. Your runtime secrets stay managed in Cloud Run / Secret Manager:

- `DISCORD_PUBLIC_KEY`
- `GOOGLE_OAUTH_TOKEN_JSON`

If those are already configured on the Cloud Run service, this workflow does not need them in GitHub.

## Workflow behavior

- Push to `main` triggers automatic deployment.
- `workflow_dispatch` lets you deploy manually from the GitHub Actions tab.

## First push

After adding the workflow and repository secrets:

1. Push this repo to GitHub.
2. Ensure the default branch is `main`.
3. Push a new commit to `main`.
4. Confirm the `Deploy to Cloud Run` workflow succeeds in GitHub Actions.
