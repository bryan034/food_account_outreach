import { useState, type FormEvent } from "react";
import {
  ArrowRight,
  Coffee,
  Compass,
  Info,
  Leaf,
  MapPin,
  Search,
  Sparkles,
  Store,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { demoDiscovery } from "@/lib/api/demo";
import type { Discovery, Place } from "@/lib/api/types";
import cafeImage from "@/assets/cafe-editorial.jpg";
import { ErrorNote, messageOf, Pending } from "./common";
import { PageFooter } from "./shell";
import { useWorkspace } from "./workspace";
export function DiscoverPage() {
  const { api, mode } = useWorkspace();
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<Discovery | null>(null);
  const [selected, setSelected] = useState<Place | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [searched, setSearched] = useState(false);
  const displayed = result || (mode === "demo" ? demoDiscovery : null);
  async function search(e: FormEvent) {
    e.preventDefault();
    if (pending || !query.trim()) return;
    setPending(true);
    setError("");
    setSearched(true);
    try {
      setResult(await api.discover(query.trim()));
    } catch (e) {
      setError(messageOf(e));
      setResult(null);
    } finally {
      setPending(false);
    }
  }
  return (
    <div className="page">
      <div className="heading-row">
        <div>
          <div className="eyebrow">A little discovery goes a long way</div>
          <h1 className="page-heading">Find your next food collaboration.</h1>
          <p className="page-description">
            Discover Singapore food spots worth a conversation. Start with a neighbourhood or a
            craving.
          </p>
        </div>
      </div>
      <form className="search-section" onSubmit={search}>
        <label className="field-label" htmlFor="business-search">
          What are you looking for?
        </label>
        <div className="search-row">
          <div className="input-wrap">
            <Search size={18} />
            <input
              id="business-search"
              className="input-control search-input"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="cafés in Tanjong Pagar, Singapore"
            />
          </div>
          <Button className="search-button" type="submit" disabled={pending || !query.trim()}>
            {pending ? <Pending /> : <Search />}Search
          </Button>
        </div>
        <p className="search-helper">
          <Info size={12} />
          {mode === "demo"
            ? "Sample results only. No Google requests are made in Demo Mode."
            : "Search uses a paid Google lookup. It runs only when you press Search."}
        </p>
      </form>
      <div className="discovery-tip">
        <div className="tip-content">
          <span className="eyebrow flex gap-2 items-center mb-0">
            <Leaf size={13} />
            Small places. Big possibilities.
          </span>
          <h2 className="tip-title">Your next favourite spot is out there.</h2>
          <p>
            From neighbourhood cafés to hidden hawker gems,
            <br className="hidden lg:block" /> find the businesses that fit your food story.
          </p>
        </div>
        <img
          className="tip-image"
          src={cafeImage}
          alt="Kaya toast, iced coffee and pandan cake on a café table"
          width={1024}
          height={640}
        />
      </div>
      <ErrorNote error={error} />
      <div className="section-header">
        <h2>
          {mode === "demo"
            ? "Businesses to explore"
            : searched
              ? "Discovery results"
              : "Your next discovery"}
          {displayed && <span className="count">{displayed.places.length} results</span>}
        </h2>
        <div className="source-label">
          {mode === "demo" ? (
            <>
              <Sparkles size={12} />
              Sample previews · Google Maps format
            </>
          ) : (
            <>
              Powered by <span className="google-word">Google Maps</span>
            </>
          )}
        </div>
      </div>
      {pending ? (
        <div className="results-grid" aria-label="Loading business results">
          {[0, 1, 2, 3].map((i) => (
            <div className="skeleton-card" key={i} />
          ))}
        </div>
      ) : displayed?.places.length ? (
        <div className="results-grid">
          {displayed.places.map((place, i) => (
            <article className="business-card" key={place.id}>
              <div className="business-top">
                <div className="business-icon">
                  {i % 3 === 0 ? (
                    <Coffee size={19} />
                  ) : i % 3 === 1 ? (
                    <Store size={19} />
                  ) : (
                    <Leaf size={19} />
                  )}
                </div>
                <div className="min-w-0">
                  <h3>{place.display_name.text}</h3>
                  <p className="category">
                    {place.primary_type?.replaceAll("_", " ") || "Category unavailable"}
                  </p>
                </div>
              </div>
              <p className="address-line">
                <MapPin size={13} />
                {place.formatted_address || "Address unavailable"}
              </p>
              <div className="business-bottom">
                <span className="operational">
                  {place.business_status === "OPERATIONAL"
                    ? "Operational"
                    : place.business_status?.replaceAll("_", " ") || "Status unavailable"}
                </span>
                <Button
                  className="detail-button"
                  variant="ghost"
                  onClick={() => setSelected(place)}
                  aria-label={`View ${place.display_name.text} details`}
                >
                  View details
                  <ArrowRight size={13} />
                </Button>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="empty-state">
          <Compass size={30} />
          <h3>
            {error
              ? "Discovery unavailable"
              : searched
                ? "No new businesses found"
                : "Where should we explore?"}
          </h3>
          <p>
            {error
              ? "Check the message above and search again when ready."
              : searched
                ? "Try another neighbourhood or food category. Previously contacted businesses are filtered by your backend."
                : "Enter a neighbourhood, cuisine or kind of food business to begin."}
          </p>
        </div>
      )}
      <div className="result-note">
        <Info size={13} className="shrink-0 mt-0.5" />
        <span>
          Discovery results are previews, not saved records. Only businesses you explicitly add
          become local records.
          {displayed?.next_page_token && (
            <>
              <br />A next-page token was returned and preserved. Additional pages are not
              requested; the backend does not accept this token yet.
            </>
          )}
        </span>
      </div>
      <PageFooter />
      <Dialog
        open={!!selected}
        onOpenChange={(open) => {
          if (!open) setSelected(null);
        }}
      >
        <DialogContent className="panel-dialog">
          <DialogTitle>{selected?.display_name.text}</DialogTitle>
          <DialogDescription>
            {mode === "demo"
              ? "Sample Google-format preview · not a saved business"
              : "Live Google Maps preview · not a saved business"}
          </DialogDescription>
          {selected && (
            <>
              <dl className="panel-meta">
                <div>
                  <dt>ADDRESS</dt>
                  <dd>{selected.formatted_address || "Unavailable"}</dd>
                </div>
                <div>
                  <dt>CATEGORY</dt>
                  <dd className="capitalize">
                    {selected.primary_type?.replaceAll("_", " ") || "Unavailable"}
                  </dd>
                </div>
                <div>
                  <dt>BUSINESS STATUS</dt>
                  <dd>{selected.business_status || "Unavailable"}</dd>
                </div>
              </dl>
              <div className="panel-section">
                <h3>Opening hours</h3>
                {selected.regular_opening_hours?.weekday_descriptions?.length ? (
                  <ul className="text-sm space-y-1">
                    {selected.regular_opening_hours.weekday_descriptions.map((d) => (
                      <li key={d}>{d}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="form-help">Opening hours are not available for this business.</p>
                )}
              </div>
              <div className="panel-section">
                <h3>
                  Contact information <span className="coming-badge ml-2">Coming later</span>
                </h3>
                <p className="form-help">
                  Website enrichment and contact storage are not connected. No contacts have been
                  extracted or verified. Email outreach is a future capability.
                </p>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
