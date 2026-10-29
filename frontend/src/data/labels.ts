import type { ActionCode } from "./types";

export const ACTION_LABELS: Record<ActionCode, string> = {
  CONFIRM_EXTRACT_EXCEL: "Confirm & Extract to Excel",
  ADD_UPDATE_DETAILS: "Add / Update Invoice Details",
  ADD_BSID_DETAILS: "Add BSID Invoice Details",
  REJECT: "Reject Record",
  REQUEST_CLARIFICATION: "Request Clarification",
  ESCALATE_TO_SUPERVISOR: "Escalate to AR Supervisor",
  CLOSE_AS_DUPLICATE: "Close as Duplicate",
  MARK_NON_DUPLICATE: "Mark as Non-Duplicate",
};

export const STATUS_LABELS: Record<string, string> = {
  AUTO_PROCESSED: "Auto Processed",
  PENDING_REVIEW: "Pending Review",
  EXCEPTION: "Exception",
  DUPLICATE: "Duplicate",
  CONFIRMED: "Confirmed",
  RESOLVED: "Resolved",
  REJECTED: "Rejected",
  IGNORED: "Ignored / Out of Scope",
};

export const STATUS_BADGE: Record<string, string> = {
  AUTO_PROCESSED: "badge-auto",
  PENDING_REVIEW: "badge-manual",
  EXCEPTION: "badge-exception",
  DUPLICATE: "badge-duplicate",
  CONFIRMED: "badge-resolved",
  RESOLVED: "badge-resolved",
  REJECTED: "badge-ignored",
  IGNORED: "badge-ignored",
};

export const CLASS_LABELS: Record<string, string> = {
  REMITTANCE: "Remittance",
  PTP: "Promise to Pay",
  DUPLICATE: "Duplicate",
  EXCEPTION: "Exception",
  OUT_OF_SCOPE: "Out of Scope",
};

export const COMPANY_CODES = ["1000", "2000", "3000", "4000", "5000", "6000"];

export const ROLE_LABELS: Record<string, string> = {
  AR_ANALYST: "AR Analyst",
  CASH_APPLICATION: "Cash Application",
  COLLECTIONS_ANALYST: "Collections Analyst",
  AR_SUPERVISOR: "AR Supervisor",
};

export function money(amount: number | null | undefined, currency?: string | null): string {
  if (amount === null || amount === undefined) return "—";
  const n = amount.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 3 });
  return currency ? `${n} ${currency}` : n;
}

export function dateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value);
  return isNaN(d.getTime()) ? value : d.toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });
}

export function dateOnly(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value);
  return isNaN(d.getTime()) ? value : d.toLocaleDateString("en-GB", { dateStyle: "medium" });
}
