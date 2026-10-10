import { afterEach, describe, expect, it, vi } from "vitest";
import { createApiClient, ApiError } from "@/lib/api/client";
import { createDemoClient } from "@/lib/api/demo";
import { canTransition, transitions, validProfile } from "@/lib/api/types";
import { directionsUrl, planFromApi, planToApi } from "@/features/tasting";
afterEach(() => {
  vi.restoreAllMocks();
});
describe("Outreach status rules", () => {
  it.each([
    ["sent", ["scheduling", "rejected"]],
    ["scheduling", ["tasting", "rejected"]],
    ["tasting", ["completed", "rejected"]],
    ["rejected", []],
    ["completed", []],
  ] as const)("%s exposes only permitted transitions", (status, allowed) => {
    expect(transitions[status]).toEqual(allowed);
  });
  it("repeating the current status is harmless", () => {
    expect(canTransition("sent", "sent")).toBe(true);
  });
  it("terminal statuses cannot return to sent", () => {
    expect(canTransition("completed", "sent")).toBe(false);
    expect(canTransition("rejected", "sent")).toBe(true);
    expect(canTransition("tasting", "scheduling")).toBe(true);
    expect(canTransition("tasting", "sent")).toBe(false);
  });
});
describe("FastAPI contract", () => {
  it("refreshes the restaurant cache after saving editable notes", async () => {
    const fetcher = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ id: 23, google_place_id: "place-123", name: "Old" })),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ id: 23, google_place_id: "place-123", name: "New" })),
      );
    const api = createApiClient("http://127.0.0.1:8000");
    await api.restaurant(23);
    await api.updateRestaurant(23, { name: "New" });
    expect((await api.restaurant(23)).name).toBe("New");
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(fetcher.mock.calls[1]?.[1]?.method).toBe("PATCH");
  });
  it("uses separate immutable approval and send endpoints, with OAuth cookies", async () => {
    const fetcher = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async () => new Response('{"id":17}'));
    const api = createApiClient("http://localhost:8000");
    const input = {
      google_place_id: "place-123",
      recipient: "hello@example.com",
      source_url: "https://example.com/contact",
      subject: "A café collaboration",
      message_text: "Exact content",
      approved: true as const,
      verified_public_business_email: true as const,
    };
    const approved = await api.approveEmail(input);
    await api.sendEmail(approved.id);
    expect(fetcher.mock.calls[0]?.[0]).toBe("http://localhost:8000/outreach/email/approve");
    expect(JSON.parse(fetcher.mock.calls[0]?.[1]?.body as string)).toEqual(input);
    expect(fetcher.mock.calls[1]?.[0]).toBe("http://localhost:8000/outreach/17/email/send");
    expect(JSON.parse(fetcher.mock.calls[1]?.[1]?.body as string)).toEqual({ approved: true });
    expect(fetcher.mock.calls[0]?.[1]?.credentials).toBe("include");
  });
  it("handles a successful disconnect with no response body", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, { status: 204 }));
    await expect(
      createApiClient("http://localhost:8000").gmailDisconnect(),
    ).resolves.toBeUndefined();
  });
  it("fetches opening hours only through an explicit detail request", async () => {
    const fetcher = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("{}"));
    const api = createApiClient("http://localhost:8000");
    expect(fetcher).not.toHaveBeenCalled();
    await api.placeDetails("place-123");
    expect(fetcher).toHaveBeenCalledWith(
      "http://localhost:8000/discovery/google-places/place-123/details",
      expect.objectContaining({ method: "GET" }),
    );
  });
  it("records a discovered place without a separate restaurant-creation request", async () => {
    const fetcher = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("{}"));
    const input = {
      google_place_id: "place-123",
      channel: "tiktok" as const,
      message_text: "Exact sent text",
      confirmed_sent: true as const,
    };
    await createApiClient("http://localhost:8000").markPlaceSent(input);
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(fetcher).toHaveBeenCalledWith(
      "http://localhost:8000/outreach/from-place/mark-sent",
      expect.objectContaining({ method: "POST", body: JSON.stringify(input) }),
    );
  });
  it("saves the tasting plan and status together", async () => {
    const fetcher = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("{}"));
    const tasting = {
      scheduled_at: "2026-11-01T11:00:00.000Z",
      address: "42 Test Road",
      notes: "",
    };
    await createApiClient("http://localhost:8000").changeStatus(105, "tasting", tasting);
    expect(JSON.parse(fetcher.mock.calls[0]?.[1]?.body as string)).toEqual({
      status: "tasting",
      tasting,
    });
  });
  it("does not discover until explicitly called and does not retry failures", async () => {
    const fetcher = vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("offline"));
    const api = createApiClient("http://localhost:8000");
    expect(fetcher).not.toHaveBeenCalled();
    await expect(api.discover("cafés in Tanjong Pagar, Singapore")).rejects.toMatchObject({
      status: 0,
    });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it("preserves the discovery token without issuing pagination calls", async () => {
    const fetcher = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        new Response(JSON.stringify({ places: [], next_page_token: "keep-token" })),
      );
    const data = await createApiClient("http://localhost:8000").discover("cafés");
    expect(data.next_page_token).toBe("keep-token");
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(JSON.parse(fetcher.mock.calls[0]?.[1]?.body as string)).toEqual({ text_query: "cafés" });
  });
  it("uses outreach ID, not restaurant ID, in status URL", async () => {
    const fetcher = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("{}"));
    await createApiClient("http://localhost:8000").changeStatus(105, "scheduling");
    expect(fetcher).toHaveBeenCalledWith(
      "http://localhost:8000/outreach/105/status",
      expect.objectContaining({ method: "PATCH", body: '{"status":"scheduling"}' }),
    );
  });
  it("caches restaurant identity lookups", async () => {
    const fetcher = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response('{"id":12,"name":"Own name","google_place_id":"p"}'));
    const api = createApiClient("http://localhost:8000");
    await Promise.all([api.restaurant(12), api.restaurant(12)]);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it.each([
    [-1, 50],
    [0, 0],
    [0, 101],
  ])("rejects invalid offset %s or limit %s", async (offset, limit) => {
    const fetcher = vi.spyOn(globalThis, "fetch");
    await expect(
      createApiClient("http://localhost:8000").outreach(offset, limit),
    ).rejects.toBeInstanceOf(ApiError);
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("accepts the limit boundaries 1 and 100", async () => {
    const fetcher = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async () => new Response("[]"));
    const api = createApiClient("http://localhost:8000");
    await api.outreach(0, 1);
    await api.outreach(0, 100);
    expect(fetcher).toHaveBeenCalledTimes(2);
  });
  it("surfaces 409 without retrying or guessing a restaurant ID", async () => {
    const fetcher = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response('{"detail":"Place ID already exists"}', { status: 409 }));
    await expect(
      createApiClient("http://localhost:8000").createRestaurant({
        google_place_id: "p",
        name: "Own name",
      }),
    ).rejects.toMatchObject({ status: 409, message: "Place ID already exists" });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it("records exact message and explicit confirmation", async () => {
    const fetcher = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("{}"));
    await createApiClient("http://localhost:8000").markSent({
      restaurant_id: 12,
      channel: "tiktok",
      message_text: "  Exact original message.\n",
      confirmed_sent: true,
    });
    expect(JSON.parse(fetcher.mock.calls[0]?.[1]?.body as string)).toEqual({
      restaurant_id: 12,
      channel: "tiktok",
      message_text: "  Exact original message.\n",
      confirmed_sent: true,
    });
  });
});
describe("Tasting time and directions", () => {
  it("round trips Singapore time independently of the computer timezone", () => {
    const plan = { when: "2026-11-01T19:00", address: "42 Test Road", notes: "" };
    expect(planToApi(plan).scheduled_at).toBe("2026-11-01T11:00:00.000Z");
    expect(planFromApi(planToApi(plan))).toEqual(plan);
  });
  it("leaves origin to Google Maps instead of storing current location", () => {
    const url = new URL(directionsUrl("Test Café", "42 Test Road"));
    expect(url.searchParams.get("destination")).toBe("42 Test Road");
    expect(url.searchParams.has("destination_place_id")).toBe(false);
    expect(url.searchParams.get("travelmode")).toBe("transit");
    expect(url.searchParams.has("origin")).toBe(false);
  });
});
describe("Demo isolation and social links", () => {
  it("simulates email without Google requests and never sends twice", async () => {
    vi.useFakeTimers();
    const fetcher = vi.spyOn(globalThis, "fetch");
    const api = createDemoClient();
    const run = (async () => {
      expect((await api.gmailStatus()).connected).toBe(true);
      expect((await api.contacts("demo-cafe-1"))[0]?.value).toBe("collabs@example.com");
      const approved = await api.approveEmail({
        google_place_id: "demo-cafe-1",
        recipient: "collabs@example.com",
        source_url: "https://example.com/contact",
        subject: "Sample",
        message_text: "Sample text",
        approved: true,
        verified_public_business_email: true,
      });
      expect(approved.sent_at).toBeNull();
      expect((await api.sendEmail(approved.id)).status).toBe("sent");
      await expect(api.sendEmail(approved.id)).rejects.toMatchObject({ status: 409 });
    })();
    try {
      await vi.runAllTimersAsync();
      await run;
      expect(fetcher).not.toHaveBeenCalled();
    } finally {
      vi.useRealTimers();
    }
  });
  it("all demo operations make no live requests", async () => {
    vi.useFakeTimers();
    const fetcher = vi.spyOn(globalThis, "fetch");
    const api = createDemoClient();
    const run = (async () => {
      await api.health();
      await api.discover("cafés");
      await api.outreach(0, 10);
      await api.restaurant(1);
      const r = await api.createRestaurant({ name: "Own sample", google_place_id: "new-p" });
      const outreach = await api.markSent({
        restaurant_id: r.id,
        channel: "instagram",
        message_text: "sample",
        confirmed_sent: true,
      });
      await api.changeStatus(outreach.id, "scheduling");
    })();
    await vi.runAllTimersAsync();
    await run;
    expect(fetcher).not.toHaveBeenCalled();
    vi.useRealTimers();
  });
  it("prevents duplicate initial outreach across channels", async () => {
    vi.useFakeTimers();
    const api = createDemoClient();
    const result = api.markSent({
      restaurant_id: 1,
      channel: "instagram",
      message_text: "sample",
      confirmed_sent: true,
    });
    const assertion = expect(result).rejects.toMatchObject({ status: 409 });
    await vi.runAllTimersAsync();
    await assertion;
    vi.useRealTimers();
  });
  it("rejects unsafe or mismatched social profile URLs", () => {
    expect(validProfile("javascript:alert(1)", "tiktok")).toBeNull();
    expect(validProfile("https://tiktok.com.evil.test/@food", "tiktok")).toBeNull();
    expect(validProfile("https://instagram.com/food", "tiktok")).toBeNull();
    expect(validProfile("https://www.tiktok.com/@food", "tiktok")).toBe(
      "https://www.tiktok.com/@food",
    );
  });
});
