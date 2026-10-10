import { ApiError } from "./client";
import {
  canTransition,
  type ApiClient,
  type Discovery,
  type Outreach,
  type Restaurant,
  type CreatorProfile,
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
      regular_opening_hours: {
        weekday_descriptions: [
          "Monday: 8:00 AM – 5:00 PM",
          "Tuesday: 8:00 AM – 5:00 PM",
          "Wednesday: 8:00 AM – 5:00 PM",
          "Thursday: 8:00 AM – 5:00 PM",
          "Friday: 8:00 AM – 6:00 PM",
          "Saturday: 9:00 AM – 6:00 PM",
          "Sunday: Closed",
        ],
      },
    },
    {
      id: "demo-cafe-2",
      display_name: { text: "The Daily Ground" },
      formatted_address: "18 Tanjong Pagar Road, Singapore 088441",
      primary_type: "cafe",
      business_status: "OPERATIONAL",
      regular_opening_hours: {
        weekday_descriptions: [
          "Monday: 8:00 AM – 5:00 PM",
          "Tuesday: 8:00 AM – 5:00 PM",
          "Wednesday: 8:00 AM – 5:00 PM",
          "Thursday: 8:00 AM – 5:00 PM",
          "Friday: 8:00 AM – 6:00 PM",
          "Saturday: 9:00 AM – 6:00 PM",
          "Sunday: Closed",
        ],
      },
    },
    {
      id: "demo-cafe-3",
      display_name: { text: "Sunday Folks" },
      formatted_address: "44 Jalan Merah Saga, Singapore 278116",
      primary_type: "dessert_shop",
      business_status: "OPERATIONAL",
      regular_opening_hours: {
        weekday_descriptions: [
          "Monday: 8:00 AM – 5:00 PM",
          "Tuesday: 8:00 AM – 5:00 PM",
          "Wednesday: 8:00 AM – 5:00 PM",
          "Thursday: 8:00 AM – 5:00 PM",
          "Friday: 8:00 AM – 6:00 PM",
          "Saturday: 9:00 AM – 6:00 PM",
          "Sunday: Closed",
        ],
      },
    },
    {
      id: "demo-cafe-4",
      display_name: { text: "Little Fern" },
      formatted_address: "6 Craig Road, Singapore 089666",
      primary_type: "restaurant",
      business_status: "OPERATIONAL",
      regular_opening_hours: {
        weekday_descriptions: [
          "Monday: 8:00 AM – 5:00 PM",
          "Tuesday: 8:00 AM – 5:00 PM",
          "Wednesday: 8:00 AM – 5:00 PM",
          "Thursday: 8:00 AM – 5:00 PM",
          "Friday: 8:00 AM – 6:00 PM",
          "Saturday: 9:00 AM – 6:00 PM",
          "Sunday: Closed",
        ],
      },
    },
    {
      id: "demo-cafe-5",
      display_name: { text: "Common Table" },
      formatted_address: "23 Keong Saik Road, Singapore 089130",
      primary_type: "cafe",
      business_status: "OPERATIONAL",
      regular_opening_hours: {
        weekday_descriptions: [
          "Monday: 8:00 AM – 5:00 PM",
          "Tuesday: 8:00 AM – 5:00 PM",
          "Wednesday: 8:00 AM – 5:00 PM",
          "Thursday: 8:00 AM – 5:00 PM",
          "Friday: 8:00 AM – 6:00 PM",
          "Saturday: 9:00 AM – 6:00 PM",
          "Sunday: Closed",
        ],
      },
    },
    {
      id: "demo-cafe-6",
      display_name: { text: "Good Company Coffee" },
      formatted_address: "9 Everton Park, Singapore 080009",
      primary_type: "coffee_shop",
      business_status: "OPERATIONAL",
      regular_opening_hours: {
        weekday_descriptions: [
          "Monday: 8:00 AM – 5:00 PM",
          "Tuesday: 8:00 AM – 5:00 PM",
          "Wednesday: 8:00 AM – 5:00 PM",
          "Thursday: 8:00 AM – 5:00 PM",
          "Friday: 8:00 AM – 6:00 PM",
          "Saturday: 9:00 AM – 6:00 PM",
          "Sunday: Closed",
        ],
      },
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
      tasting:
        status === "tasting"
          ? {
              scheduled_at: "2026-11-01T11:00:00Z",
              address: "42 Fictional Road, Singapore",
              notes: "Fictional demo tasting",
            }
          : null,
    }),
  );
  const pause = async () => new Promise((resolve) => setTimeout(resolve, 350));
  let creator: CreatorProfile | null = null;
  return {
    creatorProfile: async () => (creator ? structuredClone(creator) : null),
    saveCreatorProfile: async (input) => {
      creator = { ...input, confirmed_at: new Date().toISOString() };
      return structuredClone(creator);
    },
    geminiStatus: async () => ({ configured: true, model: "demo-no-model-call" }),
    generateDraft: async (input) => {
      await pause();
      if (!creator) throw new ApiError(409, "Save your sample creator profile in Settings first.");
      return {
        id: 0,
        channel: input.channel,
        subject: "Sample TikTok collaboration enquiry",
        message_text: `Hi ${input.restaurant_name} team,\n\nI’m ${creator.creator_name}, and I run a food-review account on TikTok: ${creator.tiktok_url}. My videos have generated over ${creator.views_over.toLocaleString("en-US")} views and more than ${creator.shares_over.toLocaleString("en-US")} shares, with every video receiving at least ${creator.minimum_video_views.toLocaleString("en-US")} views.\n\nI’d love to feature ${input.feature_detail || "your food business"} on my TikTok food-review account.\n\nWould you be open to a complimentary tasting in exchange for one TikTok review, with the hosted meal disclosed? No creator fee.\n\nLet me know if you’re interested!\n\nBest,\nBryan's dining room`,
        model: "demo-no-model-call",
        prompt_version: "sample-only",
        created_at: new Date().toISOString(),
      };
    },
    health: async () => {
      await pause();
      return { status: "ok" };
    },
    discover: async () => {
      await pause();
      const contacted = new Set(
        rows.map((row) => restaurants.find((r) => r.id === row.restaurant_id)?.google_place_id),
      );
      return structuredClone({
        ...demoDiscovery,
        places: demoDiscovery.places.filter((place) => !contacted.has(place.id)),
      });
    },
    placeDetails: async (id) => {
      await pause();
      const place = demoDiscovery.places.find((p) => p.id === id);
      if (!place) throw new ApiError(404, "Sample business not found.");
      return structuredClone(place);
    },
    contacts: async () => {
      await pause();
      return [
        {
          contact_type: "email",
          value: "collabs@example.com",
          source_url: "https://example.com/contact",
          direct_url: "mailto:collabs@example.com",
          verified: false,
          usable: false,
        },
      ];
    },
    gmailStatus: async () => ({
      configured: true,
      connected: true,
      email: "bryan.demo@example.com",
    }),
    gmailConnect: async () => {
      throw new ApiError(422, "Demo mode never connects a real Gmail account.");
    },
    gmailDisconnect: async () => {},
    approveEmail: async (input) => {
      await pause();
      if (
        !input.approved ||
        !input.verified_public_business_email ||
        !input.subject.trim() ||
        !input.message_text.trim() ||
        !input.recipient.includes("@") ||
        !input.source_url
      )
        throw new ApiError(422, "Recipient, source and approval are required.");
      let business = restaurants.find((r) => r.google_place_id === input.google_place_id);
      if (business && rows.some((row) => row.restaurant_id === business?.id))
        throw new ApiError(409, "Initial outreach already exists.");
      if (!business) {
        business = {
          id: Math.max(...restaurants.map((r) => r.id)) + 1,
          google_place_id: input.google_place_id,
          name: input.name || "Contacted business",
        };
        restaurants.push(business);
      }
      const now = new Date().toISOString();
      const row: Outreach = {
        id: Math.max(...rows.map((r) => r.id)) + 1,
        restaurant_id: business.id,
        channel: "email",
        status: "email_approved",
        message_text: input.message_text,
        sent_at: null,
        updated_at: now,
        email: {
          recipient: input.recipient,
          sender: "bryan.demo@example.com",
          subject: input.subject,
          source_url: input.source_url,
          gmail_message_id: null,
          approved_at: now,
        },
      };
      rows.unshift(row);
      return structuredClone(row);
    },
    sendEmail: async (id) => {
      await pause();
      const row = rows.find((r) => r.id === id);
      if (!row || row.channel !== "email")
        throw new ApiError(404, "Approved sample email not found.");
      if (row.status !== "email_approved") throw new ApiError(409, "Email already attempted.");
      row.status = "sent";
      row.sent_at = new Date().toISOString();
      row.updated_at = row.sent_at;
      if (row.email) row.email.gmail_message_id = "fictional-demo-id";
      return structuredClone(row);
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
    updateRestaurant: async (id, input) => {
      await pause();
      const record = restaurants.find((restaurant) => restaurant.id === id);
      if (!record) throw new ApiError(404, "Sample business not found.");
      if (!input.name.trim()) throw new ApiError(422, "Business name is required.");
      Object.assign(record, input, { name: input.name.trim() });
      return structuredClone(record);
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
    markPlaceSent: async (input) => {
      await pause();
      if (!input.confirmed_sent || !input.message_text.trim())
        throw new ApiError(422, "Confirmation and message required.");
      let restaurant = restaurants.find((r) => r.google_place_id === input.google_place_id);
      if (restaurant && rows.some((r) => r.restaurant_id === restaurant!.id))
        throw new ApiError(409, "Business already contacted.");
      if (!restaurant) {
        restaurant = {
          id: Math.max(...restaurants.map((r) => r.id)) + 1,
          google_place_id: input.google_place_id,
          name: input.name || "Contacted business",
        };
        restaurants.push(restaurant);
      }
      const now = new Date().toISOString();
      const row: Outreach = {
        id: Math.max(...rows.map((r) => r.id)) + 1,
        restaurant_id: restaurant.id,
        channel: input.channel,
        message_text: input.message_text,
        status: "sent",
        sent_at: now,
        updated_at: now,
        tasting: null,
      };
      rows.unshift(row);
      return structuredClone(row);
    },
    changeStatus: async (id, status, tasting) => {
      await pause();
      const row = rows.find((r) => r.id === id);
      if (!row) throw new ApiError(404, "Outreach record does not exist.");
      if (!canTransition(row.status, status))
        throw new ApiError(409, "This status transition is not allowed.");
      if (status === "tasting" && !tasting && !row.tasting)
        throw new ApiError(422, "Schedule your tasting first.");
      if (tasting) {
        if (
          status !== "tasting" ||
          !tasting.address.trim() ||
          Number.isNaN(Date.parse(tasting.scheduled_at))
        )
          throw new ApiError(422, "Valid tasting date and address required.");
        row.tasting = structuredClone(tasting);
      }
      row.status = status;
      row.updated_at = new Date().toISOString();
      return { ...row };
    },
  };
}
