import { ApiError } from "./client";
import {
  canTransition,
  type ApiClient,
  type Discovery,
  type Outreach,
  type Restaurant,
} from "./types";
export const demoDiscovery: Discovery = {
  next_page_token: "sample-next-page-token",
  places: [
    {
      id: "demo-cafe-1",
      display_name: { text: "Poppy & Seed" },
      formatted_address: "42 Duxton Road, Singapore 089506",
      primary_type: "cafe",
      business_status: "OPERATIONAL",
    },
    {
      id: "demo-cafe-2",
      display_name: { text: "The Daily Ground" },
      formatted_address: "18 Tanjong Pagar Road, Singapore 088441",
      primary_type: "cafe",
      business_status: "OPERATIONAL",
    },
    {
      id: "demo-cafe-3",
      display_name: { text: "Sunday Folks" },
      formatted_address: "44 Jalan Merah Saga, Singapore 278116",
      primary_type: "dessert_shop",
      business_status: "OPERATIONAL",
    },
    {
      id: "demo-cafe-4",
      display_name: { text: "Little Fern" },
      formatted_address: "6 Craig Road, Singapore 089666",
      primary_type: "restaurant",
      business_status: "OPERATIONAL",
    },
    {
      id: "demo-cafe-5",
      display_name: { text: "Common Table" },
      formatted_address: "23 Keong Saik Road, Singapore 089130",
      primary_type: "cafe",
      business_status: "OPERATIONAL",
    },
    {
      id: "demo-cafe-6",
      display_name: { text: "Good Company Coffee" },
      formatted_address: "9 Everton Park, Singapore 080009",
      primary_type: "coffee_shop",
      business_status: "OPERATIONAL",
    },
  ],
};
export function createDemoClient(): ApiClient {
  const restaurants: Restaurant[] = [
    "Kaya House",
    "Petal Coffee",
    "The Noodle Social",
    "Toast & Together",
    "Pandan Pantry",
  ].map((name, i) => ({ id: i + 1, name, google_place_id: `demo-saved-${i + 1}` }));
  const rows: Outreach[] = ["sent", "scheduling", "tasting", "completed", "rejected"].map(
    (status, i) => ({
      id: 101 + i,
      restaurant_id: i + 1,
      channel: i % 2 ? "instagram" : "tiktok",
      status: status as Outreach["status"],
      message_text: `Hi! I'm Bryan, a Singapore food creator. I'd love to explore a food collaboration with ${restaurants[i]?.name || "this business"}. Would you be open to chatting about a tasting? This is a fictional sample message, not an actual sent message.`,
      sent_at: `2026-10-0${8 - i}T04:00:00Z`,
      updated_at: `2026-10-0${8 - i}T04:00:00Z`,
    }),
  );
  const pause = async () => new Promise((resolve) => setTimeout(resolve, 350));
  return {
    health: async () => {
      await pause();
      return { status: "ok" };
    },
    discover: async () => {
      await pause();
      return structuredClone(demoDiscovery);
    },
    restaurant: async (id) => {
      await pause();
      const r = restaurants.find((r) => r.id === id);
      if (!r) throw new ApiError(404, "No sample restaurant has this local ID.");
      return { ...r };
    },
    createRestaurant: async (input) => {
      await pause();
      if (restaurants.some((r) => r.google_place_id === input.google_place_id))
        throw new ApiError(409, "This Google Place ID already has a local record.");
      const r = { ...input, id: Math.max(...restaurants.map((r) => r.id)) + 1 };
      restaurants.push(r);
      return { ...r };
    },
    outreach: async (offset, limit) => {
      await pause();
      if (offset < 0 || limit < 1 || limit > 100)
        throw new ApiError(422, "Invalid pagination values.");
      return rows.slice(offset, offset + limit).map((r) => ({ ...r }));
    },
    markSent: async (input) => {
      await pause();
      if (!input.confirmed_sent || !input.message_text.trim())
        throw new ApiError(422, "Confirmation and an exact message are required.");
      if (!restaurants.some((r) => r.id === input.restaurant_id))
        throw new ApiError(404, "Restaurant does not exist.");
      if (rows.some((r) => r.restaurant_id === input.restaurant_id))
        throw new ApiError(
          409,
          "Initial outreach already exists for this restaurant, even through a different channel.",
        );
      const now = new Date().toISOString();
      const r: Outreach = {
        ...input,
        id: Math.max(...rows.map((r) => r.id)) + 1,
        status: "sent",
        sent_at: now,
        updated_at: now,
      };
      rows.unshift(r);
      return { ...r };
    },
    changeStatus: async (id, status) => {
      await pause();
      const row = rows.find((r) => r.id === id);
      if (!row) throw new ApiError(404, "Outreach record does not exist.");
      if (!canTransition(row.status, status))
        throw new ApiError(409, "This status transition is not allowed.");
      row.status = status;
      row.updated_at = new Date().toISOString();
      return { ...row };
    },
  };
}
