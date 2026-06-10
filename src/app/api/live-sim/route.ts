import { NextResponse } from 'next/server';
import Stripe from 'stripe';

export const dynamic = 'force-dynamic';

// Persona decision model (simplified from notebook)
const SEGMENT_BASE_INTENT: Record<string, number> = {
  sme_owner_operator: 0.58,
  startup_founder_operator: 0.72,
  marketing_growth_lead: 0.78,
  creator_coach_consultant: 0.75,
  sales_bd_customer_success: 0.65,
  agency_freelancer: 0.70,
  researcher_technical_writer: 0.52,
  student_job_seeker: 0.42,
  skeptical_control: 0.18,
};

const SCORER_CARDS = [
  { scorer_id: 'persuasive_without_hype', title: 'Persuasive Without Hype', price_cents: 499 },
  { scorer_id: 'linkedin_creator_hook', title: 'LinkedIn Creator Hook', price_cents: 699 },
  { scorer_id: 'scientific_but_readable', title: 'Scientific But Readable', price_cents: 499 },
  { scorer_id: 'investor_ready', title: 'Investor-Ready', price_cents: 999 },
];

interface PersonaSim {
  persona_id: string;
  segment: string;
  job_role: string;
  market: string;
  content_job: string;
  ai_comfort: string;
  budget_sensitivity: string;
}

// Small demo panel (5 personas for live sim)
const DEMO_PERSONAS: PersonaSim[] = [
  { persona_id: 'SG_003', segment: 'startup_founder_operator', job_role: 'startup founder', market: 'Singapore', content_job: 'launch post', ai_comfort: 'high', budget_sensitivity: 'low' },
  { persona_id: 'SG_017', segment: 'marketing_growth_lead', job_role: 'growth marketer', market: 'Singapore', content_job: 'landing page', ai_comfort: 'high', budget_sensitivity: 'medium' },
  { persona_id: 'SG_031', segment: 'creator_coach_consultant', job_role: 'LinkedIn creator', market: 'Singapore', content_job: 'thought leadership', ai_comfort: 'medium', budget_sensitivity: 'medium' },
  { persona_id: 'US_008', segment: 'agency_freelancer', job_role: 'copywriter', market: 'United States', content_job: 'client copy', ai_comfort: 'high', budget_sensitivity: 'low' },
  { persona_id: 'US_042', segment: 'skeptical_control', job_role: 'finance analyst', market: 'United States', content_job: 'internal memo', ai_comfort: 'low', budget_sensitivity: 'high' },
];

function scorerFit(persona: PersonaSim, scorer: typeof SCORER_CARDS[0]): number {
  let fit = 0.25;
  if (scorer.scorer_id === 'persuasive_without_hype') {
    if (['startup_founder_operator', 'marketing_growth_lead', 'sales_bd_customer_success', 'agency_freelancer'].includes(persona.segment)) fit += 0.35;
    if (['sales', 'landing', 'launch', 'proposal'].some(k => persona.content_job.includes(k))) fit += 0.20;
  }
  if (scorer.scorer_id === 'linkedin_creator_hook') {
    if (['creator_coach_consultant', 'marketing_growth_lead'].includes(persona.segment)) fit += 0.35;
    if (['post', 'newsletter', 'thought'].some(k => persona.content_job.includes(k))) fit += 0.25;
  }
  if (scorer.scorer_id === 'scientific_but_readable') {
    if (['researcher_technical_writer', 'student_job_seeker'].includes(persona.segment)) fit += 0.30;
    if (['technical', 'grant', 'research'].some(k => persona.content_job.includes(k))) fit += 0.30;
  }
  if (scorer.scorer_id === 'investor_ready') {
    if (['startup_founder_operator', 'agency_freelancer'].includes(persona.segment)) fit += 0.30;
    if (['investor', 'pitch', 'demo', 'update'].some(k => persona.content_job.includes(k))) fit += 0.35;
  }
  if (persona.ai_comfort === 'high') fit += 0.06;
  if (persona.ai_comfort === 'low') fit -= 0.08;
  return Math.max(0.01, Math.min(0.98, fit));
}

function priceSensitivity(persona: PersonaSim, priceCents: number): number {
  const price = priceCents / 100;
  const ref = persona.budget_sensitivity === 'low' ? 12 : persona.budget_sensitivity === 'medium' ? 6 : 3;
  return 1 / (1 + Math.exp((price - ref) / Math.max(1, ref * 0.35)));
}

function revealProbability(persona: PersonaSim, scorer: typeof SCORER_CARDS[0]): number {
  const base = SEGMENT_BASE_INTENT[persona.segment] ?? 0.5;
  const fit = scorerFit(persona, scorer);
  const priceMult = priceSensitivity(persona, scorer.price_cents);
  const tryProb = Math.max(0.01, Math.min(0.98, base * 0.65 + fit * 0.35));
  return Math.max(0.01, Math.min(0.98, tryProb * priceMult * 0.85));
}

function chooseBestScorer(persona: PersonaSim) {
  let best = SCORER_CARDS[0];
  let bestFit = 0;
  for (const card of SCORER_CARDS) {
    const fit = scorerFit(persona, card);
    if (fit > bestFit) { bestFit = fit; best = card; }
  }
  return { scorer: best, fit: bestFit };
}

export async function POST() {
  const stripeKey = process.env.STRIPE_SECRET_KEY;
  if (!stripeKey) {
    return NextResponse.json({ error: 'STRIPE_SECRET_KEY not configured' }, { status: 500 });
  }

  const stripe = new Stripe(stripeKey, { apiVersion: '2024-06-20' as Stripe.LatestApiVersion });
  const results = [];

  for (const persona of DEMO_PERSONAS) {
    const { scorer, fit } = chooseBestScorer(persona);
    const prob = revealProbability(persona, scorer);
    // Deterministic "draw" from persona hash
    const hash = Math.abs(hashCode(`${persona.persona_id}-${scorer.scorer_id}-sim`)) % 10000 / 10000;
    const willBuy = hash < prob;

    const result: Record<string, unknown> = {
      persona_id: persona.persona_id,
      segment: persona.segment,
      job_role: persona.job_role,
      market: persona.market,
      content_job: persona.content_job,
      selected_scorer: scorer.title,
      scorer_id: scorer.scorer_id,
      fit_score: +fit.toFixed(3),
      reveal_probability: +prob.toFixed(3),
      will_buy: willBuy,
      stripe_session_id: null as string | null,
      stripe_session_url: null as string | null,
    };

    if (willBuy) {
      try {
        const session = await stripe.checkout.sessions.create({
          mode: 'payment',
          line_items: [{
            price_data: {
              currency: persona.market === 'Singapore' ? 'sgd' : 'usd',
              product_data: {
                name: `${scorer.title} — Reveal Report`,
                description: `Persona: ${persona.persona_id} (${persona.job_role})`,
              },
              unit_amount: scorer.price_cents,
            },
            quantity: 1,
          }],
          metadata: {
            persona_id: persona.persona_id,
            scorer_id: scorer.scorer_id,
            simulation: 'nemotron_v2_1',
          },
          success_url: `${process.env.VERCEL_URL ? 'https://' + process.env.VERCEL_URL : 'http://localhost:3000'}/live-sim?success=true`,
          cancel_url: `${process.env.VERCEL_URL ? 'https://' + process.env.VERCEL_URL : 'http://localhost:3000'}/live-sim?cancelled=true`,
        });
        result.stripe_session_id = session.id;
        result.stripe_session_url = session.url;
      } catch (e: unknown) {
        result.stripe_error = e instanceof Error ? e.message : 'unknown error';
      }
    }

    results.push(result);
  }

  const buyers = results.filter(r => r.will_buy);
  const totalRevenue = buyers.reduce((sum, r) => {
    const card = SCORER_CARDS.find(c => c.scorer_id === r.scorer_id);
    return sum + (card?.price_cents ?? 0);
  }, 0);

  return NextResponse.json({
    simulation: 'nemotron_persona_v2_1_live',
    personas_total: DEMO_PERSONAS.length,
    buyers: buyers.length,
    bounced: results.filter(r => !r.will_buy).length,
    conversion_rate: +(buyers.length / DEMO_PERSONAS.length).toFixed(3),
    total_revenue_cents: totalRevenue,
    platform_take_cents: Math.round(totalRevenue * 0.30 * 0.7), // net of fees approx
    stripe_sessions_created: buyers.filter(r => r.stripe_session_id).length,
    results,
  });
}

function hashCode(str: string): number {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash |= 0;
  }
  return hash;
}
