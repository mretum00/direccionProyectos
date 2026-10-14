import { Sparkles, Thermometer, AlertTriangle, Shield, Wrench } from 'lucide-react';

interface WelcomeScreenProps {
  onSuggestion: (text: string) => void;
}

const SUGGESTIONS = [
  {
    icon: Thermometer,
    text: 'El motor se calienta y se enciende un testigo, ¿qué compruebo?',
    hint: 'Sobrecalentamiento',
  },
  {
    icon: AlertTriangle,
    text: '¿Qué significa el código DTC P0217?',
    hint: 'Código de avería',
  },
  {
    icon: Shield,
    text: '¿Qué EPIs necesito para trabajar en el sistema de alta tensión?',
    hint: 'Seguridad',
  },
  {
    icon: Wrench,
    text: '¿Cuál es el intervalo de mantenimiento de mi versión?',
    hint: 'Mantenimiento',
  },
];

export function WelcomeScreen({ onSuggestion }: WelcomeScreenProps) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center py-12">
      <div className="relative mb-6">
        <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center shadow-xl shadow-cyan-500/20">
          <Sparkles className="w-8 h-8 text-white" />
        </div>
      </div>

      <h2 className="text-2xl font-bold text-white mb-2">¿En qué puedo ayudarte?</h2>
      <p className="text-sm text-gray-400 max-w-md mb-8">
        Consulta la documentación técnica de tu motor y obtén respuestas verificables.
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-2xl">
        {SUGGESTIONS.map(({ icon: Icon, text, hint }) => (
          <button
            key={text}
            onClick={() => onSuggestion(text)}
            className="group flex items-start gap-3 p-4 rounded-xl bg-[#151518] border border-white/5 hover:border-cyan-500/20 hover:bg-cyan-500/5 transition-all text-left"
          >
            <div className="w-9 h-9 rounded-lg bg-white/5 group-hover:bg-cyan-500/10 flex items-center justify-center flex-shrink-0 transition-colors">
              <Icon className="w-4 h-4 text-gray-400 group-hover:text-cyan-400 transition-colors" />
            </div>
            <div className="min-w-0">
              <p className="text-sm text-gray-300 group-hover:text-white transition-colors">{text}</p>
              <p className="text-[10px] text-gray-600 mt-0.5">{hint}</p>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
