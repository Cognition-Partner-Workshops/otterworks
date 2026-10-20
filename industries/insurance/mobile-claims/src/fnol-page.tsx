import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Camera, CheckCircle2, Send } from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import {
  LINES_OF_BUSINESS,
  LOSS_CAUSES,
  LOSS_CAUSE_CODES,
  buildClaimsSvcRq,
  lineOfBusinessFor,
  maskTaxId,
  newEnvelope,
  todayLocal,
  type FnolDraft,
} from "./acord";
import { submitFnol } from "./fnol-api";

const required = (label: string) => z.string().trim().min(1, `${label} is required`);

export const fnolSchema = z.object({
  policyNumber: required("Policy number").regex(/^POL-[A-Za-z]+-\d+$/, "Use the POL-LOB-NNNNN format"),
  lineOfBusiness: z.enum(LINES_OF_BUSINESS, { error: "Choose a line of business" }),
  givenName: required("Given name"),
  surname: required("Surname"),
  taxId: z.string().trim().optional(),
  lossDate: required("Loss date")
    .regex(/^\d{4}-\d{2}-\d{2}$/, "Use YYYY-MM-DD")
    .refine((d) => d <= todayLocal(), "Loss date cannot be in the future"),
  causeCode: z.enum(LOSS_CAUSE_CODES as [string, ...string[]], { error: "Choose a cause of loss" }),
  description: required("Description").max(2000),
  estimatedLossAmt: required("Estimated loss").regex(/^\d+(\.\d{1,2})?$/, "Amount like 412 or 412.50"),
  injuries: z.enum(["yes", "no"], { error: "Say whether anyone was injured" }),
  city: required("City"),
  stateProvCd: required("State").regex(/^[A-Za-z]{2}$/, "Two-letter state"),
  postalCode: required("Postal code"),
});

export type FnolFormValues = z.infer<typeof fnolSchema>;

export function toDraft(v: FnolFormValues): FnolDraft {
  return {
    ...v,
    causeCode: v.causeCode as FnolDraft["causeCode"],
    injuries: v.injuries === "yes",
  };
}

const input =
  "w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-otter-500 focus:border-transparent";

function Field({ id, label, error, children }: { id: string; label: string; error?: string; children: React.ReactNode }) {
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-gray-700 mb-1">
        {label}
      </label>
      {children}
      {error && (
        <p role="alert" className="text-xs text-red-600 mt-1">
          {error}
        </p>
      )}
    </div>
  );
}

export default function FnolPage() {
  return (
    <AppShell>
      <FnolForm />
    </AppShell>
  );
}

interface Submitted {
  claimNumber: string;
  rqUID: string;
  maskedTaxId?: string;
}

export function FnolForm({ submit = submitFnol }: { submit?: (xml: string) => Promise<unknown> }) {
  const [submitted, setSubmitted] = useState<Submitted | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setValue,
    watch,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FnolFormValues>({ resolver: zodResolver(fnolSchema) });

  const taxId = watch("taxId");

  const onSubmit = async (values: FnolFormValues) => {
    setServerError(null);
    const env = newEnvelope();
    const xml = buildClaimsSvcRq(toDraft(values), env);
    try {
      await submit(xml);
      setSubmitted({
        claimNumber: env.claimNumber,
        rqUID: env.rqUID,
        maskedTaxId: values.taxId ? maskTaxId(values.taxId) : undefined,
      });
      reset();
    } catch (e) {
      const detail = (e as { response?: { data?: { error?: string } } }).response?.data?.error;
      setServerError(detail ? `Claims hub rejected the notice: ${detail}` : "Could not reach the claims hub. Try again.");
    }
  };

  if (submitted) {
    return (
      <div className="max-w-xl mx-auto space-y-4" data-testid="fnol-receipt">
        <div className="flex items-center gap-2 text-otter-700">
          <CheckCircle2 size={22} />
          <h1 className="text-xl font-bold text-gray-900">Loss reported</h1>
        </div>
        <dl className="bg-white border border-gray-200 rounded-lg p-4 text-sm space-y-2">
          <div className="flex justify-between gap-4">
            <dt className="text-gray-500">Claim number</dt>
            <dd className="font-mono">{submitted.claimNumber}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-gray-500">Request id</dt>
            <dd className="font-mono break-all text-right">{submitted.rqUID}</dd>
          </div>
          {submitted.maskedTaxId && (
            <div className="flex justify-between gap-4">
              <dt className="text-gray-500">Tax id sent</dt>
              <dd className="font-mono">{submitted.maskedTaxId}</dd>
            </div>
          )}
        </dl>
        <button
          type="button"
          onClick={() => setSubmitted(null)}
          className="px-4 py-2 text-sm text-otter-700 bg-otter-50 rounded-lg hover:bg-otter-100"
        >
          Report another loss
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-xl mx-auto space-y-4">
      <div>
        <h1 className="text-xl font-bold text-gray-900">First notice of loss</h1>
        <p className="text-sm text-gray-500 mt-1">Report a loss from the field. It goes straight to the claims hub.</p>
      </div>

      {serverError && (
        <div role="alert" className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          {serverError}
        </div>
      )}

      <form onSubmit={handleSubmit(onSubmit)} noValidate className="bg-white border border-gray-200 rounded-lg p-4 space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Field id="policyNumber" label="Policy number" error={errors.policyNumber?.message}>
            <input
              id="policyNumber"
              className={input}
              placeholder="POL-AUTO-48100"
              autoCapitalize="characters"
              {...register("policyNumber", {
                onChange: (e) => {
                  const lob = lineOfBusinessFor(e.target.value);
                  if (lob) setValue("lineOfBusiness", lob);
                },
              })}
            />
          </Field>
          <Field id="lineOfBusiness" label="Line of business" error={errors.lineOfBusiness?.message}>
            <select id="lineOfBusiness" className={input} defaultValue="" {...register("lineOfBusiness")}>
              <option value="" disabled>
                Choose…
              </option>
              {LINES_OF_BUSINESS.map((l) => (
                <option key={l} value={l}>
                  {l}
                </option>
              ))}
            </select>
          </Field>
          <Field id="givenName" label="Insured given name" error={errors.givenName?.message}>
            <input id="givenName" className={input} autoComplete="off" {...register("givenName")} />
          </Field>
          <Field id="surname" label="Insured surname" error={errors.surname?.message}>
            <input id="surname" className={input} autoComplete="off" {...register("surname")} />
          </Field>
          <Field id="taxId" label="Insured tax id (optional)" error={errors.taxId?.message}>
            <input
              id="taxId"
              className={input}
              inputMode="numeric"
              autoComplete="off"
              placeholder="123-45-6789"
              {...register("taxId")}
            />
            {taxId && (
              <p className="text-xs text-gray-500 mt-1" data-testid="tax-id-preview">
                Sent as <span className="font-mono">{maskTaxId(taxId)}</span>
              </p>
            )}
          </Field>
          <Field id="lossDate" label="Loss date" error={errors.lossDate?.message}>
            <input id="lossDate" type="date" max={todayLocal()} className={input} {...register("lossDate")} />
          </Field>
        </div>

        <Field id="causeCode" label="Cause of loss" error={errors.causeCode?.message}>
          <select id="causeCode" className={input} defaultValue="" {...register("causeCode")}>
            <option value="" disabled>
              Choose…
            </option>
            {LOSS_CAUSES.map((c) => (
              <option key={c.code} value={c.code}>
                {c.code} · {c.label}
              </option>
            ))}
          </select>
        </Field>

        <Field id="description" label="Description" error={errors.description?.message}>
          <textarea id="description" rows={3} className={input} {...register("description")} />
        </Field>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Field id="estimatedLossAmt" label="Estimated loss (USD)" error={errors.estimatedLossAmt?.message}>
            <input id="estimatedLossAmt" inputMode="decimal" className={input} placeholder="412.00" {...register("estimatedLossAmt")} />
          </Field>
          <fieldset>
            <legend className="block text-sm font-medium text-gray-700 mb-1">Anyone injured?</legend>
            <div className="flex gap-4 py-2">
              {(["yes", "no"] as const).map((v) => (
                <label key={v} className="flex items-center gap-1.5 text-sm text-gray-700">
                  <input type="radio" value={v} {...register("injuries")} />
                  {v === "yes" ? "Yes" : "No"}
                </label>
              ))}
            </div>
            {errors.injuries && (
              <p role="alert" className="text-xs text-red-600">
                {errors.injuries.message}
              </p>
            )}
          </fieldset>
        </div>

        <div className="grid grid-cols-3 gap-3">
          <Field id="city" label="City" error={errors.city?.message}>
            <input id="city" className={input} {...register("city")} />
          </Field>
          <Field id="stateProvCd" label="State" error={errors.stateProvCd?.message}>
            <input id="stateProvCd" maxLength={2} autoCapitalize="characters" className={input} {...register("stateProvCd")} />
          </Field>
          <Field id="postalCode" label="Postal code" error={errors.postalCode?.message}>
            <input id="postalCode" inputMode="numeric" className={input} {...register("postalCode")} />
          </Field>
        </div>

        <div className="border border-dashed border-gray-300 rounded-lg p-4 text-center text-sm text-gray-500" data-testid="photos-placeholder">
          <Camera size={20} className="mx-auto mb-1 text-gray-400" />
          <p className="font-medium text-gray-600">Photos</p>
          <p>Photo capture is coming in a later release. Add photos to the claim file after you submit.</p>
          <button type="button" disabled className="mt-2 px-3 py-1.5 text-xs border border-gray-200 rounded text-gray-400 cursor-not-allowed">
            Add photos
          </button>
        </div>

        <button
          type="submit"
          disabled={isSubmitting}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-otter-600 text-white text-sm font-medium rounded-lg hover:bg-otter-700 disabled:opacity-50"
        >
          <Send size={16} />
          {isSubmitting ? "Submitting…" : "Submit first notice of loss"}
        </button>
      </form>
    </div>
  );
}
