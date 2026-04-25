# GitHub App Setup Guide

Step-by-step instructions to register and configure Sentinel as a GitHub App.

## 1. Register the App

1. Go to **GitHub → Settings → Developer Settings → GitHub Apps → New GitHub App**  
   URL: https://github.com/settings/apps/new

2. Fill in the form:

| Field | Value |
|-------|-------|
| **App name** | `Sentinel AI Review` (or your choice) |
| **Homepage URL** | Your dashboard URL (e.g. `https://sentinel-dashboard.vercel.app`) |
| **Webhook URL** | Backend URL + `/webhook/github` (e.g. `https://sentinel-api.fly.dev/webhook/github`) |
| **Webhook secret** | Generate with `openssl rand -hex 32` — save for `.env` |

3. Set **Permissions**:

| Permission | Access | Why |
|------------|--------|-----|
| Pull requests | Read & Write | Post review comments |
| Checks | Read & Write | Create check runs |
| Contents | Read | Fetch PR diffs |
| Metadata | Read | Required |

4. Subscribe to **Events**: Pull request, Pull request review, Pull request review comment.

5. **Where can this GitHub App be installed?** — start with “Only on this account” if you prefer.

6. Click **Create GitHub App**.

## 2. Private key

1. Under **Private keys**, click **Generate a private key**.
2. Save the downloaded `.pem` as `private-key.pem` in the backend directory (never commit it; it is gitignored).

## 3. App ID

Copy **App ID** from the app settings page into `GITHUB_APP_ID`.

## 4. Environment variables

```bash
GITHUB_APP_ID=123456
GITHUB_PRIVATE_KEY_PATH=./private-key.pem
GITHUB_WEBHOOK_SECRET=<the secret from step 1>
```

## 5. Install the app

1. Open `https://github.com/settings/apps/<your-app>/installations`.
2. **Install** on your account and select repositories.

## 6. Local webhooks (smee.io)

1. Create a channel at https://smee.io and copy the proxy URL.
2. `npm install -g smee-client`
3. `smee -u https://smee.io/<channel> -t http://localhost:8000/webhook/github`
4. Point the GitHub App webhook at the smee URL for local testing.

## 7. Verify

Open a test PR with an obvious issue; confirm inline comments and check runs appear.

## Troubleshooting

- **401 on webhook** — `GITHUB_WEBHOOK_SECRET` must match GitHub’s configuration.
- **No comments** — Check logs; private key path and permissions are common issues.
- **Resource not accessible by integration** — Grant Pull requests + Checks write on the app.
