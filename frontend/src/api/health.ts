import { apiRequest } from "./client";

export type ServiceState = "configured" | "not_configured";

export interface HealthResponse {
  status: "ok";
  database: "ok" | "down";
  services: { ai: ServiceState; slack: ServiceState; email: ServiceState };
}

export const getHealth = (): Promise<HealthResponse> => apiRequest<HealthResponse>("/api/health");
