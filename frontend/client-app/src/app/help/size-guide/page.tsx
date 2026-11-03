import { SizeChart } from "@/components/SizeChart";

export const metadata = { title: "Size guide" };

export default function Page() {
  return (
    <article className="mx-auto max-w-3xl px-4 py-10 text-neutral-800">
      <h1 className="font-display text-3xl font-bold text-ink">Size guide</h1>
      <p className="mt-4 leading-relaxed">Measure over light clothing. For bust or chest, measure at the fullest point; for waist, at the narrowest; for hip, at the widest.</p>
      <div className="mt-6"><SizeChart /></div>
    </article>
  );
}
