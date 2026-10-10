import { useState } from "react";
import { Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { Channel, DraftInput, GeneratedDraft } from "@/lib/api/types";
import { ErrorNote, messageOf, Pending } from "./common";
import { useWorkspace } from "./workspace";

export function GeminiDraft({
  placeId,
  channel,
  ownLabel,
  disabled,
  hasMessage,
  onGenerated,
  onBusy,
}: {
  placeId: string;
  channel: Channel;
  ownLabel: string;
  disabled: boolean;
  hasMessage: boolean;
  onGenerated: (draft: GeneratedDraft) => void;
  onBusy: (busy: boolean) => void;
}) {
  const { api, mode } = useWorkspace();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState(ownLabel);
  const [kind, setKind] = useState<DraftInput["business_kind"]>("food_business");
  const [detail, setDetail] = useState("");
  const [source, setSource] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [replace, setReplace] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [generated, setGenerated] = useState("");
  async function generate() {
    if (disabled || pending || !name.trim() || !confirmed || (hasMessage && !replace)) return;
    setPending(true);
    onBusy(true);
    setError("");
    try {
      const result = await api.generateDraft({
        request_id: crypto.randomUUID(),
        google_place_id: placeId,
        restaurant_name: name.trim(),
        business_kind: kind,
        channel,
        feature_detail: detail.trim(),
        source_url: source.trim() || null,
        facts_confirmed: true,
      });
      onGenerated(result);
      setReplace(false);
      setGenerated(
        mode === "demo"
          ? "Sample draft filled. No Gemini call was made."
          : `Draft saved and filled using ${result.model}. Review and edit before sending.`,
      );
    } catch (error) {
      setError(messageOf(error));
    } finally {
      setPending(false);
      onBusy(false);
    }
  }
  return (
    <section className="panel-section">
      <Button
        type="button"
        variant="outline"
        disabled={disabled || pending}
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        Draft with Gemini
      </Button>
      {open && (
        <fieldset className="panel-section form-stack" disabled={disabled || pending}>
          <legend>Gemini-assisted draft</legend>
          <label>
            <span className="field-label">Confirmed business name for greeting</span>
            <input
              className="input-control"
              value={name}
              maxLength={255}
              onChange={(event) => {
                setName(event.target.value);
                setConfirmed(false);
              }}
              placeholder="Name from your own knowledge or the business website"
            />
          </label>
          <label>
            <span className="field-label">Confirmed business type</span>
            <select
              className="input-control"
              value={kind}
              onChange={(event) => {
                setKind(event.target.value as DraftInput["business_kind"]);
                setConfirmed(false);
              }}
            >
              <option value="food_business">Food business</option>
              <option value="cafe">Café</option>
              <option value="restaurant">Restaurant</option>
              <option value="bakery">Bakery</option>
            </select>
          </label>
          <label>
            <span className="field-label">What you want to feature (optional)</span>
            <input
              className="input-control"
              value={detail}
              maxLength={400}
              onChange={(event) => {
                setDetail(event.target.value);
                setConfirmed(false);
              }}
              placeholder="your specialty coffee and brunch menu at Siglap V"
            />
          </label>
          <label>
            <span className="field-label">Restaurant fact source (optional)</span>
            <input
              className="input-control"
              type="url"
              value={source}
              onChange={(event) => {
                setSource(event.target.value);
                setConfirmed(false);
              }}
              placeholder="https://business-website/menu"
            />
          </label>
          <p className="form-help">
            Use facts you independently know or checked on the public business website. This feature
            does not fetch or verify that page. Avoid private information. Without a detail, the
            draft uses only the confirmed business type.
          </p>
          <label className="flex gap-2">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(event) => setConfirmed(event.target.checked)}
            />
            <span>I confirm the name, type and any feature detail are factual.</span>
          </label>
          {hasMessage && (
            <label className="flex gap-2">
              <input
                type="checkbox"
                checked={replace}
                onChange={(event) => setReplace(event.target.checked)}
              />
              <span>Replace my current draft message and email subject.</span>
            </label>
          )}
          <Button
            type="button"
            disabled={disabled || pending || !name.trim() || !confirmed || (hasMessage && !replace)}
            onClick={generate}
          >
            {pending ? <Pending /> : <Sparkles />}
            {mode === "demo" ? "Generate sample draft" : "Generate with Gemini"}
          </Button>
          <p className="form-help">
            {mode === "demo"
              ? "No live model calls in Demo Mode."
              : "Each click makes one Gemini writing request using your confirmed creator profile and restaurant facts, and may incur charges. Save your creator profile in Settings first."}{" "}
            Generation never approves or sends outreach.
          </p>
          <ErrorNote error={error} />
          {generated && (
            <p role="status" className="form-help">
              {generated}
            </p>
          )}
        </fieldset>
      )}
    </section>
  );
}
