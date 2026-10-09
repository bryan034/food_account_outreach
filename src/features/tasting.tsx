import { useEffect, useState } from "react";
import { CalendarClock, Navigation } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";

export interface TastingPlan {
  when: string; // local datetime "YYYY-MM-DDTHH:mm"
  address: string;
  notes: string;
}
const KEY = "foodfolio.tasting-plans";

// Tasting plans are kept in this browser only; the backend has no tasting fields yet.
export function loadPlans(): Record<number, TastingPlan> {
  try {
    return JSON.parse(localStorage.getItem(KEY) || "{}");
  } catch {
    return {};
  }
}
export function savePlan(id: number, plan: TastingPlan) {
  const all = loadPlans();
  all[id] = plan;
  localStorage.setItem(KEY, JSON.stringify(all));
}
export function formatTasting(when: string) {
  const d = new Date(when);
  if (Number.isNaN(d.getTime())) return when;
  return d.toLocaleString("en-SG", { dateStyle: "medium", timeStyle: "short" });
}
export function directionsUrl(name: string, address: string, placeId?: string) {
  const params = new URLSearchParams({ api: "1", destination: address || name });
  if (placeId && !placeId.startsWith("demo-")) params.set("destination_place_id", placeId);
  // No origin: Google Maps uses your current location.
  return `https://www.google.com/maps/dir/?${params}`;
}

export function TastingDialog({
  open,
  onOpenChange,
  outreachId,
  name,
  placeId,
  onSaved,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  outreachId: number;
  name: string;
  placeId?: string;
  onSaved: (plan: TastingPlan) => void;
}) {
  const [plan, setPlan] = useState<TastingPlan>({ when: "", address: "", notes: "" });
  useEffect(() => {
    if (open) setPlan(loadPlans()[outreachId] || { when: "", address: "", notes: "" });
  }, [open, outreachId]);
  function save() {
    savePlan(outreachId, plan);
    onSaved(plan);
    onOpenChange(false);
  }
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="panel-dialog">
        <DialogTitle>Plan your tasting</DialogTitle>
        <DialogDescription>{name} · saved on this device only</DialogDescription>
        <div className="form-stack">
          <label>
            <span className="field-label">Date and time</span>
            <input
              type="datetime-local"
              className="input-control"
              value={plan.when}
              onChange={(e) => setPlan({ ...plan, when: e.target.value })}
            />
          </label>
          <label>
            <span className="field-label">Address</span>
            <input
              className="input-control"
              placeholder="e.g. 42 Duxton Road, Singapore"
              value={plan.address}
              onChange={(e) => setPlan({ ...plan, address: e.target.value })}
            />
          </label>
          <label>
            <span className="field-label">Notes</span>
            <textarea
              className="input-control min-h-20"
              placeholder="Who to ask for, dishes to try, filming plans…"
              value={plan.notes}
              onChange={(e) => setPlan({ ...plan, notes: e.target.value })}
            />
          </label>
          <div className="flex gap-2 flex-wrap">
            <Button onClick={save} disabled={!plan.when}>
              <CalendarClock />
              Save tasting
            </Button>
            <Button variant="outline" asChild>
              <a
                href={directionsUrl(name, plan.address, placeId)}
                target="_blank"
                rel="noopener noreferrer"
              >
                <Navigation />
                Directions from my location
              </a>
            </Button>
          </div>
          <p className="form-help">
            Directions open in Google Maps in a new tab, starting from your current location.
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
}
