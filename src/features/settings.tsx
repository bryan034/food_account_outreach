import { useState } from "react";
import { Check, CheckCircle2, FlaskConical, HeartPulse, Plug, Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ErrorNote, messageOf, Pending } from "./common";
import { PageFooter } from "./shell";
import { useWorkspace } from "./workspace";
export function SettingsPage() {
  const { base, mode, configure, api } = useWorkspace();
  const [url, setUrl] = useState(base);
  const [choice, setChoice] = useState(mode);
  const [saved, setSaved] = useState(false);
  const [pending, setPending] = useState(false);
  const [health, setHealth] = useState("");
  const [error, setError] = useState("");
  function save() {
    setError("");
    try {
      const parsed = new URL(url);
      if (
        !["http:", "https:"].includes(parsed.protocol) ||
        parsed.username ||
        parsed.password ||
        parsed.search ||
        parsed.hash
      )
        throw new Error(
          "Use an HTTP or HTTPS API base URL without credentials, query parameters or a fragment.",
        );
      configure(choice, url.trim().replace(/\/$/, ""));
      setSaved(true);
      setHealth("");
    } catch (e) {
      setError(messageOf(e));
    }
  }
  async function check() {
    setPending(true);
    setHealth("");
    setError("");
    try {
      const data = await api.health();
      setHealth(
        data.status === "ok"
          ? mode === "demo"
            ? "Sample health check passed — no backend was contacted."
            : "Backend is healthy (status: ok)."
          : `Backend returned status: ${data.status}`,
      );
    } catch (e) {
      setError(messageOf(e));
    } finally {
      setPending(false);
    }
  }
  return (
    <div className="page">
      <div className="eyebrow">A workspace that stays yours</div>
      <h1 className="page-heading">Settings.</h1>
      <p className="page-description">
        Choose how your workspace connects. External credentials always stay in FastAPI.
      </p>
      <section className="settings-section settings-grid mt-4">
        <div>
          <h2>Workspace mode</h2>
          <p>Sample data and your local records stay separate.</p>
        </div>
        <div className="settings-content">
          <div className="mode-options">
            <Button
              variant="ghost"
              className={`mode-option ${choice === "demo" ? "selected" : ""}`}
              onClick={() => {
                setChoice("demo");
                setSaved(false);
              }}
              aria-pressed={choice === "demo"}
            >
              <strong>
                <span className="flex gap-2 items-center">
                  <FlaskConical size={16} />
                  Demo Mode
                </span>
                {choice === "demo" && <Check size={15} />}
              </strong>
              <p>Fictional sample businesses and outreach. No live API calls.</p>
            </Button>
            <Button
              variant="ghost"
              className={`mode-option ${choice === "connected" ? "selected" : ""}`}
              onClick={() => {
                setChoice("connected");
                setSaved(false);
              }}
              aria-pressed={choice === "connected"}
            >
              <strong>
                <span className="flex gap-2 items-center">
                  <Plug size={16} />
                  Connected mode
                </span>
                {choice === "connected" && <Check size={15} />}
              </strong>
              <p>Connect directly to your existing FastAPI and local PostgreSQL.</p>
            </Button>
          </div>
          <p className="form-help mt-3">
            Apply changes below. Demo changes last only for the current session and never touch your
            backend.
          </p>
        </div>
      </section>
      <section className="settings-section settings-grid">
        <div>
          <h2>FastAPI connection</h2>
          <p>
            One public API base URL.
            <br />
            No secret keys belong here.
          </p>
        </div>
        <div className="settings-content">
          <label>
            <span className="field-label">API base URL</span>
            <input
              className="input-control"
              type="url"
              value={url}
              onChange={(e) => {
                setUrl(e.target.value);
                setSaved(false);
              }}
              placeholder="http://localhost:8000"
            />
          </label>
          <p className="form-help">
            Defaults to VITE_API_BASE_URL, or http://localhost:8000. Only mode and this public URL
            are saved in this browser.
          </p>
          <div className="settings-actions">
            <Button onClick={save}>
              <Save />
              Apply settings
            </Button>
            {saved && (
              <span className="text-xs text-primary flex items-center gap-1">
                <CheckCircle2 size={14} />
                Settings applied
              </span>
            )}
          </div>
          <ErrorNote error={error} />
        </div>
      </section>
      <section className="settings-section settings-grid">
        <div>
          <h2>Backend health</h2>
          <p>Run a check when you’re ready.</p>
        </div>
        <div className="settings-content">
          <Button variant="outline" disabled={pending} onClick={check}>
            {pending ? <Pending /> : <HeartPulse />}
            {mode === "demo" ? "Run sample health check" : "Check backend health"}
          </Button>
          <p className="form-help mt-3">
            {mode === "demo"
              ? "Demo Mode is active. This action uses the mock client only."
              : `Checks GET /health at the applied URL: ${base}`}
          </p>
          {health && (
            <div className="success-note" role="status">
              {health}
            </div>
          )}
          <p className="form-help mt-3">
            A hosted preview cannot reliably reach a server on your computer. Use Demo Mode here and
            connected mode when running locally.
          </p>
        </div>
      </section>
      <section className="settings-section settings-grid">
        <div>
          <h2>Run locally</h2>
          <p>Your frontend, alongside FastAPI.</p>
        </div>
        <div className="settings-content">
          <p>Install the dependencies, set your FastAPI address, and start the frontend:</p>
          <pre className="code-block">
            {
              "bun install\n# .env.local\nVITE_API_BASE_URL=http://localhost:8000\n\nbun run dev --host 127.0.0.1 --port 8080"
            }
          </pre>
          <p className="mt-3">
            Open http://127.0.0.1:8080, choose Connected mode, then apply settings. Start your
            existing FastAPI server separately.
          </p>
          <p className="mt-3">
            In FastAPI, allow the exact frontend origin with CORS, including GET, POST, PATCH and
            the Content-Type header. Keep production origins explicit — do not use an unrestricted
            wildcard.
          </p>
          <pre className="code-block">
            {
              'app.add_middleware(\n    CORSMiddleware,\n    allow_origins=["http://127.0.0.1:8080"],\n    allow_credentials=False,\n    allow_methods=["GET", "POST", "PATCH"],\n    allow_headers=["Content-Type"],\n)'
            }
          </pre>
          <p className="mt-3">
            If you use localhost instead of 127.0.0.1, allow http://localhost:8080 too. These are
            distinct origins.
          </p>
        </div>
      </section>
      <section className="settings-section settings-grid">
        <div>
          <h2>Integration gaps</h2>
          <p>Clear boundaries, no pretend features.</p>
        </div>
        <div className="settings-content">
          <ul className="text-xs text-muted-foreground space-y-3 leading-7 list-disc pl-4">
            <li>
              Contact storage and website enrichment are not connected. Extracted contacts will
              remain unverified until confirmed.
            </li>
            <li>
              Contact priority will be Email → TikTok → Instagram. Email sending, AI-generated
              messages and creator statistics are future backend capabilities.
            </li>
            <li>
              There is no restaurant-list or Place-ID lookup endpoint. Existing local IDs must be
              entered manually.
            </li>
            <li>
              Discovery pagination is unavailable. Returned next-page tokens are preserved, not
              submitted.
            </li>
            <li>
              Outreach has no total count or server status filter. Status filtering applies to the
              displayed page.
            </li>
            <li>Social messages are sent manually outside this app. No OAuth or automated DMs.</li>
          </ul>
        </div>
      </section>
      <PageFooter />
    </div>
  );
}
