import { useEffect, useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { ErrorNote, messageOf, Pending } from "./common";
import { useWorkspace } from "./workspace";

export function CreatorProfileSettings() {
  const { api, mode } = useWorkspace();
  const [name, setName] = useState("Bryan");
  const [url, setUrl] = useState("https://www.tiktok.com/@bbbrrr9");
  const [views, setViews] = useState("146000");
  const [shares, setShares] = useState("600");
  const [minimum, setMinimum] = useState("1000");
  const [confirmed, setConfirmed] = useState(false);
  const [pending, setPending] = useState(true);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");
  const [modelStatus, setModelStatus] = useState("");
  useEffect(() => {
    let active = true;
    setPending(true);
    setError("");
    setSaved("");
    setConfirmed(false);
    Promise.all([api.creatorProfile(), api.geminiStatus()])
      .then(([profile, status]) => {
        if (!active) return;
        setName(profile?.creator_name || "Bryan");
        setUrl(profile?.tiktok_url || "https://www.tiktok.com/@bbbrrr9");
        setViews(String(profile?.views_over ?? 146000));
        setShares(String(profile?.shares_over ?? 600));
        setMinimum(String(profile?.minimum_video_views ?? 1000));
        setSaved(
          profile
            ? `Statistics last confirmed: ${new Date(profile.confirmed_at).toLocaleString()}`
            : "No creator profile saved yet.",
        );
        setModelStatus(
          status.configured
            ? `Drafting model: ${status.model}`
            : "Gemini is not configured. Set GEMINI_API_KEY in backend .env and recreate it.",
        );
      })
      .catch((error) => {
        if (active) setError(messageOf(error));
      })
      .finally(() => {
        if (active) setPending(false);
      });
    return () => {
      active = false;
    };
  }, [api]);
  async function save(event: FormEvent) {
    event.preventDefault();
    if (!confirmed || pending) return;
    setPending(true);
    setError("");
    try {
      const result = await api.saveCreatorProfile({
        creator_name: name,
        tiktok_url: url,
        views_over: Number(views),
        shares_over: Number(shares),
        minimum_video_views: Number(minimum),
        statistics_confirmed: true,
      });
      setSaved(`Statistics saved and confirmed: ${new Date(result.confirmed_at).toLocaleString()}`);
      setConfirmed(false);
    } catch (error) {
      setError(messageOf(error));
    } finally {
      setPending(false);
    }
  }
  return (
    <section className="settings-section settings-grid">
      <div>
        <h2>Creator profile and Gemini drafts</h2>
        <p>Manually confirmed facts, never invented statistics.</p>
      </div>
      <form className="settings-content form-stack" onSubmit={save} onChange={() => setSaved("")}>
        <label>
          <span className="field-label">Creator name</span>
          <input
            className="input-control"
            value={name}
            disabled={pending}
            required
            maxLength={100}
            onChange={(event) => {
              setName(event.target.value);
              setConfirmed(false);
            }}
          />
        </label>
        <label>
          <span className="field-label">Your TikTok profile</span>
          <input
            className="input-control"
            type="url"
            value={url}
            disabled={pending}
            required
            onChange={(event) => {
              setUrl(event.target.value);
              setConfirmed(false);
            }}
          />
        </label>
        <label>
          <span className="field-label">Total views — over</span>
          <input
            className="input-control"
            type="number"
            min={0}
            step={1}
            value={views}
            disabled={pending}
            required
            onChange={(event) => {
              setViews(event.target.value);
              setConfirmed(false);
            }}
          />
        </label>
        <label>
          <span className="field-label">Total shares — more than</span>
          <input
            className="input-control"
            type="number"
            min={0}
            step={1}
            value={shares}
            disabled={pending}
            required
            onChange={(event) => {
              setShares(event.target.value);
              setConfirmed(false);
            }}
          />
        </label>
        <label>
          <span className="field-label">Minimum views on every video</span>
          <input
            className="input-control"
            type="number"
            min={0}
            step={1}
            value={minimum}
            disabled={pending}
            required
            onChange={(event) => {
              setMinimum(event.target.value);
              setConfirmed(false);
            }}
          />
        </label>
        <label className="flex gap-2">
          <input
            type="checkbox"
            checked={confirmed}
            disabled={pending}
            onChange={(event) => setConfirmed(event.target.checked)}
          />
          <span>
            I confirm these statistics are accurate, including the claim about every video.
          </span>
        </label>
        <p className="form-help">
          Drafts offer a complimentary tasting for one TikTok review, hosted meal disclosed, no
          creator fee. They always end with Best, Bryan's dining room.
        </p>
        <Button type="submit" disabled={pending || !confirmed}>
          {pending && <Pending />}Save creator profile
        </Button>
        <ErrorNote error={error} />
        {saved && (
          <p role="status" className="form-help">
            {saved}
          </p>
        )}
        <p className="form-help">{modelStatus}</p>
        <p className="form-help">
          {mode === "demo"
            ? "Demo settings are ephemeral. No Gemini requests are made."
            : "Your confirmed creator profile and restaurant facts go to Gemini for writing. Python still inserts the exact statistics, offer and signature. Do not include private information."}
        </p>
      </form>
    </section>
  );
}
