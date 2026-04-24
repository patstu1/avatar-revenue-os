'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { gmApi } from '@/lib/gm-api';
import { brandsApi } from '@/lib/api';
import {
  Brain,
  Send,
  Loader2,
  CheckCircle2,
  Play,
  Zap,
  Target,
  Users,
  DollarSign,
  Cpu,
  ChevronDown,
  ChevronRight,
  MessageSquare,
  Plus,
  PanelLeftClose,
  PanelLeftOpen,
  ScanLine,
  HelpCircle,
  TrendingUp,
  Rocket,
  Clock,
  FileText,
  AlertCircle,
} from 'lucide-react';

/* ------------------------------------------------------------------ */
/*  Types                                                             */
/* ------------------------------------------------------------------ */

interface GMMessage {
  id: string;
  role: 'user' | 'gm';
  content: string;
  message_type: string;
  blueprint_data?: Record<string, any> | null;
  created_at?: string;
}

interface MachineState {
  providers: { configured: number; has_llm: boolean; has_publishing: boolean };
  brands: { count: number };
  accounts: { count: number; by_platform: Record<string, number> };
  offers: { count: number };
  content: { count: number };
  revenue: { total_90d: number };
}

interface GMSession {
  id: string;
  title: string;
  status: string;
  machine_phase?: string | null;
  message_count: number;
  created_at: string | null;
}

interface Brand {
  id: string;
  name: string;
}

/* ------------------------------------------------------------------ */
/*  Markdown-like renderer (lightweight, no external dep)             */
/* ------------------------------------------------------------------ */

function renderContent(text: string): string {
  if (!text) return '';
  let html = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    // code blocks
    .replace(/```(\w*)\n([\s\S]*?)```/g, (_m, _lang, code) =>
      `<pre class="bg-gray-950 border border-gray-800 rounded-lg p-3 my-2 overflow-x-auto text-xs font-mono text-gray-300">${code.trim()}</pre>`)
    // inline code
    .replace(/`([^`]+)`/g, '<code class="bg-gray-800 text-cyan-300 px-1.5 py-0.5 rounded text-xs font-mono">$1</code>')
    // headings
    .replace(/^#### (.+)$/gm, '<h4 class="text-sm font-bold text-blue-300 mt-3 mb-1">$1</h4>')
    .replace(/^### (.+)$/gm, '<h3 class="text-base font-bold text-blue-400 mt-3 mb-1">$1</h3>')
    .replace(/^## (.+)$/gm, '<h2 class="text-lg font-bold text-cyan-400 mt-4 mb-2">$1</h2>')
    .replace(/^# (.+)$/gm, '<h1 class="text-xl font-bold text-cyan-300 mt-4 mb-2">$1</h1>')
    // bold + italic
    .replace(/\*\*\*(.+?)\*\*\*/g, '<strong class="text-white"><em>$1</em></strong>')
    .replace(/\*\*(.+?)\*\*/g, '<strong class="text-white">$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    // numbered lists
    .replace(/^\d+\.\s+(.+)$/gm, '<div class="flex gap-2 ml-2 my-0.5"><span class="text-gray-500 select-none">&#8226;</span><span>$1</span></div>')
    // bullet lists
    .replace(/^[-*] (.+)$/gm, '<div class="flex gap-2 ml-2 my-0.5"><span class="text-cyan-600 select-none">-</span><span>$1</span></div>')
    // horizontal rule
    .replace(/^---$/gm, '<hr class="border-gray-800 my-3" />')
    // double newlines to breaks
    .replace(/\n\n/g, '<br/><br/>')
    // single newline (preserve within paragraphs)
    .replace(/\n/g, '<br/>');
  return html;
}

/* ------------------------------------------------------------------ */
/*  Action Badge                                                      */
/* ------------------------------------------------------------------ */

function ActionBadge({ type }: { type: string }) {
  const colors: Record<string, string> = {
    blueprint_presentation: 'bg-amber-900/30 text-amber-400 border-amber-800/40',
    blueprint_revision: 'bg-purple-900/30 text-purple-400 border-purple-800/40',
    execution_report: 'bg-green-900/30 text-green-400 border-green-800/40',
    conversation: 'bg-gray-800/50 text-gray-400 border-gray-700/40',
    scan: 'bg-cyan-900/30 text-cyan-400 border-cyan-800/40',
  };
  const labels: Record<string, string> = {
    blueprint_presentation: 'BLUEPRINT',
    blueprint_revision: 'REVISION',
    execution_report: 'EXECUTION',
    conversation: 'RESPONSE',
    scan: 'SCAN',
  };
  const cls = colors[type] || colors.conversation;
  const label = labels[type] || type.replace(/_/g, ' ').toUpperCase();

  return (
    <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded border ${cls}`}>
      {label}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/*  Blueprint Actions (collapsible within message)                    */
/* ------------------------------------------------------------------ */

function BlueprintActions({ data }: { data: Record<string, any> }) {
  const [open, setOpen] = useState(false);
  const sections = Object.entries(data).filter(
    ([, v]) => v !== null && v !== undefined && typeof v === 'object'
  );
  if (sections.length === 0) return null;

  return (
    <div className="mt-2 border border-gray-800/60 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-3 py-2 text-xs text-gray-400 hover:text-gray-200 hover:bg-gray-800/40 transition-colors"
      >
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        <Zap size={12} className="text-cyan-500" />
        <span className="font-mono">Blueprint data ({sections.length} sections)</span>
      </button>
      {open && (
        <div className="px-3 pb-3 space-y-2 border-t border-gray-800/40">
          {sections.map(([key, value]) => (
            <div key={key} className="mt-2">
              <div className="text-[10px] font-mono text-cyan-500 uppercase mb-1">
                {key.replace(/_/g, ' ')}
              </div>
              <pre className="text-[11px] text-gray-400 bg-gray-950/80 rounded p-2 overflow-x-auto max-h-40 overflow-y-auto">
                {typeof value === 'string' ? value : JSON.stringify(value, null, 2)}
              </pre>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Execution Panel (inline in sidebar)                               */
/* ------------------------------------------------------------------ */

function ExecutionPanel({
  blueprintStatus,
  onApprove,
  onExecute,
  executing,
}: {
  blueprintStatus: string | null;
  onApprove: () => void;
  onExecute: (step: string) => void;
  executing: string | null;
}) {
  if (!blueprintStatus) return null;

  const steps = [
    { key: 'create_brands', label: 'Create Brands', icon: Target },
    { key: 'create_accounts', label: 'Create Accounts', icon: Users },
    { key: 'create_offers', label: 'Create Offers', icon: DollarSign },
  ];

  return (
    <div className="border-t border-gray-800/60 pt-3 mt-3">
      <div className="flex items-center gap-2 text-xs font-bold text-cyan-400 mb-2 px-1">
        <Zap size={14} />
        Blueprint Execution
      </div>

      {blueprintStatus === 'proposed' && (
        <button
          onClick={onApprove}
          className="w-full py-2 bg-gradient-to-r from-green-600 to-emerald-600 text-white font-bold rounded-lg hover:from-green-500 hover:to-emerald-500 transition-all text-xs flex items-center justify-center gap-2"
        >
          <CheckCircle2 size={14} />
          Approve Blueprint
        </button>
      )}

      {(blueprintStatus === 'approved' || blueprintStatus === 'executing') && (
        <div className="space-y-1.5">
          {steps.map((step) => (
            <button
              key={step.key}
              onClick={() => onExecute(step.key)}
              disabled={executing === step.key}
              className="w-full py-1.5 px-2.5 bg-gray-900 border border-gray-800 rounded-lg text-xs text-gray-300 hover:border-cyan-700 hover:text-white transition-all flex items-center gap-2 disabled:opacity-50"
            >
              {executing === step.key ? (
                <Loader2 size={12} className="animate-spin text-cyan-400" />
              ) : (
                <step.icon size={12} className="text-gray-500" />
              )}
              {step.label}
              <Play size={10} className="ml-auto text-gray-600" />
            </button>
          ))}
        </div>
      )}

      {blueprintStatus === 'completed' && (
        <div className="text-xs text-green-400 flex items-center gap-2 px-1">
          <CheckCircle2 size={14} />
          Blueprint fully executed
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Message Bubble                                                    */
/* ------------------------------------------------------------------ */

function MessageBubble({ message }: { message: GMMessage }) {
  const isGM = message.role === 'gm';

  return (
    <div className={`flex ${isGM ? 'justify-start' : 'justify-end'} group`}>
      <div className={`max-w-[80%] lg:max-w-[70%] ${isGM ? '' : ''}`}>
        {/* GM avatar + header */}
        {isGM && (
          <div className="flex items-center gap-2 mb-1.5">
            <div className="w-7 h-7 rounded-full bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center shrink-0 shadow-lg shadow-cyan-900/20">
              <Brain size={14} className="text-white" />
            </div>
            <span className="text-[10px] font-mono text-cyan-400/80 uppercase tracking-wider">
              Strategic GM
            </span>
            {message.message_type !== 'conversation' && (
              <ActionBadge type={message.message_type} />
            )}
            {message.created_at && (
              <span className="text-[10px] text-gray-600 font-mono opacity-0 group-hover:opacity-100 transition-opacity">
                {new Date(message.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
            )}
          </div>
        )}

        {/* User timestamp */}
        {!isGM && message.created_at && (
          <div className="flex justify-end mb-1">
            <span className="text-[10px] text-gray-600 font-mono opacity-0 group-hover:opacity-100 transition-opacity">
              {new Date(message.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
          </div>
        )}

        {/* Message body */}
        <div
          className={`rounded-2xl px-4 py-3 text-sm leading-relaxed ${
            isGM
              ? 'bg-gray-900/80 border border-gray-800/60 text-gray-200 rounded-tl-md'
              : 'bg-cyan-900/30 border border-cyan-800/40 text-white rounded-tr-md'
          }`}
          dangerouslySetInnerHTML={{
            __html: renderContent(message.content),
          }}
        />

        {/* Blueprint data collapsible */}
        {isGM && message.blueprint_data && Object.keys(message.blueprint_data).length > 0 && (
          <BlueprintActions data={message.blueprint_data} />
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Typing Indicator                                                  */
/* ------------------------------------------------------------------ */

function TypingIndicator() {
  return (
    <div className="flex justify-start">
      <div className="flex items-center gap-2">
        <div className="w-7 h-7 rounded-full bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center shrink-0">
          <Brain size={14} className="text-white animate-pulse" />
        </div>
        <div className="bg-gray-900/80 border border-gray-800/60 rounded-2xl rounded-tl-md px-4 py-3 flex items-center gap-1.5">
          <div className="w-2 h-2 rounded-full bg-cyan-400 animate-bounce" style={{ animationDelay: '0ms' }} />
          <div className="w-2 h-2 rounded-full bg-cyan-400 animate-bounce" style={{ animationDelay: '150ms' }} />
          <div className="w-2 h-2 rounded-full bg-cyan-400 animate-bounce" style={{ animationDelay: '300ms' }} />
        </div>
        <span className="text-[10px] font-mono text-cyan-400/60">analyzing...</span>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Status Bar                                                        */
/* ------------------------------------------------------------------ */

function StatusBar({ state }: { state: MachineState }) {
  const items = [
    { icon: DollarSign, label: 'Revenue (90d)', value: `$${state.revenue.total_90d.toFixed(0)}`, color: 'text-green-400' },
    { icon: Users, label: 'Accounts', value: String(state.accounts.count), color: 'text-blue-400' },
    { icon: FileText, label: 'Content', value: String(state.content.count), color: 'text-purple-400' },
    { icon: Cpu, label: 'Providers', value: String(state.providers.configured), color: 'text-cyan-400' },
    { icon: Target, label: 'Brands', value: String(state.brands.count), color: 'text-amber-400' },
  ];

  return (
    <div className="flex items-center gap-1 sm:gap-3 flex-wrap">
      {items.map((item) => (
        <div
          key={item.label}
          className="flex items-center gap-1.5 bg-gray-900/60 border border-gray-800/40 rounded-lg px-2 py-1 sm:px-2.5 sm:py-1.5"
        >
          <item.icon size={12} className={item.color} />
          <span className="text-[10px] sm:text-xs font-mono text-gray-400 hidden lg:inline">{item.label}</span>
          <span className={`text-[11px] sm:text-xs font-bold ${item.color}`}>{item.value}</span>
        </div>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Conversation Sidebar                                              */
/* ------------------------------------------------------------------ */

function ConversationSidebar({
  sessions,
  activeSessionId,
  onSelect,
  onNew,
  open,
  onToggle,
}: {
  sessions: GMSession[];
  activeSessionId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  open: boolean;
  onToggle: () => void;
}) {
  return (
    <>
      {/* Toggle button (always visible) */}
      <button
        onClick={onToggle}
        className="absolute top-3 left-3 z-20 p-1.5 rounded-lg bg-gray-900/80 border border-gray-800/40 text-gray-400 hover:text-white hover:border-gray-700 transition-colors lg:hidden"
        title={open ? 'Close sidebar' : 'Open sidebar'}
      >
        {open ? <PanelLeftClose size={16} /> : <PanelLeftOpen size={16} />}
      </button>

      {/* Sidebar panel */}
      <div
        className={`
          ${open ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
          absolute lg:relative z-10 h-full
          w-64 shrink-0 bg-gray-950 lg:bg-gray-950/50 border-r border-gray-800/60
          flex flex-col transition-transform duration-200 ease-in-out
        `}
      >
        {/* Header */}
        <div className="p-3 border-b border-gray-800/60 flex items-center justify-between">
          <h3 className="text-xs font-mono text-gray-400 uppercase tracking-wider">Conversations</h3>
          <button
            onClick={onNew}
            className="p-1 rounded-md text-gray-500 hover:text-cyan-400 hover:bg-gray-800/60 transition-colors"
            title="New conversation"
          >
            <Plus size={16} />
          </button>
        </div>

        {/* Session list */}
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {sessions.length === 0 && (
            <p className="text-xs text-gray-600 text-center mt-4 px-2">No conversations yet</p>
          )}
          {sessions.map((s) => (
            <button
              key={s.id}
              onClick={() => { onSelect(s.id); onToggle(); }}
              className={`w-full text-left px-3 py-2 rounded-lg text-xs transition-colors flex items-start gap-2 ${
                s.id === activeSessionId
                  ? 'bg-cyan-900/20 border border-cyan-800/30 text-white'
                  : 'text-gray-400 hover:bg-gray-800/40 hover:text-gray-200 border border-transparent'
              }`}
            >
              <MessageSquare size={12} className="mt-0.5 shrink-0" />
              <div className="min-w-0 flex-1">
                <div className="truncate font-medium">{s.title}</div>
                <div className="text-[10px] text-gray-600 mt-0.5 flex items-center gap-1">
                  <Clock size={9} />
                  {s.created_at ? new Date(s.created_at).toLocaleDateString() : 'Unknown'}
                  <span className="text-gray-700">|</span>
                  {s.message_count} msgs
                </div>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Overlay for mobile when sidebar is open */}
      {open && (
        <div
          className="absolute inset-0 z-[5] bg-black/40 lg:hidden"
          onClick={onToggle}
        />
      )}
    </>
  );
}

/* ------------------------------------------------------------------ */
/*  Quick Action Chips                                                */
/* ------------------------------------------------------------------ */

const QUICK_ACTIONS = [
  { label: 'Scan the machine', msg: 'Scan the full machine state and tell me where things stand.', icon: ScanLine },
  { label: 'What should I do next?', msg: 'What is the single highest-leverage thing I should do right now?', icon: HelpCircle },
  { label: 'Show revenue', msg: 'Show me the current revenue trajectory and breakdown.', icon: TrendingUp },
  { label: 'Scale plan', msg: 'What is the optimal scaling plan from here? What signals should trigger the next phase?', icon: Rocket },
];

/* ------------------------------------------------------------------ */
/*  Brand Selector                                                    */
/* ------------------------------------------------------------------ */

function BrandSelector({
  brands,
  selectedBrandId,
  onChange,
}: {
  brands: Brand[];
  selectedBrandId: string | null;
  onChange: (id: string | null) => void;
}) {
  return (
    <div className="relative">
      <select
        value={selectedBrandId || 'portfolio'}
        onChange={(e) => onChange(e.target.value === 'portfolio' ? null : e.target.value)}
        className="appearance-none bg-gray-900/80 border border-gray-800/60 text-gray-300 text-xs font-mono rounded-lg pl-3 pr-8 py-1.5 focus:border-cyan-600 focus:ring-1 focus:ring-cyan-600 outline-none cursor-pointer hover:border-gray-700 transition-colors"
      >
        <option value="portfolio">Portfolio (all brands)</option>
        {brands.map((b) => (
          <option key={b.id} value={b.id}>{b.name}</option>
        ))}
      </select>
      <ChevronDown size={12} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none" />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main GM Page                                                      */
/* ------------------------------------------------------------------ */

export default function GMPage() {
  const [machineState, setMachineState] = useState<MachineState | null>(null);
  const [messages, setMessages] = useState<GMMessage[]>([]);
  const [sessions, setSessions] = useState<GMSession[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [selectedBrandId, setSelectedBrandId] = useState<string | null>(null);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(true);
  const [thinking, setThinking] = useState(false);
  const [blueprintStatus, setBlueprintStatus] = useState<string | null>(null);
  const [executing, setExecuting] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, thinking]);

  // Auto-resize textarea
  const adjustTextareaHeight = useCallback(() => {
    const ta = textareaRef.current;
    if (ta) {
      ta.style.height = 'auto';
      ta.style.height = `${Math.min(ta.scrollHeight, 160)}px`;
    }
  }, []);

  // Initialize
  useEffect(() => {
    let cancelled = false;

    async function init() {
      try {
        // Parallel: machine state + sessions + brands
        const [stateRes, sessionsRes, brandsRes] = await Promise.allSettled([
          gmApi.getMachineState(),
          gmApi.listSessions(),
          brandsApi.list(),
        ]);

        if (cancelled) return;

        // Machine state
        if (stateRes.status === 'fulfilled') {
          setMachineState(stateRes.value.data);
        }

        // Brands
        if (brandsRes.status === 'fulfilled') {
          const brandData = brandsRes.value.data;
          const brandList = Array.isArray(brandData) ? brandData : (brandData?.items || brandData?.brands || []);
          setBrands(brandList);
        }

        // Sessions
        if (sessionsRes.status === 'fulfilled') {
          const sessionList = sessionsRes.value.data as GMSession[];
          setSessions(sessionList);

          if (sessionList.length > 0) {
            // Resume most recent session
            const sid = sessionList[0].id;
            setSessionId(sid);
            const msgsRes = await gmApi.getMessages(sid);
            if (cancelled) return;
            setMessages(msgsRes.data as GMMessage[]);

            // Check blueprint status
            try {
              const bpRes = await gmApi.getBlueprint();
              setBlueprintStatus(bpRes.data?.status || null);
            } catch {
              // No blueprint yet
            }
          } else {
            // First visit: create session + auto-generate blueprint
            setThinking(true);
            const createRes = await gmApi.createSession();
            if (cancelled) return;
            const data = createRes.data;
            setSessionId(data.session.id);
            setMessages([data.initial_message as GMMessage]);
            setSessions([{
              id: data.session.id,
              title: data.session.title || 'GM Strategy Session',
              status: 'active',
              message_count: 1,
              created_at: new Date().toISOString(),
            }]);
            if (data.initial_message.blueprint_data) {
              setBlueprintStatus('proposed');
            }
            setThinking(false);
          }
        }
      } catch (err) {
        console.error('GM init failed:', err);
        setError('Failed to initialize GM. Check your connection and try again.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    init();
    return () => { cancelled = true; };
  }, []);

  // Refresh machine state periodically (every 60s)
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const res = await gmApi.getMachineState();
        setMachineState(res.data);
      } catch { /* silent */ }
    }, 60_000);
    return () => clearInterval(interval);
  }, []);

  // Load a specific session
  const loadSession = useCallback(async (sid: string) => {
    if (sid === sessionId) return;
    setMessages([]);
    setSessionId(sid);
    setThinking(true);
    try {
      const msgsRes = await gmApi.getMessages(sid);
      setMessages(msgsRes.data as GMMessage[]);
    } catch (err) {
      console.error('Load session failed:', err);
    } finally {
      setThinking(false);
    }
  }, [sessionId]);

  // Create new session
  const createNewSession = useCallback(async () => {
    setThinking(true);
    setMessages([]);
    setError(null);
    try {
      const createRes = await gmApi.createSession();
      const data = createRes.data;
      setSessionId(data.session.id);
      setMessages([data.initial_message as GMMessage]);

      const newSession: GMSession = {
        id: data.session.id,
        title: data.session.title || 'GM Strategy Session',
        status: 'active',
        message_count: 1,
        created_at: new Date().toISOString(),
      };
      setSessions((prev) => [newSession, ...prev]);

      if (data.initial_message.blueprint_data) {
        setBlueprintStatus('proposed');
      }
    } catch (err) {
      console.error('Create session failed:', err);
      setError('Failed to create new conversation.');
    } finally {
      setThinking(false);
    }
  }, []);

  // Send message
  const handleSend = useCallback(async () => {
    if (!input.trim() || !sessionId || thinking) return;
    const userText = input.trim();
    setInput('');
    setError(null);
    setThinking(true);

    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }

    // Optimistic user message
    const tempUserMsg: GMMessage = {
      id: `temp-${Date.now()}`,
      role: 'user',
      content: userText,
      message_type: 'conversation',
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);

    try {
      const res = await gmApi.sendMessage(sessionId, userText);
      const data = res.data;
      setMessages((prev) => [
        ...prev.filter((m) => m.id !== tempUserMsg.id),
        data.user_message as GMMessage,
        data.gm_message as GMMessage,
      ]);

      if (data.gm_message.message_type === 'blueprint_revision') {
        setBlueprintStatus('proposed');
      }

      // Update session message count
      setSessions((prev) =>
        prev.map((s) =>
          s.id === sessionId ? { ...s, message_count: (s.message_count || 0) + 2 } : s
        )
      );

      // Refresh machine state
      try {
        const stateRes = await gmApi.getMachineState();
        setMachineState(stateRes.data);
      } catch { /* silent */ }
    } catch (err) {
      console.error('Send failed:', err);
      setError('Message failed to send. Try again.');
      // Remove optimistic message
      setMessages((prev) => prev.filter((m) => m.id !== tempUserMsg.id));
      setInput(userText);
    } finally {
      setThinking(false);
      textareaRef.current?.focus();
    }
  }, [input, sessionId, thinking]);

  // Handle keyboard shortcuts
  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }, [handleSend]);

  // Approve blueprint
  const handleApprove = useCallback(async () => {
    try {
      await gmApi.approveBlueprint();
      setBlueprintStatus('approved');
    } catch (err) {
      console.error('Approve failed:', err);
    }
  }, []);

  // Execute step
  const handleExecute = useCallback(async (stepKey: string) => {
    setExecuting(stepKey);
    try {
      const res = await gmApi.executeStep(stepKey);
      const result = res.data;

      const execMsg: GMMessage = {
        id: `exec-${Date.now()}`,
        role: 'gm',
        content: result.success
          ? `**Executed: ${stepKey.replace(/_/g, ' ')}**\n\n${(result.results || []).map((r: string) => `- ${r}`).join('\n')}\n\n${result.created || 0} entities created.`
          : `**Execution failed:** ${result.error}`,
        message_type: 'execution_report',
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, execMsg]);

      // Refresh
      try {
        const stateRes = await gmApi.getMachineState();
        setMachineState(stateRes.data);
      } catch { /* silent */ }
      try {
        const bpRes = await gmApi.getBlueprint();
        setBlueprintStatus(bpRes.data?.status || 'executing');
      } catch { /* ignore */ }
    } catch (err) {
      console.error('Execute failed:', err);
    } finally {
      setExecuting(null);
    }
  }, []);

  // Quick action handler
  const handleQuickAction = useCallback((msg: string) => {
    setInput(msg);
    textareaRef.current?.focus();
  }, []);

  /* ---------------------------------------------------------------- */
  /*  Loading State                                                   */
  /* ---------------------------------------------------------------- */

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-120px)]">
        <div className="flex flex-col items-center gap-4">
          <div className="w-16 h-16 rounded-full bg-gradient-to-br from-cyan-500/20 to-blue-500/20 border border-cyan-800/40 flex items-center justify-center">
            <Brain size={28} className="text-cyan-400 animate-pulse" />
          </div>
          <p className="text-sm text-gray-400 font-mono">GM scanning machine state...</p>
          <div className="flex gap-1">
            <div className="w-1.5 h-1.5 rounded-full bg-cyan-500 animate-bounce" style={{ animationDelay: '0ms' }} />
            <div className="w-1.5 h-1.5 rounded-full bg-cyan-500 animate-bounce" style={{ animationDelay: '150ms' }} />
            <div className="w-1.5 h-1.5 rounded-full bg-cyan-500 animate-bounce" style={{ animationDelay: '300ms' }} />
          </div>
        </div>
      </div>
    );
  }

  /* ---------------------------------------------------------------- */
  /*  Main Render                                                     */
  /* ---------------------------------------------------------------- */

  return (
    <div className="flex flex-col h-[calc(100vh-120px)] -m-8 bg-gray-950">
      {/* ---- Top Bar ---- */}
      <div className="shrink-0 border-b border-gray-800/60 bg-gray-950/95 backdrop-blur-sm px-4 py-2.5 flex items-center justify-between gap-3 z-10">
        {/* Left: logo + title + brand selector */}
        <div className="flex items-center gap-3 min-w-0">
          {/* Mobile sidebar toggle spacer */}
          <div className="w-8 lg:hidden" />
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center shrink-0 shadow-lg shadow-cyan-900/20">
            <Brain size={20} className="text-white" />
          </div>
          <div className="hidden sm:block min-w-0">
            <h1 className="text-base font-black text-white leading-tight">Strategic GM</h1>
            <p className="text-[9px] text-gray-500 font-mono uppercase tracking-wider truncate">
              Conversational Operating Brain
            </p>
          </div>
          <div className="hidden md:block ml-2">
            <BrandSelector brands={brands} selectedBrandId={selectedBrandId} onChange={setSelectedBrandId} />
          </div>
        </div>

        {/* Right: status bar */}
        <div className="hidden sm:block">
          {machineState && <StatusBar state={machineState} />}
        </div>
      </div>

      {/* ---- Main Content: Sidebar + Chat ---- */}
      <div className="flex flex-1 min-h-0 relative">
        {/* Conversation sidebar (hidden on mobile by default) */}
        <ConversationSidebar
          sessions={sessions}
          activeSessionId={sessionId}
          onSelect={loadSession}
          onNew={createNewSession}
          open={sidebarOpen}
          onToggle={() => setSidebarOpen(!sidebarOpen)}
        />

        {/* Desktop sidebar toggle */}
        <button
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="hidden lg:flex absolute top-3 left-3 z-20 p-1.5 rounded-lg bg-gray-900/80 border border-gray-800/40 text-gray-400 hover:text-white hover:border-gray-700 transition-colors"
          style={{ left: sidebarOpen ? undefined : '0.75rem' }}
          title={sidebarOpen ? 'Close sidebar' : 'Open sidebar'}
        >
          {sidebarOpen ? <PanelLeftClose size={16} /> : <PanelLeftOpen size={16} />}
        </button>

        {/* Chat Area */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Mobile status bar */}
          <div className="sm:hidden px-3 py-2 border-b border-gray-800/40 overflow-x-auto">
            {machineState && <StatusBar state={machineState} />}
          </div>

          {/* Mobile brand selector */}
          <div className="md:hidden px-3 py-2 border-b border-gray-800/40">
            <BrandSelector brands={brands} selectedBrandId={selectedBrandId} onChange={setSelectedBrandId} />
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-4 sm:px-6 lg:px-8 py-4 space-y-4">
            {messages.length === 0 && !thinking && (
              <div className="flex flex-col items-center justify-center h-full text-center">
                <div className="w-16 h-16 rounded-full bg-gradient-to-br from-cyan-500/10 to-blue-500/10 border border-cyan-800/30 flex items-center justify-center mb-4">
                  <Brain size={28} className="text-cyan-400/60" />
                </div>
                <h2 className="text-lg font-bold text-gray-300 mb-1">Strategic GM</h2>
                <p className="text-sm text-gray-500 max-w-md">
                  Your conversational operating brain. Ask questions, get recommendations,
                  execute strategies, and monitor your content machine.
                </p>
              </div>
            )}

            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}

            {thinking && <TypingIndicator />}

            {/* Error message */}
            {error && (
              <div className="flex justify-center">
                <div className="flex items-center gap-2 bg-red-900/20 border border-red-800/40 rounded-lg px-4 py-2 text-xs text-red-400">
                  <AlertCircle size={14} />
                  {error}
                  <button onClick={() => setError(null)} className="text-red-500 hover:text-red-300 ml-2 font-bold">
                    Dismiss
                  </button>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Blueprint execution (if active) */}
          {blueprintStatus && (
            <div className="px-4 sm:px-6 lg:px-8 pb-2">
              <ExecutionPanel
                blueprintStatus={blueprintStatus}
                onApprove={handleApprove}
                onExecute={handleExecute}
                executing={executing}
              />
            </div>
          )}

          {/* Quick actions */}
          <div className="px-4 sm:px-6 lg:px-8 pb-2">
            <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-hide">
              {QUICK_ACTIONS.map((action) => (
                <button
                  key={action.label}
                  onClick={() => handleQuickAction(action.msg)}
                  disabled={thinking}
                  className="shrink-0 flex items-center gap-1.5 px-3 py-1.5 bg-gray-900/60 border border-gray-800/50 rounded-full text-xs text-gray-400 hover:text-white hover:border-cyan-800/50 hover:bg-gray-800/60 transition-all disabled:opacity-40"
                >
                  <action.icon size={12} />
                  {action.label}
                </button>
              ))}
            </div>
          </div>

          {/* Input Area */}
          <div className="shrink-0 border-t border-gray-800/60 bg-gray-950/95 backdrop-blur-sm px-4 sm:px-6 lg:px-8 py-3">
            <div className="flex gap-2 items-end max-w-4xl mx-auto">
              <div className="flex-1 relative">
                <textarea
                  ref={textareaRef}
                  value={input}
                  onChange={(e) => { setInput(e.target.value); adjustTextareaHeight(); }}
                  onKeyDown={handleKeyDown}
                  placeholder="Talk to the GM — ask questions, give direction, request analysis..."
                  rows={1}
                  className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 pr-12 text-sm text-white placeholder-gray-600 focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 outline-none resize-none leading-relaxed transition-colors"
                  disabled={thinking}
                  style={{ maxHeight: '160px' }}
                />
                <div className="absolute right-2 bottom-2 text-[9px] text-gray-700 font-mono">
                  {input.length > 0 && (
                    <span>shift+enter for newline</span>
                  )}
                </div>
              </div>
              <button
                onClick={handleSend}
                disabled={!input.trim() || thinking}
                className="shrink-0 p-3 bg-gradient-to-r from-cyan-600 to-blue-600 text-white rounded-xl hover:from-cyan-500 hover:to-blue-500 transition-all disabled:opacity-40 disabled:cursor-not-allowed shadow-lg shadow-cyan-900/20"
                title="Send message"
              >
                {thinking ? (
                  <Loader2 size={18} className="animate-spin" />
                ) : (
                  <Send size={18} />
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
