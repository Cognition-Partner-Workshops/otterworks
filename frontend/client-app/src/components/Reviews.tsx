"use client";

import { useCallback, useEffect, useState } from "react";
import { call, HttpError } from "@/lib/client";
import type { Review, ReviewPage } from "@/lib/types";
import { useBag } from "./BagProvider";

const SORTS = [["recent", "Most recent"], ["helpful", "Most helpful"], ["highest", "Highest rated"], ["lowest", "Lowest rated"]] as const;
const FITS = ["Runs small", "True to size", "Runs large"];
const VOTER = "os_voter";

function Stars({ value, size = "text-base" }: { value: number; size?: string }) {
  return (
    <span className={`${size} tracking-tight text-amber-500`} aria-label={`${value.toFixed(1)} out of 5 stars`} role="img">
      {"★★★★★".slice(0, Math.round(value))}<span className="text-neutral-300">{"★★★★★".slice(Math.round(value))}</span>
    </span>
  );
}

function voter(): string {
  let v = localStorage.getItem(VOTER);
  if (!v) { v = crypto.randomUUID(); localStorage.setItem(VOTER, v); }
  return v;
}

export function Reviews({ productId, sizes }: { productId: string; sizes: string[] }) {
  const [data, setData] = useState<ReviewPage | null>(null);
  const [sort, setSort] = useState("recent");
  const [rating, setRating] = useState<number | null>(null);
  const [pageSize, setPageSize] = useState(5);
  const [writing, setWriting] = useState(false);
  const [voted, setVoted] = useState<Set<number>>(new Set());

  const load = useCallback(async () => {
    const qs = new URLSearchParams({ sort, pageSize: String(pageSize) });
    if (rating) qs.set("rating", String(rating));
    setData(await call<ReviewPage>(`/products/${productId}/reviews?${qs}`));
  }, [productId, sort, rating, pageSize]);

  useEffect(() => { void load().catch(() => setData(null)); }, [load]);

  if (!data) return null;
  const s = data.summary;
  const maxBar = Math.max(1, ...Object.values(s.histogram));
  const fitTotal = s.fit.runsSmall + s.fit.trueToSize + s.fit.runsLarge;

  async function helpful(r: Review) {
    try {
      const res = await call<{ reviewId: number; helpfulCount: number }>(`/reviews/${r.id}/helpful`, { method: "POST", body: { voter: voter() } });
      setData((d) => d && { ...d, reviews: d.reviews.map((x) => (x.id === r.id ? { ...x, helpfulCount: res.helpfulCount } : x)) });
    } catch (e) {
      if (!(e instanceof HttpError && e.status === 409)) return;
    }
    setVoted((v) => new Set(v).add(r.id));
  }

  return (
    <section id="reviews" className="mt-16 scroll-mt-24" aria-labelledby="reviews-heading" data-testid="reviews">
      <h2 id="reviews-heading" className="font-display text-2xl font-bold">Reviews</h2>
      <div className="mt-6 grid gap-8 md:grid-cols-[280px_1fr]">
        <div>
          <p className="text-4xl font-bold">{s.rating.toFixed(1)}</p>
          <Stars value={s.rating} size="text-xl" />
          <p className="text-sm text-neutral-600">{s.ratingCount} ratings · {s.writtenCount} reviews</p>
          <ul className="mt-4 space-y-1" aria-label="Filter by star rating" data-testid="histogram">
            {[5, 4, 3, 2, 1].map((n) => {
              const c = s.histogram[String(n)] ?? 0;
              return (
                <li key={n}>
                  <button type="button" disabled={c === 0} aria-pressed={rating === n} onClick={() => setRating(rating === n ? null : n)}
                    className={`flex w-full items-center gap-2 text-sm ${rating === n ? "font-semibold" : ""} disabled:opacity-50`} data-testid={`histogram-${n}`}>
                    <span className="w-10 text-left">{n} star</span>
                    <span className="h-2 flex-1 rounded bg-neutral-200"><span className="block h-2 rounded bg-amber-500" style={{ width: `${(c / maxBar) * 100}%` }} /></span>
                    <span className="w-6 text-right">{c}</span>
                  </button>
                </li>
              );
            })}
          </ul>
          {fitTotal > 0 && (
            <div className="mt-6" data-testid="fit-summary">
              <p className="text-sm font-semibold">Fit: {s.fit.verdict}</p>
              <div className="mt-2 flex h-2 overflow-hidden rounded bg-neutral-200" aria-hidden="true">
                <span className="bg-neutral-400" style={{ width: `${(s.fit.runsSmall / fitTotal) * 100}%` }} />
                <span className="bg-teal" style={{ width: `${(s.fit.trueToSize / fitTotal) * 100}%` }} />
                <span className="bg-neutral-600" style={{ width: `${(s.fit.runsLarge / fitTotal) * 100}%` }} />
              </div>
              <p className="mt-1 flex justify-between text-xs text-neutral-600"><span>Small {s.fit.runsSmall}</span><span>True {s.fit.trueToSize}</span><span>Large {s.fit.runsLarge}</span></p>
            </div>
          )}
          <button type="button" className="btn-outline mt-6 w-full" onClick={() => setWriting(true)} data-testid="write-review">Write a review</button>
        </div>
        <div>
          {writing && <ReviewForm productId={productId} sizes={sizes} onDone={async () => { setWriting(false); setSort("recent"); setRating(null); await load(); }} onCancel={() => setWriting(false)} />}
          <div className="flex flex-wrap items-center justify-between gap-2 border-b pb-3">
            <p className="text-sm" aria-live="polite" data-testid="review-count">{data.total} {rating ? `${rating}-star ` : ""}review{data.total === 1 ? "" : "s"}</p>
            <label className="flex items-center gap-2 text-sm">Sort by
              <select value={sort} onChange={(e) => setSort(e.target.value)} className="border px-2 py-1" data-testid="review-sort">
                {SORTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </label>
          </div>
          <ul className="divide-y">
            {data.reviews.map((r) => (
              <li key={r.id} className="py-4" data-testid="review">
                <div className="flex items-center gap-2"><Stars value={r.rating} /><p className="font-semibold">{r.title}</p></div>
                <p className="mt-1 text-xs text-neutral-500">
                  {r.author}{r.location ? `, ${r.location}` : ""} · {new Date(r.createdAt).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
                  {r.verified && <span className="ml-2 font-semibold text-teal">Verified buyer</span>}
                </p>
                <p className="mt-2 text-sm">{r.body}</p>
                {(r.fitNote || r.sizePurchased) && <p className="mt-1 text-xs text-neutral-600">{r.sizePurchased && <>Size bought: {r.sizePurchased}. </>}{r.fitNote && <>Fit: {r.fitNote}</>}</p>}
                <button type="button" disabled={voted.has(r.id)} onClick={() => helpful(r)} className="mt-2 text-xs underline disabled:no-underline disabled:opacity-60" data-testid="helpful">
                  {voted.has(r.id) ? "Thanks for your feedback" : "Helpful?"} ({r.helpfulCount})
                </button>
              </li>
            ))}
          </ul>
          {data.reviews.length < data.total && (
            <button type="button" className="btn-outline mt-4" onClick={() => setPageSize((n) => n + 5)} data-testid="more-reviews">Show more reviews</button>
          )}
        </div>
      </div>
    </section>
  );
}

function ReviewForm({ productId, sizes, onDone, onCancel }: { productId: string; sizes: string[]; onDone: () => void; onCancel: () => void }) {
  const { customer } = useBag();
  const [rating, setRating] = useState(0);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [fit, setFit] = useState("");
  const [size, setSize] = useState("");
  const [author, setAuthor] = useState(customer ? customer.firstName : "");
  const [error, setError] = useState<string | null>(null);
  return (
    <form
      className="mb-6 space-y-3 border p-4"
      aria-label="Write a review"
      onSubmit={async (e) => {
        e.preventDefault();
        if (!rating) { setError("Choose a star rating."); return; }
        setError(null);
        try {
          await call(`/products/${productId}/reviews`, { method: "POST", body: { rating, title, body, fitNote: fit || null, sizePurchased: size || null, author } });
          onDone();
        } catch (err) {
          setError(err instanceof HttpError ? err.message : "Couldn't post your review.");
        }
      }}
      data-testid="review-form"
    >
      <fieldset>
        <legend className="text-sm font-semibold">Your rating</legend>
        <div className="mt-1 flex gap-1" role="radiogroup">
          {[1, 2, 3, 4, 5].map((n) => (
            <button key={n} type="button" role="radio" aria-checked={rating === n} aria-label={`${n} star${n > 1 ? "s" : ""}`} onClick={() => setRating(n)}
              className={`text-2xl ${n <= rating ? "text-amber-500" : "text-neutral-300"}`} data-testid={`rate-${n}`}>★</button>
          ))}
        </div>
      </fieldset>
      <label className="block text-sm">Title<input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={80} className="input mt-1" data-testid="review-title" /></label>
      <label className="block text-sm">Review<textarea value={body} onChange={(e) => setBody(e.target.value)} required minLength={10} maxLength={2000} rows={4} className="input mt-1" data-testid="review-body" /></label>
      <div className="grid grid-cols-2 gap-3">
        <label className="block text-sm">How did it fit?
          <select value={fit} onChange={(e) => setFit(e.target.value)} className="input mt-1" data-testid="review-fit">
            <option value="">Choose</option>{FITS.map((f) => <option key={f}>{f}</option>)}
          </select>
        </label>
        <label className="block text-sm">Size bought
          <select value={size} onChange={(e) => setSize(e.target.value)} className="input mt-1">
            <option value="">Choose</option>{sizes.map((f) => <option key={f}>{f}</option>)}
          </select>
        </label>
      </div>
      <label className="block text-sm">Display name<input value={author} onChange={(e) => setAuthor(e.target.value)} required maxLength={40} className="input mt-1" data-testid="review-author" /></label>
      {error && <p className="text-sm text-sale" role="alert">{error}</p>}
      <div className="flex gap-2">
        <button type="submit" className="btn" data-testid="review-submit">Post review</button>
        <button type="button" className="btn-outline" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  );
}
