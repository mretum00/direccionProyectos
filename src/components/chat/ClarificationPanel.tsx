import { useState } from 'react';
import { HelpCircle, Send } from 'lucide-react';
import type { Clarification as ClarificationType } from '@/types/chat';

interface ClarificationPanelProps {
  clarification: ClarificationType;
  onSubmit: (answers: Record<string, string>) => void;
}

export function ClarificationPanel({ clarification, onSubmit }: ClarificationPanelProps) {
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [text, setText] = useState('');

  function handleSubmit() {
    const parts: string[] = [];
    for (const field of clarification.missing_fields) {
      const val = answers[field.key];
      if (val) parts.push(`${field.label}: ${val}`);
    }
    if (text.trim()) parts.push(text.trim());
    if (parts.length > 0) onSubmit(Object.fromEntries(parts.map((p, i) => [`answer_${i}`, p])));
  }

  return (
    <div className="rounded-xl border border-cyan-500/30 bg-cyan-500/5 p-4">
      <div className="flex items-center gap-2 mb-3">
        <HelpCircle className="w-4 h-4 text-cyan-400" />
        <h4 className="text-sm font-semibold text-cyan-400">Información necesaria</h4>
      </div>

      {clarification.message && (
        <p className="text-sm text-gray-300 mb-3">{clarification.message}</p>
      )}

      <div className="space-y-3">
        {clarification.missing_fields.map((field) => (
          <div key={field.key}>
            <label className="block text-xs text-gray-400 mb-1.5">{field.label}</label>
            {field.options ? (
              <div className="flex gap-2">
                {field.options.map((opt) => (
                  <button
                    key={opt}
                    onClick={() => setAnswers((prev) => ({ ...prev, [field.key]: opt }))}
                    className={`px-3 py-1.5 rounded-md text-xs font-medium border transition-colors ${
                      answers[field.key] === opt
                        ? 'bg-cyan-500/15 text-cyan-400 border-cyan-500/30'
                        : 'bg-white/5 text-gray-300 border-white/10 hover:bg-white/10'
                    }`}
                  >
                    {opt}
                  </button>
                ))}
              </div>
            ) : (
              <input
                value={answers[field.key] ?? ''}
                onChange={(e) => setAnswers((prev) => ({ ...prev, [field.key]: e.target.value }))}
                placeholder={`Introduce ${field.label.toLowerCase()}`}
                className="w-full bg-[#0a0a0b] border border-white/10 rounded-md px-3 py-2 text-sm text-white outline-none focus:border-cyan-500/50"
              />
            )}
          </div>
        ))}
      </div>

      <div className="flex items-end gap-2 mt-4">
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Añadir más detalle (opcional)..."
          className="flex-1 bg-[#0a0a0b] border border-white/10 rounded-md px-3 py-2 text-sm text-white outline-none focus:border-cyan-500/50"
        />
        <button
          onClick={handleSubmit}
          className="flex items-center gap-1.5 px-3 py-2 rounded-md bg-cyan-500/15 text-cyan-400 text-sm font-medium hover:bg-cyan-500/25 transition-colors"
        >
          <Send className="w-3.5 h-3.5" />
          Enviar
        </button>
      </div>
    </div>
  );
}
