export type Status = "sent" | "scheduling" | "rejected" | "tasting" | "completed";
export type Channel = "tiktok" | "instagram";
export interface Place {
  id: string;
  display_name: { text: string };
  formatted_address: string | null;
  primary_type: string | null;
  business_status: string | null;
}
export interface Discovery {
  places: Place[];
  next_page_token: string | null;
}
export interface Restaurant {
  id: number;
  google_place_id: string;
  name: string;
}
export interface Outreach {
  id: number;
  restaurant_id: number;
  channel: Channel;
  status: Status;
  message_text: string;
  sent_at: string;
  updated_at: string;
}
export interface SentInput {
  restaurant_id: number;
  channel: Channel;
  message_text: string;
  confirmed_sent: true;
}
export interface ApiClient {
  health(): Promise<{ status: string }>;
  discover(query: string): Promise<Discovery>;
  createRestaurant(input: Omit<Restaurant, "id">): Promise<Restaurant>;
  restaurant(id: number): Promise<Restaurant>;
  outreach(offset: number, limit: number): Promise<Outreach[]>;
  markSent(input: SentInput): Promise<Outreach>;
  changeStatus(id: number, status: Status): Promise<Outreach>;
}
export const statuses: Status[] = ["sent", "scheduling", "rejected", "tasting", "completed"];
export const transitions: Record<Status, Status[]> = {
  sent: ["scheduling", "rejected"],
  scheduling: ["tasting", "rejected"],
  tasting: ["completed", "rejected"],
  rejected: [],
  completed: [],
};
export const canTransition = (from: Status, to: Status) =>
  from === to || transitions[from].includes(to);
export function validProfile(raw: string, channel: Channel): string | null {
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
