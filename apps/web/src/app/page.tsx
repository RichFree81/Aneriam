const CTA_PRIMARY =
  "inline-flex items-center justify-center gap-2 rounded-md font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:opacity-60 disabled:cursor-not-allowed bg-slate-900 text-white hover:bg-slate-800 focus-visible:ring-slate-500";
const CTA_GHOST =
  "inline-flex items-center justify-center gap-2 rounded-md font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:opacity-60 disabled:cursor-not-allowed text-slate-900 hover:bg-slate-100 focus-visible:ring-slate-300";
import Link from "next/link";

const featureCards = [
  {
    title: "Program management",
    blurb: "Milestones, dependencies, and field updates stay in one shared source of truth."
  },
  {
    title: "Cost controls",
    blurb: "Track budgets, change orders, and forecast cash flow before risk becomes delay."
  },
  {
    title: "Compliance ready",
    blurb: "Audit trails, RLS, and AWS-native services keep sensitive project data protected."
  }
] as const;

export default function Home() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-900 via-slate-950 to-black text-slate-100">
      <div className="mx-auto flex max-w-5xl flex-col gap-16 px-6 py-20 sm:py-28">
        <header className="space-y-6">
          <p className="text-sm uppercase tracking-[0.3em] text-slate-400">Aneriam</p>
          <h1 className="text-4xl font-semibold leading-tight sm:text-6xl">
            Project delivery that keeps every stakeholder on the same page.
          </h1>
          <p className="max-w-2xl text-lg text-slate-300">
            Coordinate construction programs, track commercial performance, and ship your next
            build with confidence. Aneriam orchestrates owners, PMs, and site teams working together
            in real time.
          </p>
          <div className="flex flex-col gap-4 sm:flex-row">
            <Link href="/auth/sign-up" className={CTA_PRIMARY}>
              Request early access
            </Link>
            <Link href="/docs" className={CTA_GHOST}>
              Explore the design system
            </Link>
          </div>
        </header>

        <section className="grid gap-6 sm:grid-cols-3">
          {featureCards.map(card => (
            <article
              key={card.title}
              className="rounded-xl border border-slate-800 bg-slate-900/40 p-6 shadow-lg shadow-black/30"
            >
              <h2 className="mb-2 text-xl font-semibold">{card.title}</h2>
              <p className="text-sm text-slate-300">{card.blurb}</p>
            </article>
          ))}
        </section>
      </div>
    </div>
  );
}

