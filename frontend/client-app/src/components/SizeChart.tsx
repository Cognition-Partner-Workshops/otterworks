const charts: Record<string, { title: string; head: string[]; rows: string[][] }[]> = {
  women: [{ title: "Women's tops and dresses", head: ["Size", "US", "Bust (in)", "Waist (in)", "Hip (in)"],
    rows: [["XS", "0-2", "32-33", "25-26", "35-36"], ["S", "4-6", "34-35", "27-28", "37-38"], ["M", "8-10", "36-37", "29-30", "39-40"], ["L", "12-14", "38.5-40", "31.5-33", "41.5-43"], ["XL", "16-18", "41.5-43", "34.5-36", "44.5-46"]] },
  { title: "Women's denim", head: ["Waist size", "US", "Waist (in)", "Hip (in)"],
    rows: [["24", "00", "24", "34"], ["26", "2", "26", "36"], ["28", "6", "28", "38"], ["30", "10", "30", "40"], ["32", "14", "32", "42"]] }],
  men: [{ title: "Men's tops", head: ["Size", "Chest (in)", "Neck (in)", "Sleeve (in)"],
    rows: [["XS", "34-35", "13.5", "32"], ["S", "36-38", "14-14.5", "33"], ["M", "39-41", "15-15.5", "34"], ["L", "42-44", "16-16.5", "35"], ["XL", "45-47", "17-17.5", "36"], ["XXL", "48-50", "18-18.5", "37"]] },
  { title: "Men's pants and jeans", head: ["Waist size", "Waist (in)", "Hip (in)"],
    rows: [["28", "28", "35"], ["30", "30", "37"], ["32", "32", "39"], ["34", "34", "41"], ["36", "36", "43"], ["38", "38", "45"]] }],
  kids: [{ title: "Kids", head: ["Size", "Age", "Height (in)", "Weight (lb)"],
    rows: [["4", "4", "39-41", "35-39"], ["6", "5-6", "45-47", "46-51"], ["8", "7-8", "50-52", "60-68"], ["10", "9-10", "54-56", "73-84"], ["12", "11", "57-59", "85-96"], ["14", "12", "60-62", "97-110"]] }],
  baby: [{ title: "Baby", head: ["Size", "Height (in)", "Weight (lb)"],
    rows: [["0-3M", "21-24", "8-12"], ["3-6M", "24-26.5", "12-16"], ["6-12M", "26.5-29", "16-21"], ["12-18M", "29-31", "21-24"], ["18-24M", "31-33", "24-28"]] }],
};

export function SizeChart({ department }: { department?: string }) {
  const keys = department && charts[department] ? [department] : Object.keys(charts);
  return (
    <div className="space-y-6">
      {keys.flatMap((k) => charts[k]).map((c) => (
        <section key={c.title}>
          <h3 className="mb-2 font-semibold">{c.title}</h3>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <thead><tr>{c.head.map((h) => <th key={h} scope="col" className="border-b bg-sand px-3 py-2 text-left">{h}</th>)}</tr></thead>
              <tbody>{c.rows.map((r) => <tr key={r[0]}>{r.map((v, i) => i === 0 ? <th key={i} scope="row" className="border-b px-3 py-2 text-left">{v}</th> : <td key={i} className="border-b px-3 py-2">{v}</td>)}</tr>)}</tbody>
            </table>
          </div>
        </section>
      ))}
      <p className="text-sm text-neutral-600">Between sizes? Size up for a relaxed fit, or check the fit notes in reviews.</p>
    </div>
  );
}
