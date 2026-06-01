import SiteNav from "@/components/site-nav";
import Hero from "@/components/hero";
import LedgerSection from "@/components/ledger-section";
import TrustGrid from "@/components/trust-grid";
import Sidebar from "@/components/sidebar";
import SiteFooter from "@/components/site-footer";

export default function Home() {
  return (
    <>
      <SiteNav />
      <div className="mx-auto max-w-7xl px-6 py-16 lg:py-24">
        <div className="lg:grid lg:grid-cols-[1fr_360px] lg:gap-16">
          <article className="space-y-24">
            <Hero />
            <LedgerSection />
            <TrustGrid />
          </article>
          <Sidebar />
        </div>
      </div>
      <SiteFooter />
    </>
  );
}
