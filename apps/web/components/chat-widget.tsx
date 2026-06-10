'use client';

import { useState, useRef, useEffect, type CSSProperties } from 'react';
import { useChat } from '@ai-sdk/react';
import { usePathname } from 'next/navigation';
import { TAB_NAMES } from '@/lib/chat-system-prompt';

const styles: Record<string, CSSProperties> = {
  button: {
    position: 'fixed',
    bottom: '1.5rem',
    right: '1.5rem',
    zIndex: 9999,
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
    borderRadius: '9999px',
    backgroundColor: '#4f46e5',
    padding: '0.75rem 1.25rem',
    color: '#fff',
    border: 'none',
    cursor: 'pointer',
    fontSize: '0.875rem',
    fontWeight: 500,
    boxShadow: '0 4px 12px rgba(79,70,229,0.4)',
  },
  panel: {
    position: 'fixed',
    bottom: '5.5rem',
    right: '1.5rem',
    zIndex: 9999,
    display: 'flex',
    flexDirection: 'column',
    width: '380px',
    maxWidth: 'calc(100vw - 2rem)',
    height: '500px',
    borderRadius: '0.75rem',
    border: '1px solid #e5e7eb',
    backgroundColor: '#fff',
    boxShadow: '0 20px 60px rgba(0,0,0,0.15)',
    overflow: 'hidden',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderBottom: '1px solid #e5e7eb',
    padding: '0.75rem 1rem',
  },
  title: {
    fontSize: '0.875rem',
    fontWeight: 600,
    color: '#111827',
    margin: 0,
  },
  closeBtn: {
    background: 'none',
    border: 'none',
    color: '#9ca3af',
    cursor: 'pointer',
    fontSize: '1rem',
  },
  messageArea: {
    flex: 1,
    overflowY: 'auto',
    padding: '0.75rem 1rem',
    display: 'flex',
    flexDirection: 'column',
    gap: '0.5rem',
  },
  emptyState: {
    fontSize: '0.8rem',
    color: '#9ca3af',
    textAlign: 'center',
    marginTop: '3rem',
  },
  userMsg: {
    fontSize: '0.8rem',
    borderRadius: '0.5rem',
    padding: '0.5rem 0.75rem',
    maxWidth: '85%',
    alignSelf: 'flex-end',
    backgroundColor: '#eef2ff',
    color: '#111827',
  },
  assistantMsg: {
    fontSize: '0.8rem',
    borderRadius: '0.5rem',
    padding: '0.5rem 0.75rem',
    maxWidth: '85%',
    alignSelf: 'flex-start',
    backgroundColor: '#f3f4f6',
    color: '#1f2937',
    lineHeight: 1.5,
  },
  loading: {
    fontSize: '0.8rem',
    color: '#9ca3af',
    padding: '0.5rem 0.75rem',
    alignSelf: 'flex-start',
  },
  errorMsg: {
    fontSize: '0.8rem',
    color: '#ef4444',
    padding: '0.5rem 0.75rem',
    alignSelf: 'flex-start',
  },
  form: {
    borderTop: '1px solid #e5e7eb',
    padding: '0.75rem 1rem',
    display: 'flex',
    gap: '0.5rem',
  },
  input: {
    flex: 1,
    borderRadius: '0.375rem',
    border: '1px solid #d1d5db',
    padding: '0.5rem 0.75rem',
    fontSize: '0.8rem',
    outline: 'none',
  },
  submitBtn: {
    borderRadius: '0.375rem',
    backgroundColor: '#4f46e5',
    padding: '0.5rem 0.75rem',
    fontSize: '0.8rem',
    color: '#fff',
    border: 'none',
    cursor: 'pointer',
  },
  footer: {
    borderTop: '1px solid #e5e7eb',
    padding: '0.5rem 1rem',
    textAlign: 'center',
  },
  footerText: {
    fontSize: '0.7rem',
    color: '#9ca3af',
  },
};

export function ChatWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const pathname = usePathname();
  const tabName = TAB_NAMES[pathname] || 'Unknown Page';

  const { messages, input, handleInputChange, handleSubmit, isLoading, error } = useChat({
    api: '/api/chat',
    body: {
      pageContext: { pathname, tabName },
    },
  });

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <>
      <button
        onClick={() => setIsOpen(!isOpen)}
        aria-label="Open Ask Taste Compiler chat"
        style={styles.button}
      >
        <span aria-hidden="true">💬</span>
        <span>Ask Taste Compiler</span>
      </button>

      {isOpen && (
        <div role="dialog" aria-labelledby="chat-widget-title" style={styles.panel}>
          <div style={styles.header}>
            <h2 id="chat-widget-title" style={styles.title}>
              Ask Taste Compiler
            </h2>
            <button onClick={() => setIsOpen(false)} aria-label="Close chat" style={styles.closeBtn}>
              ✕
            </button>
          </div>

          <div style={styles.messageArea} aria-live="polite">
            {messages.length === 0 && (
              <p style={styles.emptyState}>
                Ask me anything about this page or the Taste Compiler demo.
              </p>
            )}
            {messages.map((msg) => (
              <div
                key={msg.id}
                style={msg.role === 'user' ? styles.userMsg : styles.assistantMsg}
              >
                {msg.content}
              </div>
            ))}
            {isLoading && <div style={styles.loading}>Thinking…</div>}
            {error && <div style={styles.errorMsg}>Something went wrong. Please try again.</div>}
            <div ref={messagesEndRef} />
          </div>

          <form onSubmit={handleSubmit} style={styles.form}>
            <label htmlFor="chat-input" style={{ position: 'absolute', width: 1, height: 1, overflow: 'hidden' }}>
              Message
            </label>
            <input
              id="chat-input"
              type="text"
              value={input}
              onChange={handleInputChange}
              placeholder="Ask a question…"
              style={styles.input}
            />
            <button type="submit" disabled={isLoading || !input.trim()} style={styles.submitBtn}>
              Send
            </button>
          </form>

          <div style={styles.footer}>
            <span style={styles.footerText}>
              Explainer powered by Vercel AI SDK + AI Gateway
            </span>
          </div>
        </div>
      )}
    </>
  );
}
