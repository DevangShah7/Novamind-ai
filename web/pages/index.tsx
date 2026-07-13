import Head from 'next/head';
import NavBar from '../components/marketing/NavBar';
import Hero from '../components/marketing/Hero';
import FeatureGrid from '../components/marketing/FeatureGrid';
import HowItWorks from '../components/marketing/HowItWorks';
import CTA from '../components/marketing/CTA';
import Footer from '../components/marketing/Footer';

/**
 * Public marketing landing page. Free users land here first;
 * authenticated users hitting "/" should still see the marketing
 * surface (so they can read pricing/docs) — the only difference is
 * the "Get started" button reads "Open app".
 */
export default function Home() {
  return (
    <>
      <Head>
        <title>NovaMind AI — Your AI operating system</title>
        <meta
          name="description"
          content="NovaMind AI is the unified workspace for chat, voice, code, and production-ready APIs. One account, every model, one bill."
        />
      </Head>
      <div className="min-h-screen bg-background text-foreground">
        <NavBar />
        <main>
          <Hero />
          <HowItWorks />
          <FeatureGrid />
          <CTA />
        </main>
        <Footer />
      </div>
    </>
  );
}
