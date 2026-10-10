import { useEffect, useState } from "react";
import {
  ArrowRight,
  ChevronLeft,
  ChevronRight,
  Info,
  MessageSquare,
  Plus,
  CalendarClock,
  Navigation,
  RefreshCw,
  Undo2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import {
  reverts,
  statuses,
  transitions,
  type Outreach,
  type Restaurant,
  type Status,
  type TastingInput,
} from "@/lib/api/types";
import { ErrorNote, formatDate, messageOf, Pending, StatusBadge } from "./common";
import { PageFooter } from "./shell";
import { SocialWorkflow } from "./social-workflow";
import { BusinessNotes } from "./business-notes";
import { useWorkspace } from "./workspace";
import {
  directionsUrl,
  formatTasting,
  planFromApi,
  TastingDialog,
  type TastingPlan,
} from "./tasting";
const pageSize = 10;
export function OutreachPage() {
  const { api, mode } = useWorkspace();
  const [rows, setRows] = useState<Outreach[]>([]);
  const [names, setNames] = useState<Record<number, Restaurant>>({});
  const [liveNames, setLiveNames] = useState<Record<number, string>>({});
  const [lookupErrors, setLookupErrors] = useState<Record<number, string>>({});
  const [pending, setPending] = useState(true);
  const [error, setError] = useState("");
  const [offset, setOffset] = useState(0);
  const [filter, setFilter] = useState<Status | "all">("all");
  const [selected, setSelected] = useState<Outreach | null>(null);
  const [updating, setUpdating] = useState(false);
  const [detailError, setDetailError] = useState("");
  const [compose, setCompose] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const plans: Record<number, TastingPlan> = Object.fromEntries(
    rows.filter((row) => row.tasting).map((row) => [row.id, planFromApi(row.tasting!)]),
  );
  const [planning, setPlanning] = useState(false);
  const [emailConfirm, setEmailConfirm] = useState(false);
  const [emailApproved, setEmailApproved] = useState(false);
  function businessName(id: number) {
    const restaurant = names[id];
    if (!restaurant) return "Business details unavailable";
    return restaurant.name === "Contacted business"
      ? liveNames[id] || "Restaurant name unavailable"
      : restaurant.name;
  }
  async function sendApprovedEmail() {
    if (!selected || !emailApproved || updating) return;
    setUpdating(true);
    setDetailError("");
    try {
      const updated = await api.sendEmail(selected.id);
      setSelected(updated);
      setRows((previous) => previous.map((row) => (row.id === updated.id ? updated : row)));
      setEmailConfirm(false);
    } catch (error) {
      setDetailError(messageOf(error));
    } finally {
      setUpdating(false);
    }
  }
  useEffect(() => {
    let active = true;
    setPending(true);
    setError("");
    api
      .outreach(offset, pageSize)
      .then(async (data) => {
        if (!active) return;
        setRows(data);
        const ids = [...new Set(data.map((r) => r.restaurant_id))];
        const results = await Promise.all(
          ids.map(async (id) => {
            try {
              const record = await api.restaurant(id);
              // Google names are display-only and are never written back to PostgreSQL.
              let liveName: string | undefined;
              if (record.name === "Contacted business") {
                try {
                  liveName = (await api.placeDetails(record.google_place_id, true)).display_name
                    .text;
                } catch {
                  // A failed Google lookup must not hide the saved outreach record.
                }
              }
              return { id, record, liveName };
            } catch (e) {
              return { id, error: messageOf(e) };
            }
          }),
        );
        if (!active) return;
        const resolved: Record<number, Restaurant> = {};
        const currentNames: Record<number, string> = {};
        const failures: Record<number, string> = {};
        for (const r of results) {
          if (r.record) resolved[r.id] = r.record;
          else failures[r.id] = r.error || "Restaurant unavailable";
          if (r.liveName) currentNames[r.id] = r.liveName;
        }
        setNames(resolved);
        setLiveNames(currentNames);
        setLookupErrors(failures);
      })
      .catch((e) => {
        if (active) {
          setError(messageOf(e));
          setRows([]);
        }
      })
      .finally(() => {
        if (active) setPending(false);
      });
    return () => {
      active = false;
    };
  }, [api, offset, refresh]);
  async function change(status: Status) {
    if (!selected || updating) return;
    if (status === "tasting") {
      setPlanning(true);
      return;
    }
    setUpdating(true);
    setDetailError("");
    try {
      const updated = await api.changeStatus(selected.id, status);
      setSelected(updated);
      setRows((prev) => prev.map((row) => (row.id === updated.id ? updated : row)));
    } catch (e) {
      setDetailError(messageOf(e));
    } finally {
      setUpdating(false);
    }
  }
  async function saveTasting(plan: TastingInput) {
    if (!selected) return;
    const updated = await api.changeStatus(selected.id, "tasting", plan);
    setSelected(updated);
    setRows((previous) => previous.map((row) => (row.id === updated.id ? updated : row)));
  }
  const visible = filter === "all" ? rows : rows.filter((r) => r.status === filter);
  return (
    <div className="page">
      <div className="heading-row">
        <div>
          <div className="eyebrow">From first hello to a shared table</div>
          <h1 className="page-heading">Your collaborations.</h1>
          <p className="page-description">
            Keep every conversation and collaboration in one place.
          </p>
        </div>
        <Button onClick={() => setCompose(true)}>
          <Plus />
          Record outreach
        </Button>
      </div>
      {mode === "demo" && (
        <div className="notice-band mt-6">
          <Info size={15} />
          <span>
            All records and messages below are fictional samples. They do not represent actual
            outreach.
          </span>
        </div>
      )}
      <div className="filter-row" aria-label="Filter outreach by status">
        <span className="text-xs text-muted-foreground mr-3">Status</span>
        {(["all", ...statuses] as const).map((s) => (
          <Button
            key={s}
            variant="ghost"
            className={`filter-button capitalize ${filter === s ? "filter-active" : ""}`}
            onClick={() => setFilter(s)}
            aria-pressed={filter === s}
          >
            {s === "all" ? "All outreach" : s.replaceAll("_", " ")}
          </Button>
        ))}
        <Button
          className="ml-auto"
          variant="ghost"
          size="icon"
          title="Refresh outreach"
          aria-label="Refresh outreach"
          disabled={pending}
          onClick={() => setRefresh((r) => r + 1)}
        >
          <RefreshCw />
        </Button>
      </div>
      <ErrorNote error={error} />
      {pending ? (
        <div className="loading-state">
          <Pending />
          Loading outreach and restaurant details…
        </div>
      ) : visible.length ? (
        <div className="table-wrap">
          <table className="outreach-table">
            <thead>
              <tr>
                <th>Restaurant</th>
                <th>Channel</th>
                <th>Status</th>
                <th>Sent at · SGT</th>
                <th className="text-right">Details</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((row) => (
                <tr key={row.id}>
                  <td>
                    <div className="table-name">{businessName(row.restaurant_id)}</div>
                    {names[row.restaurant_id]?.name === "Contacted business" &&
                      liveNames[row.restaurant_id] && (
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
                      )}
                    {lookupErrors[row.restaurant_id] && (
                      <div className="table-id text-destructive">
                        {lookupErrors[row.restaurant_id]}
                      </div>
                    )}
                  </td>
                  <td className="capitalize">
                    {row.channel === "email"
                      ? "Email"
                      : row.channel === "tiktok"
                        ? "TikTok"
                        : "Instagram"}
                  </td>
                  <td>
                    <StatusBadge status={row.status} />
                    {row.status === "tasting" && plans[row.id]?.when && (
                      <div className="table-id mt-1 flex items-center gap-1">
                        <CalendarClock size={11} />
                        {formatTasting(plans[row.id]!.when)}
                      </div>
                    )}
                  </td>
                  <td className="text-muted-foreground">{formatDate(row.sent_at)}</td>
                  <td className="text-right">
                    <Button
                      variant="ghost"
                      className="detail-button"
                      aria-label={`View outreach for ${businessName(row.restaurant_id)}`}
                      onClick={() => {
                        setSelected(row);
                        setDetailError("");
                      }}
                    >
                      View details
                      <ArrowRight />
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="empty-state">
          <MessageSquare size={30} />
          <h3>
            {error
              ? "Outreach could not be loaded"
              : filter === "all"
                ? "No outreach yet"
                : "No matching outreach on this page"}
          </h3>
          <p>
            {filter === "all"
              ? "Sent emails and explicitly confirmed manual outreach will appear here."
              : "Try a different status or navigate to another page."}
          </p>
          {!error && filter === "all" && (
            <Button variant="outline" className="mt-5" onClick={() => setCompose(true)}>
              <Plus />
              Record manual outreach
            </Button>
          )}
        </div>
      )}
      <div className="pagination-row">
        <div>
          Page {Math.floor(offset / pageSize) + 1} · {visible.length}{" "}
          {filter === "all" ? "records" : "matching records"}
          <p className="mt-1 text-[10px]">
            Status filters apply to this page. The backend does not return a total count.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span>{pageSize} per page</span>
          <Button
            size="sm"
            variant="outline"
            disabled={offset === 0 || pending}
            onClick={() => setOffset((o) => Math.max(0, o - pageSize))}
          >
            <ChevronLeft />
            Previous
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={rows.length < pageSize || pending || !!error}
            onClick={() => setOffset((o) => o + pageSize)}
          >
            Next
            <ChevronRight />
          </Button>
        </div>
      </div>
      <div className="notice-band mt-8">
        <Info size={15} />
        <span>
          Business notes and tasting plans can be edited. The original message and sent history stay
          unchanged. Unnamed businesses use a live Google name lookup when this page loads.
        </span>
      </div>
      <PageFooter />
      <Dialog
        open={!!selected}
        onOpenChange={(open) => {
          if (!open && !updating && !planning && !emailConfirm) setSelected(null);
        }}
      >
        <DialogContent className="panel-dialog">
          <DialogTitle>
            {selected ? businessName(selected.restaurant_id) : "Outreach details"}
          </DialogTitle>
          <DialogDescription>
            {mode === "demo" ? "Fictional sample outreach record" : "Stored outreach record"} ·
            exact message is read-only
          </DialogDescription>
          {selected && (
            <>
              {names[selected.restaurant_id] && (
                <BusinessNotes
                  key={selected.restaurant_id}
                  restaurant={names[selected.restaurant_id]!}
                  liveName={liveNames[selected.restaurant_id]}
                  onSaved={(record) => {
                    setNames((previous) => ({ ...previous, [record.id]: record }));
                    if (record.name === "Contacted business") setRefresh((value) => value + 1);
                  }}
                />
              )}
              <dl className="panel-meta">
                <div>
                  <dt>CHANNEL</dt>
                  <dd>
                    {selected.channel === "email"
                      ? "Email"
                      : selected.channel === "tiktok"
                        ? "TikTok"
                        : "Instagram"}
                  </dd>
                </div>
                <div>
                  <dt>SENT AT · SGT</dt>
                  <dd>{formatDate(selected.sent_at)}</dd>
                </div>
                <div>
                  <dt>CURRENT STATUS</dt>
                  <dd>
                    <StatusBadge status={selected.status} />
                  </dd>
                </div>
              </dl>
              {selected.email && (
                <div className="panel-section">
                  <h3>Email details</h3>
                  <p className="text-sm">From: {selected.email.sender}</p>
                  <p className="text-sm">To: {selected.email.recipient}</p>
                  <p className="text-sm">Subject: {selected.email.subject}</p>
                  {selected.status === "email_approved" && (
                    <Button
                      className="mt-3"
                      disabled={updating}
                      onClick={() => {
                        setEmailApproved(false);
                        setEmailConfirm(true);
                      }}
                    >
                      Review and send approved email
                    </Button>
                  )}
                  {["email_sending", "email_unknown"].includes(selected.status) && (
                    <p className="form-help">
                      Delivery needs checking in Gmail. Do not resend: Gmail may already have
                      accepted it.
                    </p>
                  )}
                  {selected.status === "email_failed" && (
                    <p className="form-help">
                      Gmail rejected the send. This record is not marked sent. Automatic retries are
                      disabled.
                    </p>
                  )}
                </div>
              )}
              {lookupErrors[selected.restaurant_id] && (
                <ErrorNote
                  error={lookupErrors[selected.restaurant_id] || "Restaurant unavailable"}
                />
              )}
              <div className="panel-section">
                <h3>
                  {mode === "demo"
                    ? "Original sample message"
                    : selected.channel === "email"
                      ? "Exact approved email message"
                      : "Exact original message sent"}
                </h3>
                <div className="message-original">{selected.message_text}</div>
              </div>
              {selected.status === "tasting" && (
                <div className="panel-section">
                  <h3>Tasting</h3>
                  {plans[selected.id]?.when ? (
                    <div className="text-sm space-y-1 mb-3">
                      <p className="font-medium">{formatTasting(plans[selected.id]!.when)}</p>
                      {plans[selected.id]!.address && <p>{plans[selected.id]!.address}</p>}
                      {plans[selected.id]!.notes && (
                        <p className="text-muted-foreground">{plans[selected.id]!.notes}</p>
                      )}
                    </div>
                  ) : (
                    <p className="form-help mb-3">No tasting planned yet.</p>
                  )}
                  <div className="flex gap-2 flex-wrap">
                    <Button variant="outline" onClick={() => setPlanning(true)}>
                      <CalendarClock />
                      {plans[selected.id]?.when ? "Edit tasting plan" : "Plan tasting"}
                    </Button>
                    {plans[selected.id]?.when && (
                      <Button variant="outline" asChild>
                        <a
                          href={directionsUrl(
                            names[selected.restaurant_id]?.name || "",
                            plans[selected.id]!.address,
                          )}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          <Navigation />
                          Directions
                        </a>
                      </Button>
                    )}
                  </div>
                </div>
              )}
              <div className="panel-section">
                <h3>Update collaboration status</h3>
                {transitions[selected.status].length ? (
                  <div className="flex gap-2 flex-wrap">
                    {transitions[selected.status].map((s) => (
                      <Button
                        key={s}
                        variant={s === "rejected" ? "outline" : "default"}
                        disabled={updating}
                        onClick={() => change(s)}
                      >
                        {updating ? <Pending /> : <ArrowRight />}Move to {s}
                      </Button>
                    ))}
                  </div>
                ) : (
                  <p className="form-help">This collaboration is {selected.status}.</p>
                )}
                {reverts[selected.status].length > 0 && (
                  <div className="flex gap-2 flex-wrap mt-3">
                    {reverts[selected.status].map((s) => (
                      <Button
                        key={s}
                        variant="ghost"
                        size="sm"
                        disabled={updating}
                        onClick={() => change(s)}
                      >
                        <Undo2 />
                        Back to {s}
                      </Button>
                    ))}
                  </div>
                )}
                <p className="form-help mt-3">
                  Your backend is authoritative and may reject a status change. Updated{" "}
                  {formatDate(selected.updated_at)}.
                </p>
                <ErrorNote error={detailError} />
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
      <Dialog
        open={emailConfirm}
        onOpenChange={(open) => {
          if (!updating) setEmailConfirm(open);
        }}
      >
        <DialogContent className="panel-dialog">
          <DialogTitle>Review and approve email</DialogTitle>
          <DialogDescription>
            Send the stored, read-only email through its originally approved Gmail account.
          </DialogDescription>
          <p className="text-sm">To: {selected?.email?.recipient}</p>
          <p className="text-sm">Subject: {selected?.email?.subject}</p>
          <div className="message-original">{selected?.message_text}</div>
          <label className="confirm-check">
            <input
              type="checkbox"
              checked={emailApproved}
              onChange={(event) => setEmailApproved(event.target.checked)}
            />
            I approve this exact email for sending.
          </label>
          <ErrorNote error={detailError} />
          <Button disabled={!emailApproved || updating} onClick={sendApprovedEmail}>
            {updating && <Pending />}Approve and send email
          </Button>
        </DialogContent>
      </Dialog>
      {selected && (
        <TastingDialog
          open={planning}
          onOpenChange={setPlanning}
          initialPlan={selected.tasting}
          name={names[selected.restaurant_id]?.name || "This restaurant"}
          onSaved={saveTasting}
        />
      )}
      <Dialog open={compose} onOpenChange={setCompose}>
        <DialogContent className="panel-dialog">
          <DialogTitle>Record manual outreach</DialogTitle>
          <DialogDescription>
            {mode === "demo"
              ? "Try the workflow with sample records only."
              : "Choose a business and confirm the exact message you manually sent. Its business record is created automatically."}
          </DialogDescription>
          <SocialWorkflow
            onRecorded={() => {
              setOffset(0);
              setRefresh((r) => r + 1);
            }}
          />
        </DialogContent>
      </Dialog>
    </div>
  );
}
