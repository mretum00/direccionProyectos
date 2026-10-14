interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
  maxWidth?: string;
}

export function Modal({ open, onClose, title, children, maxWidth = 'max-w-lg' }: ModalProps) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      <div
        className={`relative w-full ${maxWidth} bg-[#151518] border border-white/10 rounded-xl shadow-2xl max-h-[85vh] flex flex-col`}
      >
        {title && (
          <div className="flex items-center justify-between px-5 py-3.5 border-b border-white/5 flex-shrink-0">
            <h3 className="text-sm font-semibold text-white">{title}</h3>
            <button
              onClick={onClose}
              className="text-gray-500 hover:text-white text-lg leading-none"
            >
              ×
            </button>
          </div>
        )}
        <div className="overflow-y-auto px-5 py-4">{children}</div>
      </div>
    </div>
  );
}
