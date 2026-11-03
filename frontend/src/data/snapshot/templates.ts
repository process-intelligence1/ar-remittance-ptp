import type { EmailPreview } from "../types";
import type { SnapRow } from "./rows";

// The clarification e-mail in the customer's language - the same texts as backend/app/outbound.py (TEMPLATES, DEFAULT_QUESTION).
// In the demo edition the e-mail is only shown as a preview: nothing is sent. Tested against data/eval/snapshot_rules_fixture.json.

const TEMPLATES: Record<string, { subject: string; body: string }> = {
  en: { subject: "Clarification needed: {{ detail }}", body: "Dear {{ customer }},\n\nthank you for your payment information. Before we can apply it we need a clarification regarding {{ detail }}:\n\n{{ question }}\n\nPlease reply to this e-mail.\n\nKind regards\nAccounts Receivable" },
  de: { subject: "Rückfrage: {{ detail }}", body: "Sehr geehrte Damen und Herren ({{ customer }}),\n\nvielen Dank für Ihre Zahlungsinformation. Bevor wir sie verbuchen können, benötigen wir eine Klärung zu {{ detail }}:\n\n{{ question }}\n\nBitte antworten Sie auf diese E-Mail.\n\nMit freundlichen Grüßen\nDebitorenbuchhaltung" },
  fr: { subject: "Demande de précisions : {{ detail }}", body: "Madame, Monsieur ({{ customer }}),\n\nmerci pour votre avis de paiement. Avant de pouvoir l'affecter, nous avons besoin d'une précision concernant {{ detail }} :\n\n{{ question }}\n\nMerci de répondre à ce message.\n\nCordialement\nComptabilité clients" },
  es: { subject: "Aclaración necesaria: {{ detail }}", body: "Estimados señores ({{ customer }}):\n\ngracias por la información de su pago. Antes de aplicarlo necesitamos una aclaración sobre {{ detail }}:\n\n{{ question }}\n\nPor favor, responda a este correo.\n\nSaludos cordiales\nCuentas por cobrar" },
  pt: { subject: "Esclarecimento necessário: {{ detail }}", body: "Prezados senhores ({{ customer }}),\n\nobrigado pelas informações do pagamento. Antes de aplicá-lo precisamos de um esclarecimento sobre {{ detail }}:\n\n{{ question }}\n\nPor favor, responda a este e-mail.\n\nAtenciosamente\nContas a receber" },
  ja: { subject: "ご確認のお願い：{{ detail }}", body: "{{ customer }} ご担当者様\n\nお支払いのご連絡をありがとうございます。消込の前に、{{ detail }} についてご確認をお願いいたします。\n\n{{ question }}\n\nこのメールにご返信ください。\n\nよろしくお願いいたします。\n売掛金管理" },
};

export const DEFAULT_QUESTION: Record<string, string> = {
  en: "Could you please confirm the invoice number(s) and the amount this payment is meant for?",
  de: "Könnten Sie bitte die Rechnungsnummer(n) und den Betrag bestätigen, für die diese Zahlung gedacht ist?",
  fr: "Pourriez-vous confirmer le ou les numéros de facture et le montant concernés par ce paiement ?",
  es: "¿Podría confirmar el número o números de factura y el importe al que corresponde este pago?",
  pt: "Poderia confirmar o(s) número(s) da fatura e o valor a que este pagamento se refere?",
  ja: "このお支払いの対象となる請求書番号と金額をご確認いただけますでしょうか。",
};

export const fill = (tpl: string, ctx: Record<string, string>) => tpl.replace(/\{\{ (\w+) \}\}/g, (_, k: string) => ctx[k] ?? "");

/** The "invoice X, USD 1,234.50" wording of the template. */
const detailOf = (r: SnapRow): string => {
  const money = r.amount !== null ? `${r.currency ?? ""} ${r.amount.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`.trim() : "";
  return [r.invoice_ref ? `invoice ${r.invoice_ref}` : "your payment", money].filter(Boolean).join(", ");
};

export const NO_MAIL_NOTE = "Demo edition: nothing is sent - this is only a preview.";

export function renderClarification(r: SnapRow, question?: string): EmailPreview {
  const lang = TEMPLATES[r.export.language] ? r.export.language : "en";
  const ctx = { customer: r.customer_name ?? "customer", detail: detailOf(r), question: question?.trim() || DEFAULT_QUESTION[lang] };
  const intended = r.sender_email ?? "(unknown sender)";
  return {
    subject: `[AR-DEMO][CLARIFICATION → ${intended}] ` + fill(TEMPLATES[lang].subject, ctx),
    body: `[AR-DEMO] ${NO_MAIL_NOTE} In production this e-mail would go to ${intended}.\n\n` + fill(TEMPLATES[lang].body, ctx),
    language: lang, intended_recipient: intended, actual_recipient: "nobody - preview only", template: `clarification_${lang}`,
  };
}

/** For the tests: the template without the demo wrapper. */
export const rawTemplates = TEMPLATES;
