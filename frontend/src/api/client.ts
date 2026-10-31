
const API_BASE_URL = (
  import.meta.env.VITE_API_URL || ""
).replace(/\/+$/, "");

const TOKEN_KEY = "brandguard_access_token";

export type UserRole = "creator" | "manager" | "reviewer" | "admin";

export interface DemoUser {
  id: string;
  name: string;
  initials: string;
  role: UserRole;
  title: string;
  team: string;
}

export interface DemoLoginResponse {
  token: string;
  user: DemoUser;
}

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(message: string, status: number, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = getToken();
  const headers = new Headers(options.headers);

  headers.set("Accept", "application/json");

  if (options.body != null && !headers.has("Content-Type") && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  let response: Response;

  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers,
    });
  } catch (error) {
    throw new ApiError(
      `Cannot connect to BrandGuard API at ${API_BASE_URL}. Check that the backend is running.`,
      0,
      error,
    );
  }

  if (!response.ok) {
    let detail: unknown;

    try {
      detail = await response.json();
    } catch {
      detail = await response.text().catch(() => "");
    }

    const message =
      typeof detail === "object" && detail !== null && "detail" in detail
        ? String((detail as { detail: unknown }).detail)
        : `API request failed (${response.status})`;

    throw new ApiError(message, response.status, detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

/** Fetch a file that needs the login token (for example an uploaded image), as a Blob. */
export async function apiBlob(path: string): Promise<Blob> {
  const token = getToken();
  const headers = new Headers();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { headers });
  } catch (error) {
    throw new ApiError(`Cannot connect to BrandGuard API at ${API_BASE_URL}.`, 0, error);
  }
  if (!response.ok) {
    throw new ApiError(`Request failed (${response.status})`, response.status);
  }
  return response.blob();
}

export const api = {
  listDemoUsers(): Promise<DemoUser[]> {
    return apiRequest<DemoUser[]>("/api/auth/demo-users");
  },

  loginAs(userId: string): Promise<DemoLoginResponse> {
    return apiRequest<DemoLoginResponse>("/api/auth/demo-login", {
      method: "POST",
      body: JSON.stringify({ userId }),
    });
  },

  getMe(): Promise<DemoUser> {
    return apiRequest<DemoUser>("/api/auth/me");
  },
};
