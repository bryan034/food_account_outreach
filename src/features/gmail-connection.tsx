import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import type { GmailStatus } from "@/lib/api/types";
import { ErrorNote, messageOf, Pending } from "./common";
import { useWorkspace } from "./workspace";

export function GmailConnection() {
  const { api, mode, base } = useWorkspace();
  const [status, setStatus] = useState<GmailStatus | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    api
      .gmailStatus()
      .then((value) => {
        if (active) setStatus(value);
      })
      .catch((error) => {
        if (active) setError(messageOf(error));
      });
    return () => {
      active = false;
    };
  }, [api]);
  async function connect() {
    setPending(true);
    setError("");
    try {
      if (new URL(base).hostname !== window.location.hostname)
        throw new Error(
          "Use the same hostname for frontend and API. For Compose, open 127.0.0.1:5173 and set API URL to http://127.0.0.1:8000.",
        );
      const result = await api.gmailConnect();
      const url = new URL(result.authorization_url);
      if (url.protocol !== "https:" || url.hostname !== "accounts.google.com")
        throw new Error("Unexpected Google authorization URL.");
      const callback = url.searchParams.get("redirect_uri");
      if (!callback || new URL(callback).hostname !== new URL(base).hostname)
        throw new Error(
          "The Gmail callback hostname must match the API URL so its OAuth cookie can be verified.",
        );
      window.location.assign(url.href);
    } catch (error) {
      setError(messageOf(error));
      setPending(false);
    }
  }
  async function disconnect() {
    setPending(true);
    setError("");
    try {
      await api.gmailDisconnect();
      setStatus(await api.gmailStatus());
    } catch (error) {
      setError(messageOf(error));
    } finally {
      setPending(false);
    }
  }
  return (
    <section className="settings-section settings-grid">
      <div>
        <h2>Gmail connection</h2>
        <p>Send only the emails you review and approve.</p>
      </div>
      <div className="settings-content">
        <p className="text-sm mb-3">
          {mode === "demo"
            ? "Demo mode never signs into Google or sends real email."
            : status?.connected
              ? `Connected: ${status.email}`
              : "No Gmail account connected."}
        </p>
        {status?.detail && <p className="form-help mb-3">{status.detail}</p>}
        <div className="flex gap-2 flex-wrap">
          <Button disabled={pending || mode === "demo" || !status?.configured} onClick={connect}>
            {pending && <Pending />}
            {status?.connected ? "Reconnect Gmail" : "Connect Gmail"}
          </Button>
          {mode === "connected" && status?.connected && (
            <Button variant="outline" disabled={pending} onClick={disconnect}>
              Disconnect locally
            </Button>
          )}
        </div>
        <p className="form-help mt-3">
          Google sign-in grants send-only Gmail access, plus your Google email identity—not inbox
          reading. OAuth credentials and encrypted refresh tokens stay in FastAPI/PostgreSQL. Setup
          instructions: docs/gmail-setup.md.
        </p>
        <p className="form-help">
          Use 127.0.0.1 for both frontend and API URLs during local OAuth. Disconnecting removes
          local tokens; you can also revoke this app in your Google account permissions.
        </p>
        <ErrorNote error={error} />
      </div>
    </section>
  );
}
