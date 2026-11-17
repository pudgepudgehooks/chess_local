# Private beta on Streamlit Community Cloud

Deploy **beta_app.py**, not visualization_all.py or run_trainer.py. The local trainer intentionally has no authentication. Never publish that local entry point as the beta.

## What is included

- Google OIDC sign-in plus a verified-email invitation list, checked before database access.
- Identity derived from the provider's issuer and subject, not the typed Chess.com username.
- PostgreSQL tables for puzzles, review events, and analysis jobs. All reads and writes are scoped to the signed-in account. Local JSON and legacy sample puzzles are not imported online.
- Transactional review updates and idempotent drag events; regenerated puzzles preserve review history.
- One active analysis globally, one queued/running request per user, six requests per day, queue capacity 20. Each request has at most five standard games, 400 plies per game, and 1 MB of PGN. Monthly imports take the last five standard games returned by Chess.com.
- Stockfish runs on the server with one thread and 32 MB hash. Each position search targets 0.15 seconds, depth at most 12. Jobs have a ten-minute analysis deadline; engine protocol operations have a ten-second timeout. This is a lightweight, approximate analysis suitable for a small beta; it is not equivalent to the unrestricted local depth-15 analysis.
- Jobs are persisted before execution and survive page refreshes. A crashed job's 15-minute lease expires and it is retried on the next worker poll. Results commit atomically. Identical completed requests are reused per account.

Both Chess.com and Lichess monthly imports are supported. Choose the source and use that platform's username. Lichess imports the five most recent completed standard games in the selected UTC month and does not need an API token. The same per-user quota and private storage apply to both platforms.

## 1. Create the database

Use a managed PostgreSQL database with TLS. Keep its connection string private, and enable the provider's backups before inviting testers. Use a database role scoped to this app's database/schema; it needs permission to create the four `beta_*` tables at first startup. Never use the production database for tests. This repository does not create a hosting or database account for you.

## 2. Choose the app URL and configure Google login

In Google Cloud Console, create/configure an OAuth consent screen and an OAuth client of type **Web application**. For a testing consent screen, add the intended testers. Configure this authorized redirect URI using the exact app URL you select in Community Cloud:

```text
https://YOUR-APP.streamlit.app/oauth2callback
```

Copy the client ID and client secret into Community Cloud's Secrets settings, not into GitHub or chat. Configure the same URL as `auth.redirect_uri`. The invitation list is independent of Google test-user enrollment; the user must satisfy both where applicable.

## 3. Deploy

1. Sign into https://share.streamlit.io with access to `pudgepudgehooks/chess_local`.
2. Create an app from that repository, branch `main`, entry point **beta_app.py**. Use Python **3.11**. Choose an app subdomain and keep it consistent with the OAuth redirect above.
3. In Advanced settings, paste the structure from [.streamlit/secrets.example.toml](.streamlit/secrets.example.toml), replacing every placeholder. Generate `cookie_secret` locally with `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
4. Set `beta.allowed_emails` to your Google email and your testers' verified Google emails. Never leave a placeholder in the invite list. Remove an email to revoke its access on the next app rerun. Login cookies may otherwise remain valid until expiry; change the cookie secret to invalidate all sessions.
5. Deploy. `requirements.txt` installs the Python dependencies; `packages.txt` installs Linux Stockfish at `/usr/games/stockfish`.
6. If Community Cloud offers app-level sharing restrictions for your account/repository, use them too. The application itself enforces its invitation list even when its landing page is reachable publicly.

No local executable path is entered by visitors. All runtime secrets belong in the deployment's settings. The example secrets file contains no working credentials.

## 4. Verify before invitations

- A signed-out visitor sees only the login page.
- An uninvited Google account is rejected before any database query or worker startup.
- Two invited accounts generate different libraries; neither can see the other's jobs or reviews.
- Generate a short PGN with your exact player header, leave the page, return, and use **Refresh puzzle library** after the job completes.
- Solve a puzzle, refresh, and confirm the attempt and schedule persist.
- Confirm PostgreSQL CI checks pass and configure provider backups. Review service logs for failures without sharing credentials.

## Operating limits and recovery

Community Cloud is the web host and runs a small in-process background worker. Its process can sleep, restart, or be stopped when resource limits are reached; this is not an always-on queue service. An invited visitor starts the worker. Persisted queued jobs resume then, and an interrupted running job becomes eligible after its lease expires (up to 15 minutes). A completed job erases its stored PGN payload; failed jobs also erase it. Queued/running jobs temporarily retain PGNs in your database. Puzzle records retain game context needed for review.

Reboot the app after changing database/engine secrets. Database errors fail closed. Users see a generic service error; details appear in owner-accessible logs. No database URL should be copied into bug reports. If the app grows beyond this beta, move `beta_worker.Worker` to a dedicated worker service and keep PostgreSQL as the source of truth.

There is no automated retention/deletion policy for completed job metadata and review events yet. The beta operator should handle account deletion requests by removing that owner's rows from all three data tables, and use a consistent provider backup retention policy. Do not advertise the service as a production public launch yet.

## Tests

```powershell
$env:PYTHONPATH = "$PWD\.deps"
python -m unittest discover -s tests -v
```

PostgreSQL concurrency coverage runs in GitHub Actions against an isolated PostgreSQL service. To run it locally, set `BETA_TEST_DATABASE_URL` to a dedicated test database. Most local storage tests use temporary SQLite files; they do not substitute for the PostgreSQL concurrency check.

## References

- https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
- https://docs.streamlit.io/develop/concepts/connections/authentication
- https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies
