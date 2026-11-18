import { FileText, BookOpen, GitBranch, History, Shield, BookMarked, type LucideIcon } from 'lucide-react';
import type { SourceType } from '@/types/chat';

/** Etiqueta, icono y color de cada tipo de documento (fuentes citadas y lista de documentación). */
export const SOURCE_TYPES: Record<SourceType, { label: string; icon: LucideIcon; color: string }> = {
  manual: { label: 'Manual técnico', icon: FileText, color: 'text-marca-400 bg-marca-500/10' },
  dtc_catalog: { label: 'Catálogo DTC', icon: BookOpen, color: 'text-violet-400 bg-violet-500/10' },
  decision_tree: { label: 'Árbol de decisión', icon: GitBranch, color: 'text-teal-400 bg-teal-500/10' },
  historical_case: { label: 'Caso histórico', icon: History, color: 'text-purple-400 bg-purple-500/10' },
  safety_manual: { label: 'Manual de seguridad', icon: Shield, color: 'text-orange-400 bg-orange-500/10' },
  glossary: { label: 'Glosario', icon: BookMarked, color: 'text-texto-400 bg-texto-500/10' },
};
