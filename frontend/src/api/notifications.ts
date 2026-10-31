import { apiRequest } from "./client";

export type NotificationStatus = "queued" | "sent" | "failed" | "read" | "skipped";

export interface NotificationItem {
  id: string;
  channel: "slack" | "email" | "inapp";
  recipientId: string;
  subject: string;
  status: NotificationStatus;
  error: string;
  createdAt: string;
}

export const listNotifications = (status?: NotificationStatus, limit = 100): Promise<NotificationItem[]> => {
  const params = new URLSearchParams({ limit: String(limit) });
  if (status) params.set("status", status);
  return apiRequest<NotificationItem[]>(`/api/notifications?${params.toString()}`);
};
