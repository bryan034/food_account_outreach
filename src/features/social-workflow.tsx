import { useState } from "react";
import { Check, Copy, ExternalLink, Plus, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { ApiError } from "@/lib/api/client";
import { validProfile, type Channel, type Restaurant } from "@/lib/api/types";
import { ErrorNote, messageOf, Pending } from "./common";
import { useWorkspace } from "./workspace";
export function SocialWorkflow({
  placeId = "",
  onRecorded,
}: {
  placeId?: string;
  onRecorded?: () => void;
}) {
  const { api, mode } = useWorkspace();
  const [name, setName] = useState("");
  const [googleId, setGoogleId] = useState(placeId);
  const [existingId, setExistingId] = useState("");
  const [record, setRecord] = useState<Restaurant | null>(null);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [duplicate, setDuplicate] = useState(false);
  const [channel, setChannel] = useState<Channel>("tiktok");
  const [profile, setProfile] = useState("");
  const [message, setMessage] = useState("");
  const [copied, setCopied] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [checked, setChecked] = useState(false);
  const [done, setDone] = useState(false);
  const profileUrl = validProfile(profile, channel);
  async function saveRestaurant() {
    setError("");
    setPending(true);
    try {
      setRecord(
        await api.createRestaurant({ name: name.trim(), google_place_id: googleId.trim() }),
      );
      setDuplicate(false);
    } catch (e) {
      setError(messageOf(e));
      if (e instanceof ApiError && e.status === 409) setDuplicate(true);
    } finally {
      setPending(false);
    }
  }
  async function loadExisting() {
    setError("");
    setPending(true);
    try {
      setRecord(await api.restaurant(Number(existingId)));
    } catch (e) {
      setError(messageOf(e));
    } finally {
      setPending(false);
    }
  }
  async function copy() {
    try {
      await navigator.clipboard.writeText(message);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch {
      setError("Clipboard access is unavailable. Select and copy the message manually.");
    }
  }
  async function markSent() {
    if (!record || !checked) return;
    setError("");
    setPending(true);
    try {
      await api.markSent({
        restaurant_id: record.id,
        channel,
        message_text: message,
        confirmed_sent: true,
      });
      setConfirm(false);
      setDone(true);
      onRecorded?.();
    } catch (e) {
      setError(messageOf(e));
      setConfirm(false);
    } finally {
      setPending(false);
    }
  }
  return (
    <div className="panel-section">
      <h3>{record ? "Prepare manual outreach" : "Add your own business record"}</h3>
      {!record ? (
        <>
          <p className="form-help mb-4">
            Google information above is a live preview, not your saved record. Independently enter
            the business name you want to store.
          </p>
          <div className="form-stack">
            <label>
              <span className="field-label">Your business name</span>
              <input
                className="input-control"
                placeholder="Enter an independently supplied name"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </label>
            <label>
              <span className="field-label">Google Place ID</span>
              <input
                className="input-control"
                value={googleId}
                onChange={(e) => setGoogleId(e.target.value)}
                placeholder="Google Place ID"
              />
            </label>
            <Button onClick={saveRestaurant} disabled={pending || !name.trim() || !googleId.trim()}>
              {pending ? <Pending /> : <Plus />}
              {mode === "demo" ? "Create sample record" : "Create local record"}
            </Button>
          </div>
          <ErrorNote error={error} />
          {duplicate && (
            <p className="form-help">
              This Place ID already exists. There is no lookup-by-Place-ID endpoint, so supply the
              existing local restaurant ID below. We cannot infer it.
            </p>
          )}
          <div className="panel-section">
            <h3>Already have a local record?</h3>
            <div className="flex gap-2">
              <input
                aria-label="Existing local restaurant ID"
                className="input-control"
                type="number"
                min="1"
                step="1"
                placeholder="Local restaurant ID"
                value={existingId}
                onChange={(e) => setExistingId(e.target.value)}
              />
              <Button
                variant="outline"
                onClick={loadExisting}
                disabled={
                  pending || !Number.isInteger(Number(existingId)) || Number(existingId) < 1
                }
              >
                Load record
              </Button>
            </div>
          </div>
        </>
      ) : (
        <>
          <div className="notice-band mb-5">
            <Check size={16} />
            <div>
              <strong>{record.name}</strong>
              <br />
              Your {mode === "demo" ? "sample" : "stored"} business
              <br />
              <span className="break-all">Place ID: {record.google_place_id}</span>
            </div>
          </div>
          {done ? (
            <div className="success-note">
              {mode === "demo"
                ? "Sample outreach recorded in this demo session only. No message was sent."
                : "Your confirmed outreach was recorded. The exact message is now read-only."}
            </div>
          ) : (
            <>
              <div className="form-stack">
                <label>
                  <span className="field-label">Contact channel</span>
                  <select
                    className="input-control"
                    value={channel}
                    onChange={(e) => {
                      setChannel(e.target.value as Channel);
                      setProfile("");
                    }}
                  >
                    <option value="tiktok">TikTok</option>
                    <option value="instagram">Instagram</option>
                  </select>
                </label>
                <label>
                  <span className="field-label">
                    Direct {channel === "tiktok" ? "TikTok" : "Instagram"} profile URL{" "}
                    <span className="secondary-text">(optional)</span>
                  </span>
                  <input
                    className="input-control"
                    type="url"
                    value={profile}
                    onChange={(e) => setProfile(e.target.value)}
                    placeholder={
                      channel === "tiktok"
                        ? "https://www.tiktok.com/@business"
                        : "https://www.instagram.com/business/"
                    }
                  />
                  <p className="form-help">
                    Manually supplied, unverified and not stored. Opening a profile does not confirm
                    the message was sent.
                  </p>
                  {profile && !profileUrl && (
                    <p className="form-help text-destructive">
                      Use a direct HTTPS {channel === "tiktok" ? "tiktok.com" : "instagram.com"}{" "}
                      profile URL.
                    </p>
                  )}
                </label>
                <label>
                  <span className="field-label">Exact message you manually sent</span>
                  <textarea
                    className="input-control"
                    rows={6}
                    value={message}
                    onChange={(e) => {
                      setMessage(e.target.value);
                      setCopied(false);
                    }}
                    placeholder="Hi, I'm Bryan, a Singapore food creator…"
                  />
                  <p className="form-help">
                    Paste, review and send yourself in a browser where you are logged in. Keep the
                    message here identical to what you sent.
                  </p>
                </label>
                <div className="profile-controls">
                  <Button variant="outline" disabled={!message.trim()} onClick={copy}>
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
                <Button
                  disabled={pending || !message.trim()}
                  onClick={() => {
                    setChecked(false);
                    setConfirm(true);
                  }}
                >
                  <Send />
                  {mode === "demo" ? "I sent this message — simulate" : "I sent this message"}
                </Button>
              </div>
              <ErrorNote error={error} />
              <Dialog
                open={confirm}
                onOpenChange={(value) => {
                  if (!pending) setConfirm(value);
                }}
              >
                <DialogContent className="panel-dialog">
                  <DialogTitle>
                    {mode === "demo"
                      ? "Simulate sent confirmation"
                      : "Confirm you sent this message"}
                  </DialogTitle>
                  <DialogDescription>
                    {mode === "demo"
                      ? "This creates a sample record only. No actual social message will be sent."
                      : "This records outreach only. The app does not send a message."}
                  </DialogDescription>
                  <div className="message-original">{message}</div>
                  <label className="confirm-check">
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={(e) => setChecked(e.target.checked)}
                    />
                    {mode === "demo"
                      ? "I understand this is a demo simulation, not actual sent outreach."
                      : "I confirm that I manually sent this exact message to this business on " +
                        (channel === "tiktok" ? "TikTok" : "Instagram") +
                        "."}
                  </label>
                  <div className="flex justify-end gap-2">
                    <Button variant="outline" disabled={pending} onClick={() => setConfirm(false)}>
                      Cancel
                    </Button>
                    <Button disabled={!checked || pending} onClick={markSent}>
                      {pending && <Pending />}
                      {mode === "demo" ? "Record sample outreach" : "Confirm and record sent"}
                    </Button>
                  </div>
                </DialogContent>
              </Dialog>
            </>
          )}
        </>
      )}
    </div>
  );
}
