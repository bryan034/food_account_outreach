import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { DiscoverPage } from "@/features/discover";
import { SocialWorkflow } from "@/features/social-workflow";
import { TastingDialog } from "@/features/tasting";
import { OutreachPage } from "@/features/outreach";
import { CreatorProfileSettings } from "@/features/creator-profile";

const api = vi.hoisted(() => ({
  placeDetails: vi.fn(),
  markPlaceSent: vi.fn(),
  contacts: vi.fn(),
  gmailStatus: vi.fn(),
  approveEmail: vi.fn(),
  sendEmail: vi.fn(),
  outreach: vi.fn(),
  restaurant: vi.fn(),
  updateRestaurant: vi.fn(),
  creatorProfile: vi.fn(),
  saveCreatorProfile: vi.fn(),
  geminiStatus: vi.fn(),
  generateDraft: vi.fn(),
}));
const workspace = vi.hoisted(() => ({ mode: "demo" }));
vi.mock("@/features/workspace", () => ({ useWorkspace: () => ({ api, mode: workspace.mode }) }));
vi.mock("@/features/shell", () => ({ PageFooter: () => null }));

const place = {
  id: "private-place-id",
  display_name: { text: "Test Café" },
  formatted_address: "42 Test Road",
  primary_type: "cafe",
  business_status: "OPERATIONAL",
};
beforeEach(() => {
  vi.resetAllMocks();
  workspace.mode = "demo";
});
afterEach(cleanup);

describe("Gemini drafting is separate from sending", () => {
  it("requires factual confirmation, fills the message and never calls approval or send", async () => {
    workspace.mode = "connected";
    api.generateDraft.mockResolvedValue({
      id: 8,
      model: "test-model",
      message_text: "Grounded draft\n\nBest,\nBryan's dining room",
      subject: "Safe subject",
    });
    render(<SocialWorkflow place={place} />);
    fireEvent.click(screen.getByRole("button", { name: "Draft with Gemini" }));
    const generate = screen.getByRole("button", { name: "Generate with Gemini" });
    expect(generate).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Confirmed business name for greeting"), {
      target: { value: "Confirmed Café" },
    });
    fireEvent.change(screen.getByLabelText("Confirmed business type"), {
      target: { value: "cafe" },
    });
    fireEvent.click(
      screen.getByLabelText("I confirm the name, type and any feature detail are factual."),
    );
    fireEvent.click(generate);
    await waitFor(() =>
      expect(screen.getByLabelText("Exact message you manually sent")).toHaveValue(
        "Grounded draft\n\nBest,\nBryan's dining room",
      ),
    );
    expect(api.generateDraft).toHaveBeenCalledWith(
      expect.objectContaining({
        google_place_id: place.id,
        restaurant_name: "Confirmed Café",
        business_kind: "cafe",
        channel: "tiktok",
        facts_confirmed: true,
      }),
    );
    expect(api.approveEmail).not.toHaveBeenCalled();
    expect(api.sendEmail).not.toHaveBeenCalled();
    expect(api.markPlaceSent).not.toHaveBeenCalled();
  });

  it("requires permission to replace edits and preserves them if Gemini fails", async () => {
    workspace.mode = "connected";
    api.generateDraft.mockRejectedValue(new Error("Gemini unavailable"));
    render(<SocialWorkflow place={place} />);
    fireEvent.change(screen.getByLabelText("Exact message you manually sent"), {
      target: { value: "My existing message" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Draft with Gemini" }));
    fireEvent.change(screen.getByLabelText("Confirmed business name for greeting"), {
      target: { value: "Confirmed Café" },
    });
    fireEvent.click(
      screen.getByLabelText("I confirm the name, type and any feature detail are factual."),
    );
    expect(screen.getByRole("button", { name: "Generate with Gemini" })).toBeDisabled();
    fireEvent.click(screen.getByLabelText("Replace my current draft message and email subject."));
    fireEvent.click(screen.getByRole("button", { name: "Generate with Gemini" }));
    expect(await screen.findByText("Gemini unavailable")).toBeInTheDocument();
    expect(screen.getByLabelText("Exact message you manually sent")).toHaveValue(
      "My existing message",
    );
    expect(api.sendEmail).not.toHaveBeenCalled();
  });

  it("blocks editing and sending while generation is running", async () => {
    let resolve!: (value: unknown) => void;
    api.generateDraft.mockReturnValue(
      new Promise((finish) => {
        resolve = finish;
      }),
    );
    render(<SocialWorkflow place={place} />);
    fireEvent.click(screen.getByRole("button", { name: "Draft with Gemini" }));
    fireEvent.change(screen.getByLabelText("Confirmed business name for greeting"), {
      target: { value: "Confirmed Café" },
    });
    fireEvent.click(
      screen.getByLabelText("I confirm the name, type and any feature detail are factual."),
    );
    fireEvent.click(screen.getByRole("button", { name: "Generate sample draft" }));
    expect(screen.getByLabelText("Exact message you manually sent")).toBeDisabled();
    expect(screen.getByLabelText("Contact channel")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Simulate sent message" })).toBeDisabled();
    resolve({ id: 0, model: "demo", message_text: "Sample", subject: "Sample" });
    await waitFor(() =>
      expect(screen.getByLabelText("Exact message you manually sent")).toHaveValue("Sample"),
    );
  });

  it("saves statistics only after the user confirms them", async () => {
    api.creatorProfile.mockResolvedValue(null);
    api.geminiStatus.mockResolvedValue({ configured: false, model: "test-model" });
    api.saveCreatorProfile.mockResolvedValue({ confirmed_at: "2026-10-09T00:00:00Z" });
    render(<CreatorProfileSettings />);
    await screen.findByText("No creator profile saved yet.");
    const save = screen.getByRole("button", { name: "Save creator profile" });
    expect(save).toBeDisabled();
    fireEvent.click(
      screen.getByLabelText(
        "I confirm these statistics are accurate, including the claim about every video.",
      ),
    );
    fireEvent.click(save);
    await waitFor(() =>
      expect(api.saveCreatorProfile).toHaveBeenCalledWith({
        creator_name: "Bryan",
        tiktok_url: "https://www.tiktok.com/@bbbrrr9",
        views_over: 146000,
        shares_over: 600,
        minimum_video_views: 1000,
        statistics_confirmed: true,
      }),
    );
  });
});

describe("Saved contacted businesses", () => {
  it("shows a live restaurant name when no label exists and saves editable notes", async () => {
    const business = { id: 23, google_place_id: place.id, name: "Contacted business" };
    api.outreach.mockResolvedValue([
      {
        id: 11,
        restaurant_id: 23,
        channel: "email",
        status: "sent",
        message_text: "Immutable sent message",
        sent_at: "2026-10-09T00:00:00Z",
        updated_at: "2026-10-09T00:00:00Z",
      },
    ]);
    api.restaurant.mockResolvedValue(business);
    api.placeDetails.mockResolvedValue(place);
    api.updateRestaurant.mockResolvedValue({ ...business, name: "My café", area: "East" });
    render(<OutreachPage />);
    await screen.findByText("Test Café");
    fireEvent.click(screen.getByRole("button", { name: "View outreach for Test Café" }));
    const name = screen.getByLabelText("Business name / your label");
    expect(name).toHaveValue("");
    expect(name).toHaveAttribute("placeholder", "Test Café");
    fireEvent.change(name, { target: { value: "My café" } });
    fireEvent.change(screen.getByLabelText("Area"), { target: { value: "East" } });
    fireEvent.click(screen.getByRole("button", { name: "Save business notes" }));
    await screen.findByText("Business notes saved.");
    expect(api.updateRestaurant).toHaveBeenCalledWith(23, {
      name: "My café",
      area: "East",
      category: null,
      address: null,
      website_url: null,
    });
    expect(screen.getByText("Immutable sent message")).toBeInTheDocument();
    expect(api.sendEmail).not.toHaveBeenCalled();
    expect(screen.getAllByText("My café").length).toBeGreaterThan(0);
  });

  it("keeps the saved outreach visible when the live Google name lookup fails", async () => {
    api.outreach.mockResolvedValue([
      {
        id: 11,
        restaurant_id: 23,
        channel: "email",
        status: "sent",
        message_text: "Saved",
        sent_at: null,
        updated_at: "2026-10-09T00:00:00Z",
      },
    ]);
    api.restaurant.mockResolvedValue({
      id: 23,
      google_place_id: place.id,
      name: "Contacted business",
    });
    api.placeDetails.mockRejectedValue(new Error("Google unavailable"));
    render(<OutreachPage />);
    expect(await screen.findByText("Restaurant name unavailable")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "View outreach for Restaurant name unavailable" }),
    ).toBeInTheDocument();
  });
});

describe("Business details and manual outreach", () => {
  it("loads opening hours on click, hides provider IDs and needs no add-record form", async () => {
    api.placeDetails.mockResolvedValue({
      ...place,
      regular_opening_hours: { weekday_descriptions: ["Monday: 9 AM – 5 PM"] },
    });
    render(<DiscoverPage />);
    expect(api.placeDetails).not.toHaveBeenCalled();
    fireEvent.click(screen.getAllByRole("button", { name: /View .* details/ })[0]!);
    expect(await screen.findByText("Monday: 9 AM – 5 PM")).toBeInTheDocument();
    expect(screen.queryByText(place.id)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Prepare outreach" }));
    expect(screen.getByLabelText("Exact message you manually sent")).toBeInTheDocument();
    expect(api.markPlaceSent).not.toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: /Create.*record/i })).not.toBeInTheDocument();
  });

  it("records a place only after explicit manual-send confirmation", async () => {
    api.markPlaceSent.mockResolvedValue({ id: 7 });
    render(<SocialWorkflow place={place} />);
    fireEvent.change(screen.getByLabelText("Exact message you manually sent"), {
      target: { value: "  Exact text\n" },
    });
    expect(api.markPlaceSent).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Simulate sent message" }));
    expect(screen.getByRole("button", { name: "Confirm and record" })).toBeDisabled();
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Confirm and record" }));
    await waitFor(() =>
      expect(api.markPlaceSent).toHaveBeenCalledWith({
        google_place_id: place.id,
        channel: "tiktok",
        message_text: "  Exact text\n",
        confirmed_sent: true,
      }),
    );
    expect(
      await screen.findByText("Sample outreach recorded. No message was sent."),
    ).toBeInTheDocument();
  });
});

describe("Approved Gmail outreach", () => {
  it("changes the profile field and send action, and approves before delivery", async () => {
    workspace.mode = "connected";
    api.contacts.mockResolvedValue([
      {
        contact_type: "email",
        value: "hello@example.com",
        source_url: "https://example.com/contact",
      },
    ]);
    api.gmailStatus.mockResolvedValue({
      configured: true,
      connected: true,
      email: "creator@example.com",
    });
    api.approveEmail.mockResolvedValue({ id: 12, status: "email_approved" });
    api.sendEmail.mockResolvedValue({ id: 12, status: "sent" });
    render(<SocialWorkflow place={place} />);
    fireEvent.change(screen.getByLabelText("Contact channel"), { target: { value: "email" } });
    await waitFor(() =>
      expect(screen.getByLabelText("Business email address")).toHaveValue("hello@example.com"),
    );
    expect(screen.queryByLabelText("Direct profile URL (optional)")).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Email subject"), {
      target: { value: "A café collaboration" },
    });
    fireEvent.change(screen.getByLabelText("Email message"), {
      target: { value: "Exact approved text" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send email" }));
    expect(api.approveEmail).not.toHaveBeenCalled();
    expect(api.sendEmail).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Approve and send email" })).toBeDisabled();
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Approve and send email" }));
    await waitFor(() => expect(api.sendEmail).toHaveBeenCalledWith(12));
    expect(api.approveEmail).toHaveBeenCalledWith({
      google_place_id: place.id,
      recipient: "hello@example.com",
      source_url: "https://example.com/contact",
      subject: "A café collaboration",
      message_text: "Exact approved text",
      approved: true,
      verified_public_business_email: true,
    });
    expect(api.approveEmail.mock.invocationCallOrder[0]).toBeLessThan(
      api.sendEmail.mock.invocationCallOrder[0]!,
    );
    expect(api.markPlaceSent).not.toHaveBeenCalled();
    expect(await screen.findByText(/Gmail accepted your email/)).toBeInTheDocument();
  });

  it("leaves the recipient empty with the requested placeholder when no email exists", async () => {
    workspace.mode = "connected";
    api.contacts.mockResolvedValue([]);
    api.gmailStatus.mockResolvedValue({
      configured: true,
      connected: true,
      email: "creator@example.com",
    });
    render(<SocialWorkflow place={place} />);
    fireEvent.change(screen.getByLabelText("Contact channel"), { target: { value: "email" } });
    expect(await screen.findByPlaceholderText("Email address was not found")).toHaveValue("");
    expect(screen.getByRole("button", { name: "Send email" })).toBeDisabled();
    expect(api.approveEmail).not.toHaveBeenCalled();
  });
});

describe("Tasting planner", () => {
  it("does not save on opening or cancellation", () => {
    const onSaved = vi.fn();
    const onOpenChange = vi.fn();
    render(<TastingDialog open name="Test Café" onSaved={onSaved} onOpenChange={onOpenChange} />);
    expect(onSaved).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(onOpenChange).toHaveBeenCalledWith(false);
    expect(onSaved).not.toHaveBeenCalled();
  });

  it("submits Singapore time and stays open on a backend failure", async () => {
    const onSaved = vi.fn().mockRejectedValue(new Error("Backend unavailable"));
    const onOpenChange = vi.fn();
    render(<TastingDialog open name="Test Café" onSaved={onSaved} onOpenChange={onOpenChange} />);
    fireEvent.change(screen.getByLabelText("Date and time · SGT"), {
      target: { value: "2026-11-01T19:00" },
    });
    fireEvent.change(screen.getByLabelText("Tasting address"), {
      target: { value: "42 Test Road" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save tasting" }));
    expect(await screen.findByText("Backend unavailable")).toBeInTheDocument();
    expect(onSaved).toHaveBeenCalledWith({
      scheduled_at: "2026-11-01T11:00:00.000Z",
      address: "42 Test Road",
      notes: "",
    });
    expect(onOpenChange).not.toHaveBeenCalled();
  });
});
