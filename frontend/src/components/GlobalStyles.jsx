export default function GlobalStyles() {
  return (
    <style>{`
      @keyframes fadeIn { from { opacity: 0; transform: translateY(-10px); } to { opacity: 1; transform: translateY(0); } }
      @keyframes pulseRed { 0%, 100% { box-shadow: 0 0 15px rgba(239,68,68,0.2); border-color: rgba(239,68,68,0.4); } 50% { box-shadow: 0 0 25px rgba(239,68,68,0.7); border-color: rgba(239,68,68,0.9); } }
      @keyframes slideInRight { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
      .animate-fadeIn { animation: fadeIn 0.3s ease-in-out forwards; }
      .animate-pulseRed { animation: pulseRed 2s infinite; }
      .animate-slideInRight { animation: slideInRight 0.5s cubic-bezier(0.23, 1, 0.32, 1) forwards; }
    `}</style>
  );
}