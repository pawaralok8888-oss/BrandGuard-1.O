import { apiBlob, apiRequest } from "./client";

export type AssetFormat = "" | "social_post" | "web_page" | "email" | "ad" | "product_page" | "blog_article";

export const ASSET_FORMAT_OPTIONS: { value: AssetFormat; label: string }[] = [
  { value: "", label: "Choose asset type" },
  { value: "social_post", label: "Social post" },
  { value: "web_page", label: "Web page" },
  { value: "email", label: "Email" },
  { value: "ad", label: "Ad" },
  { value: "product_page", label: "Product page" },
  { value: "blog_article", label: "Blog article" },
];

export type ContentChannel = "Website" | "Instagram" | "Email" | "Ad";
export type ContentTeam = "Marketing" | "Sales" | "Brand" | "Legal" | "Product" | "Design" | "HR" | "Support";
export type ContentStatus = "Draft" | "Checked" | "Fixing" | "In Review" | "Changes requested" | "Approved" | "Published" | "Needs revalidation";

export interface ContentRecord {
  id: string;
  title: string;
  channel: ContentChannel;
  team: ContentTeam;
  status: ContentStatus;
  bodyText: string;
  bodyHtml: string;
  ownerId: string;
  createdAt: string;
  updatedAt: string;
  currentVersion: number;
  thumbnailArt: string | null;
  imageUrl: string | null;
  altText: string | null;
  format: AssetFormat;
  imageIsLogo: boolean;
}

export interface ContentInput {
  title: string;
  channel: ContentChannel;
  team: ContentTeam;
  bodyText: string;
  bodyHtml: string;
  thumbnailArt?: string | null;
  imageUrl?: string | null;
  altText?: string | null;
  format?: AssetFormat;
}

export type ContentPatch = Partial<Pick<ContentInput, "title" | "channel" | "bodyText" | "bodyHtml" | "altText" | "format">>;

export interface ContentVersion {
  version: number;
  changeType: "initial" | "ai_fix" | "human_edit" | "reviewer_edit" | "restore" | "other";
  actorLabel: string;
  note: string;
  createdAt: string;
  bodyText: string;
}

export interface Revision {
  actorLabel: string;
  kind: "person" | "ai";
  action: string;
  detail: string;
  fromStatus: ContentStatus | null;
  toStatus: ContentStatus | null;
  version: number | null;
  createdAt: string;
}

export const listContent = (): Promise<ContentRecord[]> =>
  apiRequest<ContentRecord[]>("/api/content");

export const createContent = (input: ContentInput): Promise<ContentRecord> =>
  apiRequest<ContentRecord>("/api/content", {
    method: "POST",
    body: JSON.stringify(input),
  });

export const getContent = (id: string): Promise<ContentRecord> =>
  apiRequest<ContentRecord>(`/api/content/${encodeURIComponent(id)}`);

export const updateContent = (id: string, patch: ContentPatch): Promise<ContentRecord> =>
  apiRequest<ContentRecord>(`/api/content/${encodeURIComponent(id)}`, {
    method: "PUT",
    body: JSON.stringify(patch),
  });

export const listVersions = (id: string): Promise<ContentVersion[]> =>
  apiRequest<ContentVersion[]>(`/api/content/${encodeURIComponent(id)}/versions`);

export const listRevisions = (id: string): Promise<Revision[]> =>
  apiRequest<Revision[]>(`/api/content/${encodeURIComponent(id)}/revisions`);

export interface UploadedImage {
  contentId: string;
  imageUrl: string;
  imageWidth: number;
  imageHeight: number;
  altText: string | null;
}

/** Attach an image to a saved draft. The image checks read this file when the draft is checked. */
export const uploadContentImage = (
  id: string,
  file: File,
  altText: string,
  isLogo = false,
): Promise<UploadedImage> => {
  const form = new FormData();
  form.append("file", file);
  form.append("alt_text", altText);
  form.append("is_logo", String(isLogo));
  return apiRequest<UploadedImage>(`/api/content/${encodeURIComponent(id)}/image`, {
    method: "POST",
    body: form,
  });
};

/** Load the stored image for a draft as an object URL the page can show. Revoke it when done. */
export const loadContentImageUrl = async (id: string): Promise<string> => {
  const blob = await apiBlob(`/api/content/${encodeURIComponent(id)}/image`);
  return URL.createObjectURL(blob);
};

/** Remove the saved image from a draft. The server refuses once the content is in review. */
export const deleteContentImage = (id: string): Promise<void> =>
  apiRequest<void>(`/api/content/${encodeURIComponent(id)}/image`, { method: "DELETE" });
