import type { ApiClient, Outreach, Restaurant } from "./types";
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}
const fallback: Record<number, string> = {
  404: "The requested record does not exist.",
  409: "This record already exists or the status change is not allowed.",
  422: "Please check the submitted information.",
  502: "Google returned an upstream error. Please try again later.",
  503: "Google is unavailable or has not been configured.",
};
export function createApiClient(base: string): ApiClient {
  const cache = new Map<number, Promise<Restaurant>>();
  async function request<T>(path: string, method = "GET", data?: unknown): Promise<T> {
    let response: Response;
    try {
      response = await fetch(`${base.replace(/\/$/, "")}${path}`, {
        method,
        credentials: "include",
        ...(data !== undefined
          ? { headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) }
          : {}),
      });
    } catch {
      throw new ApiError(
        0,
        "The backend cannot be reached. Check the API URL, that FastAPI is running, and its CORS settings.",
      );
    }
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      const detail = body?.detail;
      const readable =
        typeof detail === "string"
          ? detail
          : Array.isArray(detail)
            ? detail
                .map((d: { msg?: string }) => d.msg)
                .filter(Boolean)
                .join("; ")
            : "";
      throw new ApiError(
        response.status,
        readable || fallback[response.status] || `Request failed (${response.status}).`,
      );
    }
    return response.status === 204 ? (undefined as T) : response.json();
  }
  return {
    creatorProfile: () => request("/creator-profile"),
    saveCreatorProfile: (input) => request("/creator-profile", "PATCH", input),
    geminiStatus: () => request("/gemini/status"),
    generateDraft: (input) => request("/outreach/drafts/generate", "POST", input),
    health: () => request("/health"),
    discover: (text_query) => request("/discovery/google-places/new-leads", "POST", { text_query }),
    placeDetails: (id, nameOnly = false) =>
      request(
        `/discovery/google-places/${encodeURIComponent(id)}/details${nameOnly ? "?name_only=true" : ""}`,
      ),
    contacts: (id) =>
      request(`/discovery/google-places/${encodeURIComponent(id)}/contacts`, "POST"),
    gmailStatus: () => request("/gmail/status"),
    gmailConnect: () => request("/gmail/connect", "POST"),
    gmailDisconnect: () => request("/gmail/connection", "DELETE"),
    approveEmail: (input) => request("/outreach/email/approve", "POST", input),
    sendEmail: (id) => request(`/outreach/${id}/email/send`, "POST", { approved: true }),
    createRestaurant: async (input) => {
      const record = await request<Restaurant>("/restaurants", "POST", input);
      cache.set(record.id, Promise.resolve(record));
      return record;
    },
    restaurant: (id) => {
      let pending = cache.get(id);
      if (!pending) {
        pending = request<Restaurant>(`/restaurants/${id}`).catch((error) => {
          cache.delete(id);
          throw error;
        });
        cache.set(id, pending);
      }
      return pending;
    },
    updateRestaurant: async (id, input) => {
      const record = await request<Restaurant>(`/restaurants/${id}`, "PATCH", input);
      cache.set(id, Promise.resolve(record));
      return record;
    },
    outreach: (offset, limit) => {
      if (
        offset < 0 ||
        !Number.isInteger(offset) ||
        limit < 1 ||
        limit > 100 ||
        !Number.isInteger(limit)
      )
        return Promise.reject(new ApiError(422, "Invalid pagination values."));
      return request<Outreach[]>(`/outreach?offset=${offset}&limit=${limit}`);
    },
    markSent: (input) => request("/outreach/mark-sent", "POST", input),
    markPlaceSent: (input) => request("/outreach/from-place/mark-sent", "POST", input),
    changeStatus: (id, status, tasting) =>
      request(`/outreach/${id}/status`, "PATCH", { status, ...(tasting ? { tasting } : {}) }),
  };
}
