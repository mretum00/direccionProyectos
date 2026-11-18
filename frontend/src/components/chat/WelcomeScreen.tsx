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
    text: '¿Qué significa el código de avería HTM-0101?',
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
        <div className="icono-marca w-16 h-16 rounded-2xl shadow-xl shadow-marca-500/20">
          <Sparkles className="w-8 h-8 text-sobre-marca" />
        </div>
      </div>

      <h2 className="text-2xl font-bold text-texto mb-2">¿En qué puedo ayudarte?</h2>
      <p className="text-sm text-texto-400 max-w-md mb-8">
        Consulta la documentación técnica de tu motor y obtén respuestas verificables.
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-2xl">
        {SUGGESTIONS.map(({ icon: Icon, text, hint }) => (
          <button
            key={text}
            onClick={() => onSuggestion(text)}
            className="tarjeta-interactiva group flex items-start gap-3 p-4 text-left"
          >
            <div className="w-9 h-9 rounded-lg bg-contraste/5 group-hover:bg-marca-500/10 flex items-center justify-center flex-shrink-0 transition-colors">
              <Icon className="w-4 h-4 text-texto-400 group-hover:text-marca-400 transition-colors" />
            </div>
            <div className="min-w-0">
              <p className="text-sm text-texto-300 group-hover:text-texto transition-colors">{text}</p>
              <p className="text-[11px] text-texto-600 mt-0.5">{hint}</p>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
