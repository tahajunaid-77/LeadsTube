// Shapes of the data the dashboard works with (shared by the server and the browser).

/** Columns of results/all_channels.csv (every value is text in the CSV). */
export const LEAD_FIELDS = [
  "fit_score", "fit_label", "fit_reason", "channel_name", "channel_link", "country", "subscribers", "total_videos",
  "last_upload", "activity", "content_type", "niche_match", "best_email", "emails", "email_source", "website",
  "linkedin", "facebook", "instagram", "twitter", "tiktok", "podcast", "booking", "other_links",
  "latest_video_title", "recent_videos", "description", "channel_id", "found_by", "first_found", "found_in",
] as const;
export type LeadField = (typeof LEAD_FIELDS)[number];

/** A lead as saved in the CSV. */
export type CsvLead = Record<LeadField, string>;

/** A lead prepared for the UI (numbers parsed, emails split). */
export type Lead = CsvLead & {
  subs: number;
  fit: number;
  /** email was found by web search (worth a double-check) */
  web: boolean;
  emailsList: string[];
};

export type ProfileField = "website" | "linkedin" | "facebook" | "instagram" | "twitter" | "tiktok" | "podcast" | "booking" | "channel_link";

/** A row of results/run_history.csv. */
export type RunRow = Record<string, string> & { run: string; date: string; new_channels: string; with_email: string };

export type RatingValue = "good" | "medium" | "low";
export type Ratings = Record<string, { rating: RatingValue; date: string }>;

export interface LearningStatus {
  active: boolean;
  ratings: number;
  counts: Record<RatingValue, number>;
  needed: number;
  likes: string[];
  dislikes: string[];
  trained_at?: string;
  relearning?: boolean;
}

/** GET /api/data */
export interface DataPayload {
  channels: CsvLead[];
  runs: RunRow[];
  contacted: Record<string, string>;
  ratings: Ratings;
  learning: LearningStatus;
  updated: string | Date | null;
}

export interface Draft {
  to: string;
  subject: string;
  body: string;
  status: "draft" | "sent";
  sent?: string;
  updated?: string;
}

export interface SmartleadRecord {
  campaign_id: number;
  campaign: string;
  email: string;
  date: string;
}

/** GET /api/email/state */
export interface MailState {
  drafts: Record<string, Draft>;
  optOut: string[];
  smartlead: Record<string, SmartleadRecord>;
  sentToday: number;
  limit: number;
  ready: { sending: boolean; smartlead: boolean };
}

/** Your email copy (Email page). */
export interface Copy {
  subject: string;
  body: string;
  updated?: string;
}

export interface KeyUsage {
  name: string;
  label: string;
  used: number;
  left: number;
  quota: number;
}

/** GET /api/limits */
export interface Limits {
  youtube: KeyUsage[];
  resetsInMs: number;
  serper: number | null;
}

export type JobMode = "" | "search" | "emails" | "other";

/** GET /api/run */
export interface Job {
  running: boolean;
  mode: JobMode;
  started: string | null;
  finished: string | null;
  code: number | null;
  log: string;
}

export type FitGoal = "top" | "good" | "possible";

/** POST /api/run */
export interface RunRequest {
  mode: "search" | "emails";
  target?: string;
  countries?: string;
  days?: string;
  keywords?: string;
  fitGoal?: FitGoal;
}

export interface Campaign {
  id: number;
  name: string;
  status?: string;
}

/** Settings sent to the browser (secrets only say whether they are set). */
export interface PublicSettings {
  from_name: string;
  from_email: string;
  smtp_host: string;
  smtp_port: string | number;
  daily_limit: string | number;
  app_password: string;
  app_password_set: boolean;
  smartlead_api_key: string;
  smartlead_api_key_set: boolean;
}

/** GET /api/icp */
export interface IcpPayload {
  text: string;
  updated: string | Date | null;
  canUndo: boolean;
}

/** Personalization fields for one lead (lib/personalize.ts). */
export interface PersonalFields {
  email: string;
  first_name: string;
  greeting_name: string;
  channel_name: string;
  latest_video: string;
  personal_line: string;
  content_kind: string;
  subscribers: string;
  country: string;
  fit_score: string;
  youtube_link: string;
  website: string;
  linkedin: string;
}

/** Personalization fields plus the columns Smartlead expects. */
export type SmartleadRow = PersonalFields & {
  company_name: string;
  linkedin_profile: string;
  location: string;
  email_subject?: string;
  email_body?: string;
};

// ---------------------------------------------------------------- browser-side shared state

export type View = "leads" | "email" | "runs" | "settings";
export type SettingsTab = "icp" | "smartlead" | "sending";

/** The dashboard's loaded data (leads prepared for the UI). */
export interface DashboardData {
  channels: Lead[];
  runs: RunRow[];
  contacted: Record<string, string>;
  ratings: Ratings;
  learning: LearningStatus | null;
  updated: string | Date | null;
  loaded: boolean;
  error: string;
}

/** What the dashboard hands to every page and dialog. */
export interface Shared {
  data: DashboardData;
  mail: MailState;
  copy: Copy;
  toast: (msg: string) => void;
  loadData: () => Promise<void>;
  loadMail: () => Promise<void>;
  setCopy: (copy: Copy) => void;
  setContacted: (links: string[], value: boolean) => Promise<void>;
  setRating: (links: string[], rating: RatingValue | null) => Promise<void>;
  openSettings: (tab?: SettingsTab) => void;
  byLink: Map<string, Lead>;
}
