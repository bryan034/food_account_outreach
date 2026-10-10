import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import type { Restaurant } from "@/lib/api/types";
import { ErrorNote, messageOf, Pending } from "./common";
import { useWorkspace } from "./workspace";

/** Editable CRM notes, separate from immutable sent-message evidence. */
export function BusinessNotes({
  restaurant,
  liveName,
  onSaved,
}: {
  restaurant: Restaurant;
  liveName?: string | undefined;
  onSaved: (restaurant: Restaurant) => void;
}) {
  const { api } = useWorkspace();
  const [name, setName] = useState(restaurant.name === "Contacted business" ? "" : restaurant.name);
  const [category, setCategory] = useState(restaurant.category || "");
  const [address, setAddress] = useState(restaurant.address || "");
  const [area, setArea] = useState(restaurant.area || "");
  const [website, setWebsite] = useState(restaurant.website_url || "");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  async function save(event: FormEvent) {
    event.preventDefault();
    if (pending) return;
    setPending(true);
    setError("");
    setSaved(false);
    try {
      const updated = await api.updateRestaurant(restaurant.id, {
        name: name.trim() || "Contacted business",
        category: category.trim() || null,
        address: address.trim() || null,
        area: area.trim() || null,
        website_url: website.trim() || null,
      });
      onSaved(updated);
      setSaved(true);
    } catch (error) {
      setError(messageOf(error));
    } finally {
      setPending(false);
    }
  }

  return (
    <form className="panel-section form-stack" onSubmit={save}>
      <h3>Business notes</h3>
      <label>
        <span className="field-label">Business name / your label</span>
        <input
          className="input-control"
          value={name}
          disabled={pending}
          maxLength={255}
          placeholder={liveName || "Current restaurant name unavailable"}
          onChange={(event) => {
            setName(event.target.value);
            setSaved(false);
          }}
        />
      </label>
      {liveName && restaurant.name === "Contacted business" && (
        <p className="form-help">
          Default name shown above is from{" "}
          <span
            translate="no"
            style={{
              fontFamily: "sans-serif",
              fontWeight: 400,
              fontSize: 12,
              color: "#5e5e5e",
              whiteSpace: "nowrap",
              letterSpacing: "normal",
            }}
          >
            Google Maps
          </span>
          .
        </p>
      )}
      <p className="form-help">
        Leave the name blank to display the current Google restaurant name. Enter your own business
        notes below, not copied Google listing data.
      </p>
      <label>
        <span className="field-label">Category</span>
        <input
          className="input-control"
          value={category}
          disabled={pending}
          maxLength={100}
          onChange={(event) => {
            setCategory(event.target.value);
            setSaved(false);
          }}
        />
      </label>
      <label>
        <span className="field-label">Area</span>
        <input
          className="input-control"
          value={area}
          disabled={pending}
          maxLength={100}
          onChange={(event) => {
            setArea(event.target.value);
            setSaved(false);
          }}
        />
      </label>
      <label>
        <span className="field-label">Business address</span>
        <input
          className="input-control"
          value={address}
          disabled={pending}
          maxLength={2000}
          onChange={(event) => {
            setAddress(event.target.value);
            setSaved(false);
          }}
        />
      </label>
      <label>
        <span className="field-label">Business website</span>
        <input
          className="input-control"
          type="url"
          value={website}
          disabled={pending}
          onChange={(event) => {
            setWebsite(event.target.value);
            setSaved(false);
          }}
        />
      </label>
      <ErrorNote error={error} />
      <Button type="submit" disabled={pending}>
        {pending && <Pending />}Save business notes
      </Button>
      {saved && <p role="status">Business notes saved.</p>}
    </form>
  );
}
