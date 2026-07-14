# Deployment Guide — Gwaro Capital

This document explains quick ways to make the application publicly reachable using Docker (recommended) or a PaaS that accepts a `Procfile` (Heroku, Render, etc.).

Quick Docker (local) - build and run:

```bash
docker build -t gwaro-capital:latest .
docker run -p 8000:8000 \
  -e SECRET_KEY='replace-with-secure' \
  -e DATABASE_URL='sqlite:///gwaro.db' \
  gwaro-capital:latest
```

Docker Compose (local):

```bash
docker-compose up --build
```

Platform notes:
- Always set `SECRET_KEY` and other secrets via environment variables on the host.
- For production, use a proper RDBMS (Postgres) instead of the default SQLite and configure `DATABASE_URL`.
- Mount or configure a persistent directory for `logs/` and `database/` to avoid data loss.

Security:
- Terminate debug mode (`FLASK_ENV=production`).
- Use HTTPS at the load-balancer (NGINX or managed TLS) and set `SESSION_COOKIE_SECURE=true`.

Next steps after deployment:
- Point a domain and TLS certificate to the host.
- Add monitoring, backups, and automated deployments.

Render deploy (recommended)

1. Push your repo to GitHub (see commands below).
2. Create a Render account and connect your GitHub repo.
3. Use the existing `render.yaml` or create a new Web Service using Docker and the `Dockerfile`.
4. In Render service settings add two secrets: `SECRET_KEY` and `DATABASE_URL` (or set them under Environment).
5. Deploy. Render provides automatic HTTPS.

GitHub push commands (run locally):

```bash
git init
git add .
git commit -m "Prepare site for deploy"
git branch -M main
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```

Set up GitHub Actions & Render deploy

- Ensure the `RENDER_API_KEY` and `RENDER_SERVICE_ID` are stored as GitHub Secrets in the repo (Settings → Secrets).
- The workflow `.github/workflows/render-deploy.yml` will run on pushes to `main` and trigger Render.

Google Search Console (submit sitemap)

1. Go to https://search.google.com/search-console and add `https://gwarocapital.com`.
2. Verify ownership (DNS TXT is easiest via your domain registrar).
3. In Search Console → Sitemaps, submit `https://gwarocapital.com/sitemap.xml`.
4. Use URL Inspection to request indexing for the homepage and important pages.

Troubleshooting & verification

- Check `https://gwarocapital.com/robots.txt` and `https://gwarocapital.com/sitemap.xml` in your browser after deployment.
- Use `curl -I https://gwarocapital.com` to confirm HTTP 200 and TLS.
- Check Render logs if the app fails to start.

