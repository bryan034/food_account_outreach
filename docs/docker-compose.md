# Start the whole application with Docker Compose

This is a local development setup, not a production deployment. Docker Desktop must be running. Keep `.env` at the repository root using `.env.example` as a template; never commit real credentials.

## Commands

From the repository root:

```sh
docker compose up --build -d
```

- `docker compose` reads `compose.yaml` and uses `.env` for `${...}` substitutions.
- `up` creates/starts all three services: `db`, `backend`, `frontend`.
- `--build` builds the two application images from the current repository. Dependencies are cached when their lockfiles have not changed.
- `-d` leaves the services running in the background, so one terminal is sufficient.

Open `http://127.0.0.1:5173`. In Settings choose **Connected**, set the API URL to `http://127.0.0.1:8000`, apply and check health. Demo remains the safe default unless your browser has saved Connected settings. Change `FRONTEND_PORT` or `BACKEND_PORT` in `.env` if needed; use those changed ports in your browser settings too.

After code changes, repeat `docker compose up --build -d`. These images contain a copy of your code, not a live mount; editing VS Code files alone does not update running containers. This avoids mixing your macOS `.venv` or `node_modules` with Linux dependencies. Once built, `docker compose up -d` starts the existing images without a rebuild.

```sh
docker compose ps
docker compose logs -f backend frontend
docker compose down
```

- `ps` lists service status and health.
- `logs` reads their output; `-f` follows new output; the two names select only the application services. Ctrl+C stops following logs, not the containers.
- `down` stops/removes service containers and their Compose network. It does **not** remove the existing named database volume. Do not add `-v`: that requests volume deletion and can erase your database.

Stop any separately running Uvicorn/Vite processes before Compose starts, because two processes cannot claim the same host port. This implementation stops only the local application processes started by the coding session during verification, not unrelated services.

## Connections and startup order

| Caller | Destination | Reason |
| --- | --- | --- |
| Browser on your Mac | `http://127.0.0.1:5173` | Published frontend port |
| Browser's JavaScript | `http://127.0.0.1:8000` | Published FastAPI port; the browser cannot resolve Docker service names |
| Backend container | `db:5432` | Compose resolves the PostgreSQL service name inside its network |
| Python run directly on your Mac | `localhost:${POSTGRES_PORT}` | Published database port; your existing `.env` remains usable |

The named volume remains `food_outreach_postgres_data`. This preserves your existing database. Only PostgreSQL needs persistent storage here; FastAPI owns records in PostgreSQL, and the frontend stores no application records in its container.

The database must pass its healthcheck before backend starts. Backend runs `alembic upgrade head`, then starts Uvicorn only if migration succeeds. Its healthcheck must pass before frontend starts. This is a single-backend local setup; a scaled deployment would use a separate migration job rather than several replicas running migrations simultaneously.

Containers bind their servers to `0.0.0.0` **inside** the container so Docker can reach them. Compose publishes ports on `127.0.0.1` **on your computer** so they are not publicly exposed on your LAN. CORS permits the two local frontend origins for your selected port. CORS is not authentication: don't expose this app publicly as-is.

## Files, line by line

### `Dockerfile.backend`

- `FROM python:3.13-slim-bookworm`: starts with Python 3.13 on a small Debian Linux image.
- `COPY --from=ghcr.io/astral-sh/uv:0.12.17 /uv /bin/uv`: copies the official uv binary, matching the installed uv version used to develop this project.
- `WORKDIR /app`: subsequent relative paths and commands use this container directory.
- `ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never`: copies dependencies into the environment and uses the image's Python instead of downloading another interpreter.
- `ENV PATH="/app/.venv/bin:$PATH"`: makes the uv-installed `python`, `alembic` and `uvicorn` executable without activating a shell environment.
- `COPY pyproject.toml uv.lock README.md ./`: copies dependency/build metadata. README is needed by the Python package's build metadata.
- `COPY src/automate_food_places_outreach ...`: copies only the backend package into its matching path.
- `RUN uv sync --locked --no-dev`: installs locked application dependencies and the project. `--locked` refuses an outdated lockfile; `--no-dev` excludes pytest. Docker's environment is separate from your Mac's uv environment.
- `COPY alembic.ini ./` and `COPY migrations ./migrations`: include migration configuration and revision history.
- `EXPOSE 8000`: documents the internal port; it does not publish it by itself.
- `CMD [...]`: runs the startup shell. `alembic upgrade head` applies pending schema migrations; `&&` starts the API only on success; `exec` replaces the shell with Uvicorn so Docker's stop signal reaches it. `--host 0.0.0.0` listens on container interfaces; `--port 8000` uses its internal API port. `--no-access-log` prevents OAuth authorization codes in callback URLs from appearing in HTTP access logs.

### `Dockerfile.frontend`

- `FROM node:24-bookworm-slim`: includes Node and npm on Debian, separate from your Mac's installed Node.
- `WORKDIR /app`: sets the application directory.
- `COPY package.json package-lock.json ./`: copies dependency metadata before source so dependency installation can be cached.
- `RUN npm ci`: installs exactly the npm lockfile's dependency tree, refusing mismatches. Keep `package-lock.json` in Git for this build.
- `COPY src ./src`, `COPY public ./public`, `COPY vite.config.ts tsconfig.json ./`: copy frontend sources, assets and configuration. The Python source also lives under `src`, but Vite does not execute it.
- `EXPOSE 5173`: documents the internal frontend port.
- `CMD [...]`: runs `npm run dev`; `--` forwards flags to Vite; `--host 0.0.0.0` permits Docker to forward traffic; `--port 5173` selects the container port; `--strictPort` fails clearly rather than silently moving to another port. This uses Vite development mode, not a production web server.

### `compose.yaml`

- `services` declares three separate containers; adding them does not combine their filesystems.
- Each application's `build.context: .` makes the repository its build input; `dockerfile` selects its recipe.
- Backend `env_file: [ .env ]` loads runtime variables directly from the project file. Use literal `NAME=value` assignments for credentials, not bare variable names or `${OTHER_VARIABLE}` references. Same-named shell exports no longer replace the Places key, OAuth credentials or Gmail encryption key because those variables have no overriding `environment` entry. The file is not passed to frontend or baked into either image. Discovery returns a configuration error if no usable key exists.
- `environment` overrides selected values from `env_file`. Backend overrides `POSTGRES_HOST` to `db` and `POSTGRES_PORT` to `5432` regardless of your host-side `.env` values. Database credentials remain substituted identically for database and backend; public ports also still use Compose substitution (shell first, then `.env`).
- `VITE_API_BASE_URL` is a public browser URL, not a secret or an internal Docker URL. Docker explicitly supplies it to Vite at startup; browser Settings can still override it.
- `${BACKEND_PORT:-8000}` and `${FRONTEND_PORT:-5173}` provide defaults when optional variables are absent.
- `ports` entries are `host-interface:host-port:container-port`. The host side is local-only; the internal ports stay fixed.
- `depends_on` with `condition: service_healthy` waits for readiness, not merely process creation. It does not guarantee a dependency stays healthy forever.
- Backend `healthcheck.test` uses Python's standard-library HTTP client against its own `/health`; frontend uses Node's `fetch` against its own page. Neither makes a paid Google request or sends outreach.
- `interval` controls the gap between probes; `timeout` caps a probe; `retries` counts consecutive failures; `start_period` gives startup extra time before failures count.
- The existing `volumes` declaration and explicit database-volume name remain unchanged.

### `.dockerignore`

This filters the build context before Docker receives it. It excludes `.env`/other environment files, host dependency folders, Git history, bytecode, caches and build artifacts. Dockerfiles copy specific sources rather than `COPY . .`, giving another boundary against accidentally baking credentials into images. Runtime backend credentials still exist in the container environment; anyone with Docker access can inspect them, so this is not a production secret-management solution.

## Sources

The configuration follows [uv's Docker integration guide](https://docs.astral.sh/uv/guides/integration/docker/) and [Docker Compose startup ordering](https://docs.docker.com/compose/how-tos/startup-order/).
