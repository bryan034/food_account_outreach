export type Status =
  | "sent"
  | "scheduling"
  | "rejected"
  | "tasting"
  | "completed"
  | "email_approved"
  | "email_sending"
  | "email_failed"
  | "email_unknown";
export type Channel = "email" | "tiktok" | "instagram";
export interface Place {
  id: string;
  display_name: { text: string };
  formatted_address: string | null;
  primary_type: string | null;
  business_status: string | null;
  website_url?: string | null;
  /** Optional: only shown when the backend includes Google opening hours. */
  regular_opening_hours?: { weekday_descriptions?: string[] | null } | null;
}
export interface Discovery {
  places: Place[];
  next_page_token: string | null;
}
export interface Restaurant {
  id: number;
  google_place_id: string;
  name: string;
  category?: string | null;
  address?: string | null;
  area?: string | null;
  website_url?: string | null;
}
export type RestaurantNotes = Pick<
  Restaurant,
  "name" | "category" | "address" | "area" | "website_url"
>;
export interface Outreach {
  id: number;
  restaurant_id: number;
  channel: Channel;
  status: Status;
  message_text: string;
  sent_at: string | null;
  updated_at: string;
  tasting?: TastingInput | null;
  email?: {
    recipient: string;
    sender: string;
    subject: string;
    source_url: string;
    gmail_message_id: string | null;
    approved_at: string;
  } | null;
}
export interface TastingInput {
  scheduled_at: string;
  address: string;
  notes: string;
}
export interface PlaceSentInput {
  google_place_id: string;
  name?: string;
  channel: Exclude<Channel, "email">;
  message_text: string;
  confirmed_sent: true;
}
export interface SentInput {
  restaurant_id: number;
  channel: Exclude<Channel, "email">;
  message_text: string;
  confirmed_sent: true;
}
export interface PublicContact {
  contact_type: Channel;
  value: string;
  source_url: string;
  direct_url: string;
  verified: boolean;
  usable: boolean;
}
export interface GmailStatus {
  configured: boolean;
  connected: boolean;
  email: string | null;
  detail?: string | null;
}
export interface EmailApprovalInput {
  google_place_id: string;
  name?: string;
  recipient: string;
  source_url: string;
  subject: string;
  message_text: string;
  approved: true;
  verified_public_business_email: true;
}
export interface CreatorProfileInput {
  creator_name: string;
  tiktok_url: string;
  views_over: number;
  shares_over: number;
  minimum_video_views: number;
  statistics_confirmed: true;
}
export interface CreatorProfile extends CreatorProfileInput {
  confirmed_at: string;
}
export interface DraftInput {
  request_id: string;
  google_place_id: string;
  restaurant_name: string;
  business_kind: "cafe" | "restaurant" | "bakery" | "food_business";
  channel: Channel;
  feature_detail: string;
  source_url: string | null;
  facts_confirmed: true;
}
export interface GeneratedDraft {
  id: number;
  channel: Channel;
  subject: string;
  message_text: string;
  model: string;
  prompt_version: string;
  created_at: string;
}
export interface ApiClient {
  creatorProfile(): Promise<CreatorProfile | null>;
  saveCreatorProfile(input: CreatorProfileInput): Promise<CreatorProfile>;
  geminiStatus(): Promise<{ configured: boolean; model: string }>;
  generateDraft(input: DraftInput): Promise<GeneratedDraft>;
  health(): Promise<{ status: string }>;
  discover(query: string): Promise<Discovery>;
  placeDetails(id: string, nameOnly?: boolean): Promise<Place>;
  contacts(id: string): Promise<PublicContact[]>;
  gmailStatus(): Promise<GmailStatus>;
  gmailConnect(): Promise<{ authorization_url: string }>;
  gmailDisconnect(): Promise<void>;
  approveEmail(input: EmailApprovalInput): Promise<Outreach>;
  sendEmail(outreachId: number): Promise<Outreach>;
  createRestaurant(input: Omit<Restaurant, "id">): Promise<Restaurant>;
  restaurant(id: number): Promise<Restaurant>;
  updateRestaurant(id: number, input: RestaurantNotes): Promise<Restaurant>;
  outreach(offset: number, limit: number): Promise<Outreach[]>;
  markSent(input: SentInput): Promise<Outreach>;
  markPlaceSent(input: PlaceSentInput): Promise<Outreach>;
  changeStatus(id: number, status: Status, tasting?: TastingInput): Promise<Outreach>;
}
export const statuses: Status[] = [
  "sent",
  "scheduling",
  "rejected",
  "tasting",
  "completed",
  "email_approved",
  "email_sending",
  "email_failed",
  "email_unknown",
];
export const transitions: Record<Status, Status[]> = {
  sent: ["scheduling", "rejected"],
  scheduling: ["tasting", "rejected"],
  tasting: ["completed", "rejected"],
  rejected: [],
  completed: [],
  email_approved: [],
  email_sending: [],
  email_failed: [],
  email_unknown: [],
};
/** Backward moves to correct a mistaken status change. */
export const reverts: Record<Status, Status[]> = {
  sent: [],
  scheduling: ["sent"],
  tasting: ["scheduling"],
  completed: ["tasting"],
  rejected: ["sent", "scheduling", "tasting"],
  email_approved: [],
  email_sending: [],
  email_failed: [],
  email_unknown: [],
};
export const canTransition = (from: Status, to: Status) =>
  from === to || transitions[from].includes(to) || reverts[from].includes(to);
export function validProfile(raw: string, channel: Channel): string | null {
  if (channel === "email") return null;
  try {
    const url = new URL(raw);
    const hosts =
      channel === "tiktok"
        ? ["tiktok.com", "www.tiktok.com"]
        : ["instagram.com", "www.instagram.com"];
    return url.protocol === "https:" && hosts.includes(url.hostname) && url.pathname !== "/"
      ? url.href
      : null;
  } catch {
    return null;
  }
}
