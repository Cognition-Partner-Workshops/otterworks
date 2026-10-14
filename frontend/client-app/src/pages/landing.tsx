import { Link } from "react-router-dom";
import { Footer } from "@/components/layout/footer";
import { ConceptBanner } from "@/components/layout/concept-banner";
import { BrandLockup } from "@/components/ui/brand-lockup";
import {
  COMPANY,
  FOUNDING_STORY,
  LEADERSHIP,
  DEPARTMENTS,
  PRODUCTS,
  PRESS_RELEASES,
  CAREERS,
} from "@/lib/corporate";

export default function Home() {
  return (
    <main className="min-h-screen bg-[#f5f5f5] text-gray-800">
      <ConceptBanner />
      <header className="border-b border-[#ddd] bg-white">
        <nav aria-label="Product navigation" className="border-b border-[#ddd]">
          <div className="mx-auto flex h-11 max-w-6xl items-stretch gap-6 overflow-x-auto px-4 text-base">
            <span aria-current="page" className="flex shrink-0 items-center border-b-2 border-[#012169] font-medium text-[#012169]">
              Document Center
            </span>
            <span className="flex shrink-0 items-center text-gray-600">
              Operations Console
            </span>
            <span className="flex shrink-0 items-center text-gray-600">Help</span>
          </div>
        </nav>
        <div className="mx-auto flex min-h-16 max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <Link to="/" aria-label="Bank of America Document Center home">
            <BrandLockup logoSize={32} />
          </Link>
          <nav className="flex w-full items-center justify-end gap-2 sm:w-auto">
            <a
              href="/login"
              className="border border-otter-600 text-sm transition hover:bg-otter-50"
            >
              Sign In
            </a>
            <a
              href="/register"
              className="bg-otter-600 text-sm text-white transition hover:bg-otter-700"
            >
              Create Account
            </a>
          </nav>
        </div>
      </header>

      {/* Hero */}
      <section className="bank-gradient text-white">
        <div className="mx-auto grid max-w-6xl grid-cols-1 items-center gap-10 px-4 py-12 md:grid-cols-[minmax(280px,360px)_1fr] md:gap-16 md:py-16">
          <div className="rounded-[8px] bg-white p-6 text-gray-800 shadow-lg">
            <h2 className="mb-5 text-xl font-semibold text-[#012169]">
              Sign in to your account
            </h2>
            <label htmlFor="landing-email" className="mb-1.5 block text-sm font-medium text-gray-700">
              Email
            </label>
            <input
              id="landing-email"
              type="email"
              placeholder="you@example.com"
              className="mb-4 w-full rounded-[4px] border border-[#333] px-3 py-3 text-sm"
            />
            <label htmlFor="landing-password" className="mb-1.5 block text-sm font-medium text-gray-700">
              Password
            </label>
            <input
              id="landing-password"
              type="password"
              placeholder="Enter your password"
              className="mb-5 w-full rounded-[4px] border border-[#333] px-3 py-3 text-sm"
            />
            <Link
              to="/login"
              className="block w-full bg-otter-600 text-center text-sm font-medium text-white"
            >
              Log in
            </Link>
          </div>
          <div className="py-2">
            <h1 className="mb-5 text-4xl font-light leading-tight text-white sm:text-5xl">
              Document Center
            </h1>
            <p className="max-w-2xl text-lg leading-relaxed text-white/90">
              {COMPANY.tagline}. Secure file storage, collaborative documents and
              enterprise search under a single audit trail.
            </p>
          </div>
        </div>
      </section>

      {/* Our Story */}
      <Section id="story" title="Our Story">
        <div className="max-w-3xl mx-auto space-y-4">
          {FOUNDING_STORY.map((paragraph) => (
            <p key={paragraph.slice(0, 32)} className="text-sm text-gray-600 leading-relaxed">
              {paragraph}
            </p>
          ))}
        </div>
      </Section>

      {/* Products */}
      <Section id="products" title="Products" alt>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {PRODUCTS.map((product) => (
            <Card key={product.name} title={product.name} body={product.description} />
          ))}
        </div>
      </Section>

      {/* Leadership */}
      <Section id="leadership" title="Leadership">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {LEADERSHIP.map((leader) => (
            <div key={leader.name} className="p-5 bg-white rounded border border-gray-300">
              <div className="w-10 h-10 rounded-full bg-otter-600 text-white flex items-center justify-center text-sm font-semibold mb-3">
                {leader.name.split(" ").map((part) => part[0]).join("")}
              </div>
          <h3 className="text-sm font-semibold text-[#012169]">{leader.name}</h3>
              <p className="text-xs uppercase tracking-wider text-accent-600 mb-2">
                {leader.title}
              </p>
              <p className="text-xs text-gray-500 leading-relaxed">{leader.bio}</p>
            </div>
          ))}
        </div>
      </Section>

      {/* Departments */}
      <Section id="departments" title="Departments" alt>
        <div className="overflow-x-auto">
          <table className="w-full bg-white border border-gray-300 text-sm">
            <thead>
              <tr className="bg-otter-50 text-left">
                <th className="px-4 py-2 border-b border-gray-300 text-xs uppercase tracking-wider text-gray-600">
                  Department
                </th>
                <th className="px-4 py-2 border-b border-gray-300 text-xs uppercase tracking-wider text-gray-600">
                  Charter
                </th>
              </tr>
            </thead>
            <tbody>
              {DEPARTMENTS.map((dept) => (
                <tr key={dept.name} className="border-b border-gray-200 last:border-b-0">
                  <td className="px-4 py-2 font-medium text-gray-900 whitespace-nowrap">
                    {dept.name}
                  </td>
                  <td className="px-4 py-2 text-gray-600">{dept.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      {/* Internal updates */}
      <Section id="press" title="Internal Updates">
        <ul className="max-w-3xl mx-auto divide-y divide-gray-200 bg-white border border-gray-300 rounded">
          {PRESS_RELEASES.map((release) => (
            <li key={release.title} className="px-5 py-3">
              <p className="text-xs uppercase tracking-wider text-gray-400">
                {release.date}
              </p>
              <p className="text-sm font-medium text-gray-900">{release.title}</p>
            </li>
          ))}
        </ul>
      </Section>

      {/* Careers */}
      <Section id="careers" title="Careers" alt>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {CAREERS.map((job) => (
            <div
              key={job.role}
              className="p-4 bg-white rounded border border-gray-300 flex items-center justify-between gap-4"
            >
              <div>
                <h3 className="text-sm font-semibold text-gray-900">{job.role}</h3>
                <p className="text-xs text-gray-500">
                  {job.team} · {job.location}
                </p>
              </div>
              <span className="text-xs font-medium text-otter-600 border border-otter-600 rounded px-3 py-1 whitespace-nowrap">
                Open
              </span>
            </div>
          ))}
        </div>
      </Section>

      <div className="bg-white border-t border-gray-300 py-6 text-center">
        <p className="text-xs text-gray-400">
          {COMPANY.name} · Headquartered at {COMPANY.headquarters} · Founded{" "}
          {COMPANY.founded}
        </p>
      </div>

      <Footer />
    </main>
  );
}

function Section({
  id,
  title,
  alt = false,
  children,
}: Readonly<{
  id: string;
  title: string;
  alt?: boolean;
  children: React.ReactNode;
}>) {
  return (
    <section id={id} className={alt ? "bg-white" : "bg-otter-50"}>
      <div className="max-w-6xl mx-auto px-4 py-14">
        <h2 className="mb-2 text-center text-xl font-bold text-[#012169]">{title}</h2>
        <div className="w-10 h-0.5 bg-accent-500 mx-auto mb-8" />
        {children}
      </div>
    </section>
  );
}

function Card({ title, body }: Readonly<{ title: string; body: string }>) {
  return (
    <div className="p-5 bg-white rounded border border-gray-300">
      <h3 className="mb-1.5 text-sm font-semibold text-[#012169]">{title}</h3>
      <p className="text-xs text-gray-500 leading-relaxed">{body}</p>
    </div>
  );
}
