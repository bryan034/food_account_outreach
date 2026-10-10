import { AlertCircle, Check, ExternalLink, Loader2, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { Status } from "@/lib/api/types";
export function StatusBadge({ status }: { status: Status }) {
  return (
    <span className={`status-badge status-${status}`}>
      <span className="status-dot" />
      {status.charAt(0).toUpperCase() + status.slice(1).replaceAll("_", " ")}
    </span>
  );
}
export function ErrorNote({ error }: { error: string }) {
  return error ? (
    <div className="error-note" role="alert">
      <AlertCircle size={17} />
      <span>{error}</span>
    </div>
  ) : null;
}
export function Pending() {
  return <Loader2 className="animate-spin" size={17} />;
}
export const messageOf = (error: unknown) =>
  error instanceof Error ? error.message : "Something went wrong. Please try again.";
export function formatDate(value: string | null) {
  if (!value) return "Not sent";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Unknown date"
    : date.toLocaleString("en-SG", {
        day: "numeric",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        timeZone: "Asia/Singapore",
      });
}
export function safeUrl(value?: string) {
  try {
    const url = new URL(value || "");
    return url.protocol === "https:" || url.protocol === "http:" ? url.href : null;
  } catch {
    return null;
  }
}
export interface ContactInfo {
  type: "email" | "tiktok" | "instagram";
  value: string;
  directUrl?: string;
  sourceUrl?: string;
  verified: boolean;
  usable: boolean;
  enrichmentError?: string;
}
export function ContactCard({ contact }: { contact: ContactInfo }) {
  const direct = safeUrl(contact.directUrl),
    source = safeUrl(contact.sourceUrl);
  return (
    <div className="contact-card">
      <div className="flex items-center justify-between gap-2">
        <strong className="capitalize">{contact.type}</strong>
        <span className="mini-label">
          {contact.verified ? (
            <>
              <ShieldCheck size={13} />
              Verified
            </>
          ) : (
            "Unverified"
          )}
        </span>
      </div>
      <p className="break-all mt-2">{contact.value}</p>
      <div className="flex gap-3 mt-3 text-xs text-muted-foreground">
        <span>
          {contact.usable ? (
            <>
              <Check size={12} /> Usable
            </>
          ) : (
            "Not confirmed usable"
          )}
        </span>
        {source && (
          <a href={source} target="_blank" rel="noopener noreferrer">
            Source page ↗
          </a>
        )}
      </div>
      {direct && (
        <Button asChild variant="link" className="px-0">
          <a href={direct} target="_blank" rel="noopener noreferrer">
            <ExternalLink />
            Open profile
          </a>
        </Button>
      )}
      {contact.enrichmentError && <ErrorNote error={contact.enrichmentError} />}
    </div>
  );
}
