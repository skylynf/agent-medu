import { useEffect, useRef, useState } from "react";

export interface ChatMessage {
  role: "student" | "patient" | "tutor" | "system";
  content: string;
  emotion?: string;
  hint_level?: string;
  timestamp: number;
}

interface Props {
  messages: ChatMessage[];
  onSend: (content: string) => void;
  disabled: boolean;
  patientName: string;
  isTyping: boolean;
}

function TypingBubble({ patientName }: { patientName: string }) {
  return (
    <div className="flex justify-start">
      <div className="max-w-[75%] bg-white border border-slate-200 text-slate-800 rounded-2xl rounded-bl-md px-4 py-3 shadow-sm">
        <div className="text-xs font-medium text-slate-400 mb-1">
          {patientName}
        </div>
        <div className="flex items-center gap-1.5 py-1">
          <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce [animation-delay:0ms]" />
          <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce [animation-delay:150ms]" />
          <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce [animation-delay:300ms]" />
        </div>
      </div>
    </div>
  );
}

export default function ChatPanel({ messages, onSend, disabled, patientName, isTyping }: Props) {
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || disabled) return;
    onSend(text);
    setInput("");
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg, i) => {
          if (msg.role === "tutor") return null;

          const isStudent = msg.role === "student";
          return (
            <div
              key={i}
              className={`flex ${isStudent ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[75%] ${
                  isStudent
                    ? "bg-medical text-white rounded-2xl rounded-br-md"
                    : "bg-white border border-slate-200 text-slate-800 rounded-2xl rounded-bl-md"
                } px-4 py-3 shadow-sm`}
              >
                {!isStudent && (
                  <div className="text-xs font-medium text-slate-400 mb-1">
                    {patientName}
                    {msg.emotion && msg.emotion !== "baseline" && (
                      <span className="ml-2 text-amber-500">
                        ({msg.emotion === "empathetic" ? "放松" : msg.emotion === "cold" ? "紧张" : msg.emotion === "rushing" ? "焦虑" : ""})
                      </span>
                    )}
                  </div>
                )}
                <div className="text-sm leading-relaxed whitespace-pre-wrap">
                  {msg.content}
                </div>
              </div>
            </div>
          );
        })}
        {isTyping && <TypingBubble patientName={patientName} />}
        <div ref={bottomRef} />
      </div>

      <form
        onSubmit={handleSubmit}
        className="border-t border-slate-200 p-4 bg-white"
      >
        <div className="flex gap-3">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={disabled ? "会话已结束" : "输入你的问诊内容..."}
            disabled={disabled || isTyping}
            className="flex-1 px-4 py-2.5 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-medical/30 focus:border-medical transition-all disabled:bg-slate-100"
            autoFocus
          />
          <button
            type="submit"
            disabled={disabled || !input.trim() || isTyping}
            className="px-6 py-2.5 bg-medical text-white rounded-xl font-medium hover:bg-medical-dark transition-colors disabled:opacity-50"
          >
            发送
          </button>
        </div>
      </form>
    </div>
  );
}
