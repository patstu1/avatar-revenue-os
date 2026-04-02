'use client';

import { useEffect, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { brandsApi } from '@/lib/api';
import { copilotApi } from '@/lib/copilot-api';
import {
  AlertTriangle,
  MessageCircle,
  Plus,
  Send,
  Loader2,
} from 'lucide-react';

type Brand = { id: string; name: string };

type Session = {
  id: string;
  title: string;
  created_at: string;
};

type Message = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  grounding_sources?: string[];
  truth_boundaries?: { status: string };
  created_at: string;
};

const QUICK_PROMPTS = [
  { label: 'What needs me?', key: 'what_needs_me', text: 'What needs me right now?' },
  { label: "What's blocked?", key: 'what_blocked', text: 'What is blocked?' },
  { label: 'What failed?', key: 'what_failed', text: 'What failed today?' },
  { label: 'Missing credentials?', key: 'missing_credentials', text: 'What credentials are missing?' },
  { label: 'Active providers?', key: 'active_providers', text: 'Which providers are active?' },
  { label: 'What should launch?', key: 'what_launch', text: 'What should launch next?' },
];

function truthBadgeColor(status: string) {
  const s = String(status).toLowerCase();
  if (s === 'live') return 'bg-emerald-900/40 text-emerald-200 border-emerald-700/50';
  if (s === 'blocked') return 'bg-red-900/40 text-red-200 border-red-700/50';
  if (s === 'recommendation_only') return 'bg-amber-900/40 text-amber-200 border-amber-700/50';
  if (s === 'synthetic') return 'bg-violet-900/40 text-violet-200 border-violet-700/50';
  if (s === 'proxy') return 'bg-blue-900/40 text-blue-200 border-blue-700/50';
  if (s === 'queued') return 'bg-cyan-900/40 text-cyan-200 border-cyan-700/50';
  return 'bg-gray-800 text-gray-300 border-gray-700';
}

function renderMarkdown(text: string | undefined | null) {
  if (!text) return '';
  return text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
}

function errMessage(e: unknown) {
  if (e && typeof e === 'object' && 'response' in e) {
    const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (d) return String(d);
  }
  return e instanceof Error ? e.message : 'Something went wrong';
}

export default function CopilotPage() {
  const queryClient = useQueryClient();
  const [selectedBrandId, setSelectedBrandId] = useState('');
  const [activeSessionId, setActiveSessionId] = useState('');
  const [input, setInput] = useState('');
  const [localMessages, setLocalMessages] = useState<Message[]>([]);
  const [thinking, setThinking] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const { data: brands, isLoading: brandsLoading } = useQuery({
    queryKey: ['brands'],
    queryFn: () => brandsApi.list().then((r) => r.data as Brand[]),
  });

  useEffect(() => {
    if (brands?.length && !selectedBrandId) setSelectedBrandId(String(brands[0].id));
  }, [brands, selectedBrandId]);

  const sessionsQ = useQuery({
    queryKey: ['copilot-sessions', selectedBrandId],
    queryFn: () => copilotApi.listSessions(selectedBrandId).then((r) => r.data as Session[]),
    enabled: Boolean(selectedBrandId),
  });

  const createSessionMut = useMutation({
    mutationFn: (brandId: string) => copilotApi.createSession(brandId),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['copilot-sessions', selectedBrandId] });
      const session = res.data as Session;
      setActiveSessionId(session.id);
      setLocalMessages([]);
    },
  });

  useEffect(() => {
    if (sessionsQ.data?.length && !activeSessionId) {
      setActiveSessionId(sessionsQ.data[0].id);
    } else if (sessionsQ.data && sessionsQ.data.length === 0 && selectedBrandId && !createSessionMut.isPending) {
      createSessionMut.mutate(selectedBrandId);
    }
  }, [sessionsQ.data, activeSessionId, selectedBrandId]);

  const messagesQ = useQuery({
    queryKey: ['copilot-messages', activeSessionId],
    queryFn: () => copilotApi.getMessages(activeSessionId).then((r) => r.data as Message[]),
    enabled: Boolean(activeSessionId),
  });

  useEffect(() => {
    if (messagesQ.data) setLocalMessages(messagesQ.data);
  }, [messagesQ.data]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [localMessages, thinking]);

  const sendMut = useMutation({
    mutationFn: ({ content, quickKey }: { content: string; quickKey?: string }) =>
      copilotApi.sendMessage(activeSessionId, content, quickKey),
    onMutate: ({ content }) => {
      const userMsg: Message = {
        id: `tmp-${Date.now()}`,
        role: 'user',
        content,
        created_at: new Date().toISOString(),
      };
      setLocalMessages((prev) => [...prev, userMsg]);
      setThinking(true);
    },
    onSuccess: (res) => {
      const assistantMsg = res.data as Message;
      setLocalMessages((prev) => [...prev, assistantMsg]);
      setThinking(false);
      queryClient.invalidateQueries({ queryKey: ['copilot-messages', activeSessionId] });
    },
    onError: () => {
      setThinking(false);
    },
  });

  function handleSend() {
    const trimmed = input.trim();
    if (!trimmed || !activeSessionId || sendMut.isPending) return;
    setInput('');
    sendMut.mutate({ content: trimmed });
  }

  function handleQuickPrompt(prompt: (typeof QUICK_PROMPTS)[number]) {
    if (!activeSessionId || sendMut.isPending) return;
    setInput('');
    sendMut.mutate({ content: prompt.text, quickKey: prompt.key });
  }

  function handleNewSession() {
    if (!selectedBrandId || createSessionMut.isPending) return;
    createSessionMut.mutate(selectedBrandId);
  }

  if (brandsLoading) {
    return (
      <div className="min-h-[60vh] rounded-xl border border-gray-800 bg-gray-900 p-8 text-white">
        <div className="h-8 w-80 bg-gray-800 rounded animate-pulse mb-6" />
        <div className="h-40 bg-gray-800/80 rounded animate-pulse" />
        <p className="text-center text-brand-300 mt-8">Loading…</p>
      </div>
    );
  }

  if (!brands?.length) {
    return (
      <div className="rounded-xl border border-gray-800 bg-gray-900 p-12 text-center text-gray-400">
        Create a brand to use the Operator Copilot.
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] rounded-xl border border-gray-800 bg-gray-900 text-white overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-4 border-b border-gray-800 px-6 py-4 shrink-0">
        <MessageCircle className="text-brand-300" size={24} />
        <h1 className="text-xl font-bold">Operator Copilot</h1>
        <div className="ml-auto">
          <select
            aria-label="Select brand"
            className="rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5 text-sm text-white focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500 outline-none"
            value={selectedBrandId}
            onChange={(e) => {
              setSelectedBrandId(e.target.value);
              setActiveSessionId('');
              setLocalMessages([]);
            }}
          >
            {brands.map((b) => (
              <option key={b.id} value={String(b.id)}>{b.name}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Session sidebar */}
        <div className="w-56 shrink-0 border-r border-gray-800 flex flex-col bg-gray-950/50">
          <div className="px-3 py-3 border-b border-gray-800">
            <button
              type="button"
              onClick={handleNewSession}
              disabled={createSessionMut.isPending}
              className="w-full flex items-center justify-center gap-2 rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm font-medium text-brand-300 hover:bg-gray-700 disabled:opacity-50"
            >
              <Plus size={14} />
              New Session
            </button>
          </div>
          <div className="flex-1 overflow-y-auto">
            {sessionsQ.isLoading && (
              <p className="text-xs text-gray-500 px-3 py-4 text-center">Loading…</p>
            )}
            {sessionsQ.data?.map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => { setActiveSessionId(s.id); setLocalMessages([]); }}
                className={`w-full text-left px-3 py-2.5 text-sm border-b border-gray-800/60 transition-colors ${
                  s.id === activeSessionId
                    ? 'bg-brand-600/20 text-brand-300'
                    : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200'
                }`}
              >
                <p className="truncate font-medium text-xs">{s.title}</p>
                <p className="text-[10px] text-gray-600 mt-0.5">
                  {new Date(s.created_at).toLocaleDateString()}
                </p>
              </button>
            ))}
          </div>
        </div>

        {/* Chat area */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
            {messagesQ.isLoading && (
              <p className="text-center text-gray-500 py-8">Loading messages…</p>
            )}
            {localMessages.map((m) => (
              <div
                key={m.id}
                className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[75%] rounded-xl px-4 py-3 text-sm leading-relaxed ${
                    m.role === 'user'
                      ? 'bg-violet-600/30 text-violet-100 border border-violet-500/30'
                      : 'bg-gray-800 text-gray-200 border border-gray-700'
                  }`}
                >
                  <div
                    dangerouslySetInnerHTML={{ __html: renderMarkdown(m.content) }}
                  />
                  {m.role === 'assistant' && m.truth_boundaries?.status && (
                    <span
                      className={`inline-flex items-center rounded-md border px-2 py-0.5 text-[10px] font-medium mt-2 ${truthBadgeColor(m.truth_boundaries.status)}`}
                    >
                      {m.truth_boundaries.status}
                    </span>
                  )}
                  {m.role === 'assistant' && m.grounding_sources && m.grounding_sources.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-2">
                      {m.grounding_sources.map((src, i) => (
                        <span
                          key={i}
                          className="inline-flex rounded border border-gray-700 bg-gray-900 px-1.5 py-0.5 text-[10px] text-gray-500"
                        >
                          {src}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
            {thinking && (
              <div className="flex justify-start">
                <div className="flex items-center gap-2 rounded-xl bg-gray-800 border border-gray-700 px-4 py-3 text-sm text-gray-400">
                  <Loader2 size={14} className="animate-spin" />
                  Thinking…
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Quick prompts */}
          <div className="px-6 pb-2 flex flex-wrap gap-2">
            {QUICK_PROMPTS.map((qp) => (
              <button
                key={qp.key}
                type="button"
                onClick={() => handleQuickPrompt(qp)}
                disabled={sendMut.isPending || !activeSessionId}
                className="rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5 text-xs font-medium text-gray-300 hover:bg-gray-700 hover:text-brand-300 disabled:opacity-40 transition-colors"
              >
                {qp.label}
              </button>
            ))}
          </div>

          {/* Input */}
          <div className="border-t border-gray-800 px-6 py-4 shrink-0">
            {sendMut.isError && (
              <div className="flex items-center gap-2 text-sm text-red-300 mb-3">
                <AlertTriangle size={14} />
                {errMessage(sendMut.error)}
              </div>
            )}
            <form
              onSubmit={(e) => { e.preventDefault(); handleSend(); }}
              className="flex items-center gap-3"
            >
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask the copilot…"
                className="flex-1 rounded-lg border border-gray-700 bg-gray-800 px-4 py-2.5 text-sm text-white placeholder:text-gray-500 focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500 outline-none"
              />
              <button
                type="submit"
                disabled={!input.trim() || sendMut.isPending || !activeSessionId}
                className="rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-brand-500 disabled:opacity-40 transition-colors flex items-center gap-2"
              >
                <Send size={14} />
                Send
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
