'use client';

import { useState, useRef, useEffect } from 'react';

interface Message {
  role: 'user' | 'assistant';
  text: string;
}

const CANNED: Record<string, string> = {
  default:
    "I'm Taste Compiler, EvalWeaver's AI assistant. Ask me how scoring works, what a pay-to-reveal teaser looks like, how creators earn 70% rev-share, or anything else about the platform.",
  persuasive:
    'The "Make it more persuasive" scorer uses Nemotron-based rubrics across 8 axes: hook strength, social proof density, urgency framing, clarity, specificity, CTA sharpness, tone fit, and emotional resonance. Score lift is shown as a teaser before you pay.',
  creator:
    'Creators publish a scorer by describing their goal in plain English on the /create page. EvalWeaver auto-generates rubric axes, estimates demand from 5 000+ simulated personas, and mints the scorer to the marketplace. You earn 70% of every reveal.',
  stripe:
    'Checkout is a single Stripe session. After payment clears the webhook fires, the full reveal is unlocked server-side, and your download link appears — no page refresh needed.',
  demand:
    'Demand is estimated by running your scorer concept through 5 000 synthetic personas segmented by role, market, and willingness-to-pay. The result is a predicted monthly reveal volume and revenue range.',
};

function getReply(input: string): string {
  const q = input.toLowerCase();
  if (q.includes('persuasive') || q.includes('scorer') || q.includes('rubric') || q.includes('score'))
    return CANNED.persuasive;
  if (q.includes('creator') || q.includes('publish') || q.includes('70') || q.includes('earn') || q.includes('revenue'))
    return CANNED.creator;
  if (q.includes('stripe') || q.includes('pay') || q.includes('checkout') || q.includes('reveal') || q.includes('unlock'))
    return CANNED.stripe;
  if (q.includes('demand') || q.includes('persona') || q.includes('simulation') || q.includes('estimate'))
    return CANNED.demand;
  return CANNED.default;
}

const SUGGESTIONS = [
  'How does scoring work?',
  'How do creators earn?',
  'What happens after I pay?',
  'How is demand estimated?',
];

export default function AskWidget() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    { role: 'assistant', text: CANNED.default },
  ]);
  const [input, setInput] = useState('');
  const [typing, setTyping] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 120);
    }
  }, [open]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, typing]);

  function send(text?: string) {
    const msg = (text ?? input).trim();
    if (!msg) return;
    setMessages((m) => [...m, { role: 'user', text: msg }]);
    setInput('');
    setTyping(true);
    setTimeout(() => {
      setTyping(false);
      setMessages((m) => [...m, { role: 'assistant', text: getReply(msg) }]);
    }, 700);
  }

  return (
    <>
      {/* Floating bubble */}
      <button
        onClick={() => setOpen((o) => !o)}
        aria-label={open ? 'Close Taste Compiler chat' : 'Ask Taste Compiler'}
        className="fixed bottom-6 right-6 z-50 flex items-center gap-2 rounded-full border border-white/10 bg-black/90 px-4 py-2.5 text-sm font-medium text-white/80 shadow-xl backdrop-blur-xl transition-all hover:border-brand-500/40 hover:text-white"
      >
        {open ? (
          <>
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
              <path d="M1 1l12 12M13 1L1 13" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            </svg>
            <span>Close</span>
          </>
        ) : (
          <>
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-brand-400 opacity-60" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-brand-400" />
            </span>
            Ask Taste Compiler
          </>
        )}
      </button>

      {/* Chat panel */}
      {open && (
        <div className="fixed bottom-20 right-6 z-50 flex w-[360px] flex-col rounded-2xl border border-white/[0.08] bg-[#0a0a0a] shadow-2xl ring-1 ring-white/[0.04]">
          {/* Header */}
          <div className="flex items-center gap-3 border-b border-white/[0.06] px-4 py-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-brand-500 to-purple-500">
              <span className="text-xs font-bold text-white">TC</span>
            </div>
            <div>
              <p className="text-sm font-semibold leading-none">Taste Compiler</p>
              <p className="mt-0.5 text-xs text-white/40">EvalWeaver AI assistant</p>
            </div>
            <div className="ml-auto flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
              <span className="text-xs text-white/40">online</span>
            </div>
          </div>

          {/* Messages */}
          <div className="flex max-h-72 flex-col gap-3 overflow-y-auto px-4 py-4">
            {messages.map((m, i) => (
              <div
                key={i}
                className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed ${
                    m.role === 'user'
                      ? 'rounded-br-sm bg-brand-600 text-white'
                      : 'rounded-bl-sm bg-white/[0.06] text-white/80'
                  }`}
                >
                  {m.text}
                </div>
              </div>
            ))}
            {typing && (
              <div className="flex justify-start">
                <div className="flex items-center gap-1 rounded-2xl rounded-bl-sm bg-white/[0.06] px-3.5 py-3">
                  {[0, 1, 2].map((d) => (
                    <span
                      key={d}
                      className="h-1.5 w-1.5 rounded-full bg-white/40 animate-bounce"
                      style={{ animationDelay: `${d * 0.15}s` }}
                    />
                  ))}
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Suggestions */}
          {messages.length <= 1 && (
            <div className="flex flex-wrap gap-1.5 border-t border-white/[0.05] px-4 pb-3 pt-3">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs text-white/60 transition hover:border-brand-500/30 hover:text-white/80"
                >
                  {s}
                </button>
              ))}
            </div>
          )}

          {/* Input */}
          <div className="border-t border-white/[0.06] px-3 py-3">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                send();
              }}
              className="flex items-center gap-2"
            >
              <input
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask anything about EvalWeaver…"
                className="flex-1 rounded-lg bg-white/[0.05] px-3 py-2 text-sm text-white placeholder-white/30 outline-none ring-0 transition focus:bg-white/[0.08]"
              />
              <button
                type="submit"
                disabled={!input.trim()}
                aria-label="Send message"
                className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-brand-600 text-white transition hover:bg-brand-500 disabled:opacity-40"
              >
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
                  <path d="M1 7h12M8 2l5 5-5 5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
