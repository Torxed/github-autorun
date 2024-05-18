# github-autorun

Approves runners automatically in PR's if `.github/workflows` are untouched.

# Install & Run

1. Log-on to [GitHub](#)
2. Go to `Personal/Repo settings`
3. Go to `Developer Settings`
4. Setup a `Personal access tokens`/`Fine-grained tokens`.
5. Add the token to `github-autorun.toml` and define the repo:
   ```toml
   [github]
   access_token = "github_pat_..."
   repository = "Torxed/github-autorun"
   ```
6. Go to `https://github.com/<owner>/<repo>/settings/hooks`
7. `Add webhook` with:
   - `Payload URL` to where `github-autorun` will listen
   - `Content type` set to `application/json`
   - Configure a `Secret` that will be configured in `github-autorun.toml`:
     ```toml
     [github]
     secret = "..."
     ```
   - Select `Let me select individual events` to not spam the webhook too much:
     * `Pull requests`
     * `Workflow jobs`

After that is done, you should be able to start:
```bash
$ python -m autorun
```