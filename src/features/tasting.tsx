import { useEffect, useState } from "react";
import { CalendarClock, Navigation } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import type { TastingInput } from "@/lib/api/types";
import { ErrorNote, messageOf, Pending } from "./common";

export interface TastingPlan {
  when: string;
  address: string;
  notes: string;
}
export function planFromApi(plan: TastingInput): TastingPlan {
  // datetime-local has no timezone. Display and submit Singapore time explicitly.
  const when = new Date(Date.parse(plan.scheduled_at) + 8 * 3600000).toISOString().slice(0, 16);
  return { when, address: plan.address, notes: plan.notes };
}
export function planToApi(plan: TastingPlan): TastingInput {
  return {
    scheduled_at: new Date(plan.when + ":00+08:00").toISOString(),
    address: plan.address.trim(),
    notes: plan.notes,
  };
}
export function formatTasting(when: string) {
  const date = new Date(when + ":00+08:00");
  return Number.isNaN(date.getTime())
    ? when
    : date.toLocaleString("en-SG", {
        timeZone: "Asia/Singapore",
        dateStyle: "medium",
        timeStyle: "short",
      });
}
export function directionsUrl(name: string, address: string) {
  const params = new URLSearchParams({
    api: "1",
    destination: address || name,
    travelmode: "transit",
  });
  return `https://www.google.com/maps/dir/?${params}`;
}
export function TastingDialog({
  open,
  onOpenChange,
  name,
  initialPlan,
  onSaved,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  name: string;
  initialPlan?: TastingInput | null | undefined;
  onSaved: (plan: TastingInput) => Promise<void>;
}) {
  const [plan, setPlan] = useState<TastingPlan>({ when: "", address: "", notes: "" });
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    if (open) {
      setPlan(initialPlan ? planFromApi(initialPlan) : { when: "", address: "", notes: "" });
      setError("");
    }
  }, [open, initialPlan]);
  async function save() {
    setPending(true);
    setError("");
    try {
      await onSaved(planToApi(plan));
      onOpenChange(false);
    } catch (error) {
      setError(messageOf(error));
    } finally {
      setPending(false);
    }
  }
  return (
    <Dialog
      open={open}
      onOpenChange={(open) => {
        if (!pending) onOpenChange(open);
      }}
    >
      <DialogContent className="panel-dialog">
        <DialogTitle>Plan your tasting</DialogTitle>
        <DialogDescription>{name} · date and time in Singapore (SGT)</DialogDescription>
        <div className="form-stack">
          <label>
            <span className="field-label">Date and time · SGT</span>
            <input
              type="datetime-local"
              className="input-control"
              value={plan.when}
              onChange={(e) => setPlan({ ...plan, when: e.target.value })}
            />
          </label>
          <label>
            <span className="field-label">Tasting address</span>
            <input
              className="input-control"
              value={plan.address}
              onChange={(e) => setPlan({ ...plan, address: e.target.value })}
              placeholder="Enter the agreed venue address"
            />
          </label>
          <label>
            <span className="field-label">Notes</span>
            <textarea
              className="input-control min-h-20"
              value={plan.notes}
              onChange={(e) => setPlan({ ...plan, notes: e.target.value })}
            />
          </label>
          <ErrorNote error={error} />
          <div className="flex gap-2 flex-wrap">
            <Button disabled={pending || !plan.when || !plan.address.trim()} onClick={save}>
              {pending ? <Pending /> : <CalendarClock />}Save tasting
            </Button>
            {plan.address.trim() && (
              <Button variant="outline" asChild>
                <a
                  href={directionsUrl(name, plan.address)}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <Navigation />
                  Directions from my location
                </a>
              </Button>
            )}
          </div>
          <p className="form-help">
            Google Maps opens transit directions and asks for your location if needed. Saving
            persists the plan through your selected workspace API.
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
}
