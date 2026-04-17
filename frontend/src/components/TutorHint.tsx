import { useEffect, useState } from "react";

interface Props {
  content: string;
  hintLevel: string;
  onDismiss: () => void;
}

const levelStyles: Record<string, string> = {
  gentle: "bg-blue-50 border-blue-200 text-blue-800",
  moderate: "bg-amber-50 border-amber-200 text-amber-800",
  strong: "bg-red-50 border-red-200 text-red-800",
};

const levelLabels: Record<string, string> = {
  gentle: "温和提示",
  moderate: "引导提示",
  strong: "重要提醒",
};

export default function TutorHint({ content, hintLevel, onDismiss }: Props) {
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    setVisible(true);
    const timer = setTimeout(() => {
      setVisible(false);
      onDismiss();
    }, 15000);
    return () => clearTimeout(timer);
  }, [content, onDismiss]);

  if (!visible) return null;

  return (
    <div
      className={`mx-4 mb-3 p-4 rounded-xl border-2 ${
        levelStyles[hintLevel] || levelStyles.moderate
      } animate-[slideUp_0.3s_ease-out]`}
    >
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <span className="text-lg">&#x1F393;</span>
          <span className="text-xs font-semibold uppercase tracking-wide">
            {levelLabels[hintLevel] || "导师提示"}
          </span>
        </div>
        <button
          onClick={() => {
            setVisible(false);
            onDismiss();
          }}
          className="text-sm opacity-50 hover:opacity-100"
        >
          关闭
        </button>
      </div>
      <p className="text-sm leading-relaxed">{content}</p>
    </div>
  );
}
