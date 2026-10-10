import { useEffect, useRef, useState } from "react";
import { Check, Copy, ExternalLink, Search, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import {
  validProfile,
  type Channel,
  type Place,
  type PublicContact,
  type GmailStatus,
  type Status,
} from "@/lib/api/types";
import { ErrorNote, messageOf, Pending, safeUrl } from "./common";
import { useWorkspace } from "./workspace";
import { GeminiDraft } from "./gemini-draft";

export function SocialWorkflow({ place, onRecorded }: { place?: Place; onRecorded?: () => void }) {
  const { api, mode } = useWorkspace();
  const [business, setBusiness] = useState<Place | null>(place || null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Place[]>([]);
  const [label, setLabel] = useState("");
  const [channel, setChannel] = useState<Channel>("tiktok");
  const [profile, setProfile] = useState("");
  const [message, setMessage] = useState("");
  const [pending, setPending] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [checked, setChecked] = useState(false);
  const [done, setDone] = useState(false);
  const [recipient, setRecipient] = useState("");
  const [source, setSource] = useState("");
  const [subject, setSubject] = useState("");
  const [emailContacts, setEmailContacts] = useState<PublicContact[]>([]);
  const [contactsPending, setContactsPending] = useState(false);
  const [gmail, setGmail] = useState<GmailStatus | null>(null);
  const [approvedId, setApprovedId] = useState<number | null>(null);
  const [emailOutcome, setEmailOutcome] = useState<Status | null>(null);
  const contactLookups = useRef(new Map<string, Promise<PublicContact[]>>());
  const isEmail = channel === "email";
  const locked = pending || generating || approvedId !== null;
  const profileUrl = isEmail ? null : validProfile(profile, channel);

  useEffect(() => {
    if (!isEmail || !business) return;
    let active = true;
    setContactsPending(true);
    setError("");
    let lookup = contactLookups.current.get(business.id);
    if (!lookup) {
      lookup = api.contacts(business.id);
      contactLookups.current.set(business.id, lookup);
    }
    lookup
      .then((contacts) => {
        if (!active) return;
        const emails = contacts.filter((contact) => contact.contact_type === "email");
        setEmailContacts(emails);
        setRecipient(emails[0]?.value || "");
        setSource(emails[0]?.source_url || "");
      })
      .catch((error) => {
        if (active) setError(messageOf(error));
      })
      .finally(() => {
        if (active) setContactsPending(false);
      });
    api
      .gmailStatus()
      .then((value) => {
        if (active) setGmail(value);
      })
      .catch((error) => {
        if (active) setError(messageOf(error));
      });
    return () => {
      active = false;
    };
  }, [api, isEmail, business]);

  async function search() {
    if (pending || !query.trim()) return;
    setPending(true);
    setError("");
    try {
      setResults((await api.discover(query.trim())).places);
    } catch (error) {
      setError(messageOf(error));
    } finally {
      setPending(false);
    }
  }
  async function copy() {
    try {
      await navigator.clipboard.writeText(message);
      setCopied(true);
    } catch {
      setError("Select and copy the message manually; clipboard access is unavailable.");
    }
  }
  async function markSent() {
    if (!business || !checked || pending || generating) return;
    setPending(true);
    setError("");
    try {
      if (channel === "email") {
        let identity = approvedId;
        if (identity === null) {
          const approved = await api.approveEmail({
            google_place_id: business.id,
            ...(label.trim() ? { name: label.trim() } : {}),
            recipient: recipient.trim(),
            source_url: source.trim(),
            subject,
            message_text: message,
            approved: true,
            verified_public_business_email: true,
          });
          identity = approved.id;
          setApprovedId(identity);
        }
        const result = await api.sendEmail(identity);
        setEmailOutcome(result.status);
      } else {
        await api.markPlaceSent({
          google_place_id: business.id,
          ...(label.trim() ? { name: label.trim() } : {}),
          channel,
          message_text: message,
          confirmed_sent: true,
        });
      }
      setConfirm(false);
      setDone(true);
      onRecorded?.();
    } catch (error) {
      setError(messageOf(error));
    } finally {
      setPending(false);
    }
  }
  return (
    <div className="panel-section">
      {!business ? (
        <div className="form-stack">
          <h3>Choose a business</h3>
          <label>
            <span className="field-label">Business search</span>
            <input
              className="input-control"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Business name and Singapore neighbourhood"
            />
          </label>
          <Button disabled={pending || !query.trim()} onClick={search}>
            {pending ? <Pending /> : <Search />}Search businesses
          </Button>
          <p className="form-help">Search runs only when you press the button.</p>
          {results.map((result) => (
            <Button key={result.id} variant="outline" onClick={() => setBusiness(result)}>
              {result.display_name.text}
            </Button>
          ))}
        </div>
      ) : done ? (
        <div className="success-note">
          {mode === "demo"
            ? "Sample outreach recorded. No message was sent."
            : emailOutcome === "sent"
              ? "Gmail accepted your email for sending. Your exact approved message was saved."
              : emailOutcome === "email_unknown" || emailOutcome === "email_sending"
                ? "Delivery needs checking in Gmail. Do not resend; your approved message is saved in Outreach."
                : emailOutcome === "email_failed"
                  ? "Gmail rejected this send. Nothing is marked as sent. Review the saved record in Outreach."
                  : "Your confirmed outreach and exact message were saved."}
          <a className="block mt-3 underline" href="/outreach">
            View contacted businesses in Outreach
          </a>
        </div>
      ) : (
        <div className="form-stack">
          <h3>{business.display_name.text}</h3>
          <p className="form-help">
            {isEmail
              ? "Your exact email is saved on approval, then sent through your connected Gmail account."
              : "The business record is created automatically when you confirm sending."}
          </p>
          <label>
            <span className="field-label">Name for your outreach notes (optional)</span>
            <input
              className="input-control"
              value={label}
              disabled={locked}
              onChange={(e) => setLabel(e.target.value)}
              placeholder={business.display_name.text}
            />
            <span className="form-help">
              Leave blank to display the current restaurant name from Google in Outreach. Your own
              label is saved; Google names are looked up rather than permanently stored.
            </span>
          </label>
          <label>
            <span className="field-label">Contact channel</span>
            <select
              className="input-control"
              value={channel}
              disabled={locked}
              onChange={(e) => {
                setChannel(e.target.value as Channel);
                setProfile("");
              }}
            >
              <option value="tiktok">TikTok</option>
              <option value="instagram">Instagram</option>
              <option value="email">Email</option>
            </select>
          </label>
          {isEmail ? (
            <>
              <p className="form-help">
                Selecting Email makes one Google website lookup, then reads public website pages.
                You still approve every send.
              </p>
              {contactsPending && (
                <p className="form-help">
                  Looking for public email addresses on the business website…
                </p>
              )}
              {emailContacts.length > 1 && (
                <label>
                  <span className="field-label">Emails found on public pages</span>
                  <select
                    className="input-control"
                    disabled={locked}
                    value={`${recipient}|${source}`}
                    onChange={(event) => {
                      const contact = emailContacts.find(
                        (entry) => `${entry.value}|${entry.source_url}` === event.target.value,
                      );
                      if (contact) {
                        setRecipient(contact.value);
                        setSource(contact.source_url);
                      }
                    }}
                  >
                    <option value="">Choose a sourced email</option>
                    {emailContacts.map((entry) => (
                      <option
                        key={`${entry.value}|${entry.source_url}`}
                        value={`${entry.value}|${entry.source_url}`}
                      >
                        {entry.value}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              <label>
                <span className="field-label">Business email address</span>
                <input
                  type="email"
                  className="input-control"
                  disabled={locked || contactsPending}
                  value={recipient}
                  onChange={(event) => setRecipient(event.target.value)}
                  placeholder={
                    contactsPending ? "Searching for email address…" : "Email address was not found"
                  }
                />
              </label>
              <label>
                <span className="field-label">Public business source page</span>
                <input
                  type="url"
                  className="input-control"
                  disabled={locked || contactsPending}
                  value={source}
                  onChange={(event) => setSource(event.target.value)}
                  placeholder="https://business-website/contact"
                />
              </label>
              {safeUrl(source) && (
                <a
                  className="text-sm underline"
                  href={safeUrl(source)!}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Review public email source ↗
                </a>
              )}
              <p className="form-help">
                If no address is found, supply the full email and its public source page. The
                backend checks the source; it never guesses an address.
              </p>
              <label>
                <span className="field-label">Email subject</span>
                <input
                  className="input-control"
                  disabled={locked}
                  value={subject}
                  onChange={(event) => setSubject(event.target.value)}
                  maxLength={200}
                />
              </label>
              <p className="form-help">
                {gmail?.connected
                  ? `Sending from ${gmail.email}`
                  : "Connect Gmail in Settings before sending."}{" "}
                <a className="underline" href="/settings">
                  Gmail settings
                </a>
              </p>
              {gmail?.detail && <p className="form-help">{gmail.detail}</p>}
            </>
          ) : (
            <label>
              <span className="field-label">Direct profile URL (optional)</span>
              <input
                type="url"
                className="input-control"
                value={profile}
                disabled={locked}
                onChange={(e) => setProfile(e.target.value)}
                placeholder={
                  channel === "tiktok"
                    ? "https://www.tiktok.com/@business"
                    : "https://www.instagram.com/business/"
                }
              />
            </label>
          )}
          <GeminiDraft
            key={business.id}
            placeId={business.id}
            channel={channel}
            ownLabel={label}
            disabled={pending || approvedId !== null}
            hasMessage={!!message.trim() || !!subject.trim()}
            onBusy={setGenerating}
            onGenerated={(draft) => {
              setMessage(draft.message_text);
              if (isEmail) setSubject(draft.subject);
              setCopied(false);
              setChecked(false);
            }}
          />
          <label>
            <span className="field-label">
              {isEmail ? "Email message" : "Exact message you manually sent"}
            </span>
            <textarea
              rows={6}
              className="input-control"
              value={message}
              disabled={locked}
              onChange={(e) => {
                setMessage(e.target.value);
                setCopied(false);
              }}
            />
          </label>
          {!isEmail && (
            <div className="flex gap-2 flex-wrap">
              <Button variant="outline" disabled={locked || !message.trim()} onClick={copy}>
                {copied ? <Check /> : <Copy />}
                {copied ? "Copied" : "Copy Message"}
              </Button>
              {profileUrl && (
                <Button variant="outline" asChild>
                  <a href={profileUrl} target="_blank" rel="noopener noreferrer">
                    <ExternalLink />
                    Open {channel === "tiktok" ? "TikTok" : "Instagram"} Profile
                  </a>
                </Button>
              )}
            </div>
          )}
          <p className="form-help">
            {isEmail
              ? "You must review and approve the exact recipient, subject and message before Gmail sends it. No automatic sending or retries."
              : "Paste, review and send manually. Copying or opening a profile does not mark outreach as sent."}
          </p>
          <Button
            disabled={
              generating ||
              pending ||
              !message.trim() ||
              (isEmail &&
                (contactsPending ||
                  !gmail?.connected ||
                  !recipient.includes("@") ||
                  !source.trim() ||
                  !subject.trim()))
            }
            onClick={() => {
              setChecked(false);
              setConfirm(true);
            }}
          >
            <Send />
            {isEmail
              ? mode === "demo"
                ? "Simulate sending email"
                : "Send email"
              : mode === "demo"
                ? "Simulate sent message"
                : "I sent this message"}
          </Button>
        </div>
      )}
      <ErrorNote error={error} />
      <Dialog
        open={confirm}
        onOpenChange={(open) => {
          if (!pending) setConfirm(open);
        }}
      >
        <DialogContent className="panel-dialog">
          <DialogTitle>
            {isEmail ? "Review and approve email" : "Confirm sent outreach"}
          </DialogTitle>
          <DialogDescription>
            {mode === "demo"
              ? "This records fictional sample outreach only."
              : isEmail
                ? "Approving sends this exact email through your connected Gmail account."
                : "Confirm you manually sent this exact message."}
          </DialogDescription>
          {isEmail && (
            <dl className="panel-meta">
              <div>
                <dt>FROM</dt>
                <dd>{gmail?.email}</dd>
              </div>
              <div>
                <dt>TO</dt>
                <dd>{recipient}</dd>
              </div>
              <div>
                <dt>SUBJECT</dt>
                <dd>{subject}</dd>
              </div>
            </dl>
          )}
          <div className="message-original">{message}</div>
          <label className="confirm-check">
            <input
              type="checkbox"
              checked={checked}
              onChange={(e) => setChecked(e.target.checked)}
            />
            {mode === "demo"
              ? "I understand this is a demo simulation."
              : isEmail
                ? "I verified this public business email and approve this exact email for sending."
                : "I manually sent this exact message to this business."}
          </label>
          <Button disabled={!checked || pending} onClick={markSent}>
            {pending && <Pending />}
            {isEmail
              ? mode === "demo"
                ? "Approve and simulate send"
                : "Approve and send email"
              : "Confirm and record"}
          </Button>
        </DialogContent>
      </Dialog>
    </div>
  );
}
