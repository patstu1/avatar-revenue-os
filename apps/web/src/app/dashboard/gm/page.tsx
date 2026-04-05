'use client';

import { useEffect, useRef, useState } from 'react';
import { gmApi } from '@/lib/gm-api';
import {
  Brain,
  Send,
  Loader2,
  CheckCircle2,
  Play,
  RefreshCw,
  Zap,
  Target,
  Users,
  DollarSign,
  TrendingUp,
  Shield,
  Cpu,
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

/* ------------------------------------------------------------------ */
/*  Phase Badge                                                       */
/* ------------------------------------------------------------------ */

/* ------------------------------------------------------------------ */
/*  Machine State Bar — factual counts only, no gates                 */
/* ------------------------------------------------------------------ */

function MachineStateBar({ state }: { state: MachineState }) {
  return (
    <div className="bg-gray-900/80 border border-gray-800/60 rounded-xl px-5 py-3 flex items-center gap-6 text-xs">
      <div className="flex items-center gap-1 text-gray-400">
        <Cpu size={12} /> <span>{state.providers.configured} providers</span>
      </div>
      <div className="flex items-center gap-1 text-gray-400">
        <Target size={12} /> <span>{state.brands.count} brands</span>
      </div>
      <div className="flex items-center gap-1 text-gray-400">
        <Users size={12} /> <span>{state.accounts.count} accounts</span>
      </div>
      <div className="flex items-center gap-1 text-gray-400">
        <DollarSign size={12} /> <span>${state.revenue.total_90d.toFixed(0)}</span>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Execution Panel                                                   */
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
    <div className="bg-gray-900/80 border border-cyan-800/30 rounded-xl p-4 space-y-3">
      <div className="flex items-center gap-2 text-sm font-bold text-cyan-400">
        <Zap size={16} />
        Blueprint Execution
      </div>

      {blueprintStatus === 'proposed' && (
        <button
          onClick={onApprove}
          className="w-full py-2.5 bg-gradient-to-r from-green-600 to-emerald-600 text-white font-bold rounded-lg hover:from-green-500 hover:to-emerald-500 transition-all text-sm flex items-center justify-center gap-2"
        >
          <CheckCircle2 size={16} />
          Approve Blueprint
        </button>
      )}

      {(blueprintStatus === 'approved' || blueprintStatus === 'executing') && (
        <div className="space-y-2">
          {steps.map((step) => (
            <button
              key={step.key}
              onClick={() => onExecute(step.key)}
              disabled={executing === step.key}
              className="w-full py-2 px-3 bg-gray-800 border border-gray-700 rounded-lg text-sm text-gray-300 hover:border-cyan-700 hover:text-white transition-all flex items-center gap-2 disabled:opacity-50"
            >
              {executing === step.key ? (
                <Loader2 size={14} className="animate-spin text-cyan-400" />
              ) : (
                <step.icon size={14} className="text-gray-500" />
              )}
              {step.label}
              <Play size={12} className="ml-auto text-gray-600" />
            </button>
          ))}
        </div>
      )}

      {blueprintStatus === 'completed' && (
        <div className="text-sm text-green-400 flex items-center gap-2">
          <CheckCircle2 size={16} />
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
    <div className={`flex ${isGM ? 'justify-start' : 'justify-end'} mb-4`}>
      <div className={`max-w-[85%] ${isGM ? 'order-2' : 'order-1'}`}>
        {isGM && (
          <div className="flex items-center gap-2 mb-1">
            <div className="w-6 h-6 rounded-full bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center">
              <Brain size={14} className="text-white" />
            </div>
            <span className="text-[10px] font-mono text-cyan-400 uppercase">Strategic GM</span>
            {message.message_type === 'blueprint_presentation' && (
              <span className="text-[10px] font-mono text-amber-400 bg-amber-900/20 px-1.5 py-0.5 rounded">BLUEPRINT</span>
            )}
            {message.message_type === 'blueprint_revision' && (
              <span className="text-[10px] font-mono text-purple-400 bg-purple-900/20 px-1.5 py-0.5 rounded">REVISION</span>
            )}
          </div>
        )}
        <div
          className={`rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap ${
            isGM
              ? 'bg-gray-900/80 border border-gray-800/60 text-gray-200'
              : 'bg-cyan-900/30 border border-cyan-800/40 text-white'
          }`}
          dangerouslySetInnerHTML={{
            __html: renderContent(message.content),
          }}
        />
      </div>
    </div>
  );
}

function renderContent(text: string): string {
  if (!text) return '';
  let html = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong class="text-white">$1</strong>')
    .replace(/^## (.+)$/gm, '<h2 class="text-lg font-bold text-cyan-400 mt-4 mb-2">$1</h2>')
    .replace(/^### (.+)$/gm, '<h3 class="text-base font-bold text-blue-400 mt-3 mb-1">$1</h3>')
    .replace(/^- (.+)$/gm, '<div class="flex gap-2 ml-2"><span class="text-cyan-600">-</span><span>$1</span></div>')
    .replace(/\n\n/g, '<br/><br/>');
  return html;
}

/* ------------------------------------------------------------------ */
/*  Main GM Page                                                      */
/* ------------------------------------------------------------------ */

export default function GMPage() {
  const [machineState, setMachineState] = useState<MachineState | null>(null);
  const [messages, setMessages] = useState<GMMessage[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(true);
  const [thinking, setThinking] = useState(false);
  const [blueprintStatus, setBlueprintStatus] = useState<string | null>(null);
  const [executing, setExecuting] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Initialize: scan state + check for existing session
  useEffect(() => {
    let cancelled = false;

    async function init() {
      try {
        // Get machine state
        const stateRes = await gmApi.getMachineState();
        if (cancelled) return;
        setMachineState(stateRes.data);

        // Check for existing sessions
        const sessionsRes = await gmApi.listSessions();
        if (cancelled) return;
        const sessions = sessionsRes.data as any[];

        if (sessions.length > 0) {
          // Resume most recent session
          const sid = sessions[0].id;
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
          // First visit — create session + auto-generate blueprint
          setThinking(true);
          const createRes = await gmApi.createSession();
          if (cancelled) return;
          const data = createRes.data;
          setSessionId(data.session.id);
          setMessages([data.initial_message as GMMessage]);
          if (data.initial_message.blueprint_data) {
            setBlueprintStatus('proposed');
          }
          setThinking(false);
        }
      } catch (err) {
        console.error('GM init failed:', err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    init();
    return () => { cancelled = true; };
  }, []);

  // Send message
  const handleSend = async () => {
    if (!input.trim() || !sessionId || thinking) return;
    const userText = input.trim();
    setInput('');
    setThinking(true);

    // Optimistic user message
    const tempUserMsg: GMMessage = {
      id: `temp-${Date.now()}`,
      role: 'user',
      content: userText,
      message_type: 'conversation',
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

      // Refresh machine state
      const stateRes = await gmApi.getMachineState();
      setMachineState(stateRes.data);
    } catch (err) {
      console.error('Send failed:', err);
    } finally {
      setThinking(false);
    }
  };

  // Approve blueprint
  const handleApprove = async () => {
    try {
      await gmApi.approveBlueprint();
      setBlueprintStatus('approved');
    } catch (err) {
      console.error('Approve failed:', err);
    }
  };

  // Execute step
  const handleExecute = async (stepKey: string) => {
    setExecuting(stepKey);
    try {
      const res = await gmApi.executeStep(stepKey);
      const result = res.data;

      // Add execution report to chat
      const execMsg: GMMessage = {
        id: `exec-${Date.now()}`,
        role: 'gm',
        content: result.success
          ? `**Executed: ${stepKey.replace(/_/g, ' ')}**\n\n${(result.results || []).map((r: string) => `- ${r}`).join('\n')}\n\n${result.created || 0} entities created.`
          : `**Execution failed:** ${result.error}`,
        message_type: 'execution_report',
      };
      setMessages((prev) => [...prev, execMsg]);

      // Refresh machine state
      const stateRes = await gmApi.getMachineState();
      setMachineState(stateRes.data);

      // Check blueprint status
      try {
        const bpRes = await gmApi.getBlueprint();
        setBlueprintStatus(bpRes.data?.status || 'executing');
      } catch { /* ignore */ }
    } catch (err) {
      console.error('Execute failed:', err);
    } finally {
      setExecuting(null);
    }
  };

  // Loading state
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[70vh]">
        <div className="flex flex-col items-center gap-4">
          <div className="w-16 h-16 rounded-full bg-gradient-to-br from-cyan-500/20 to-blue-500/20 border border-cyan-800/40 flex items-center justify-center">
            <Brain size={28} className="text-cyan-400 animate-pulse" />
          </div>
          <p className="text-sm text-gray-400 font-mono">GM scanning machine state...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-120px)]">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center">
            <Brain size={22} className="text-white" />
          </div>
          <div>
            <h1 className="text-xl font-black text-white">Strategic GM</h1>
            <p className="text-[10px] text-gray-500 font-mono uppercase">Maximum-ceiling revenue operating brain</p>
          </div>
        </div>
        {machineState && <MachineStateBar state={machineState} />}
      </div>

      {/* Main content area */}
      <div className="flex gap-4 flex-1 min-h-0">
        {/* Chat area */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Messages */}
          <div className="flex-1 overflow-y-auto pr-2 space-y-1">
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}
            {thinking && (
              <div className="flex items-center gap-2 text-cyan-400 text-sm py-2">
                <Loader2 size={16} className="animate-spin" />
                <span className="font-mono text-xs">GM analyzing...</span>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="mt-3 flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
              placeholder="Talk to the GM — adjust the plan, ask questions, give direction..."
              className="flex-1 bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-sm text-white placeholder-gray-600 focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 outline-none"
              disabled={thinking}
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || thinking}
              className="px-4 py-3 bg-gradient-to-r from-cyan-600 to-blue-600 text-white rounded-xl hover:from-cyan-500 hover:to-blue-500 transition-all disabled:opacity-40"
            >
              <Send size={18} />
            </button>
          </div>
        </div>

        {/* Execution sidebar */}
        <div className="w-64 shrink-0 space-y-3">
          <ExecutionPanel
            blueprintStatus={blueprintStatus}
            onApprove={handleApprove}
            onExecute={handleExecute}
            executing={executing}
          />

          {/* Quick actions */}
          <div className="bg-gray-900/80 border border-gray-800/60 rounded-xl p-4 space-y-2">
            <p className="text-[10px] font-mono text-gray-500 uppercase">Quick Prompts</p>
            {[
              { label: 'What\'s next?', msg: 'What is the single highest-leverage thing I should do right now?' },
              { label: 'Revise niches', msg: 'I want to revise the niche selections. Show me alternatives.' },
              { label: 'Add accounts', msg: 'I want to add more accounts. What do you recommend?' },
              { label: 'Show numbers', msg: 'Show me the expected revenue trajectory for this blueprint.' },
              { label: 'Scale triggers', msg: 'What signals should trigger the next scaling phase?' },
            ].map((q) => (
              <button
                key={q.label}
                onClick={() => { setInput(q.msg); }}
                className="w-full text-left px-3 py-1.5 text-xs text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg transition-colors"
              >
                {q.label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
