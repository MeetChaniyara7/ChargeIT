import React, { useState } from 'react';
import { Bot, Sparkles, X, ArrowRight, ShieldCheck } from 'lucide-react';

export const AgentFloatingButton: React.FC = () => {
  const [modalOpen, setModalOpen] = useState(false);

  return (
    <>
      {/* Floating Action Button — Bottom Right */}
      <div className="fixed bottom-6 right-6 z-40 group">
        <button
          type="button"
          onClick={() => setModalOpen(true)}
          className="relative flex items-center space-x-2.5 px-4 py-3 rounded-full bg-slate-900/90 hover:bg-slate-800 border border-slate-700/80 text-slate-200 shadow-2xl backdrop-blur-xl transition-all cursor-pointer group-hover:border-cyan-500/50 group-hover:shadow-cyan-500/10"
        >
          <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-cyan-500/20 to-amber-500/20 border border-cyan-500/30 flex items-center justify-center text-cyan-400">
            <Bot className="w-4 h-4" />
          </div>

          <div className="text-left pr-1">
            <div className="flex items-center gap-1.5">
              <span className="text-xs font-bold text-white tracking-tight">Reserve with Agent</span>
              <span className="px-1.5 py-0.2 text-[9px] font-bold rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30 uppercase tracking-wider">
                Soon
              </span>
            </div>
            <span className="text-[10px] text-slate-400 block -mt-0.5">AI Voice & Auto-Booking</span>
          </div>
        </button>

        {/* Hover Tooltip */}
        <div className="absolute right-0 bottom-full mb-3 hidden group-hover:flex items-center px-3 py-1.5 rounded-xl bg-slate-900/95 text-slate-300 text-xs border border-slate-800 shadow-xl whitespace-nowrap animate-fade-in pointer-events-none">
          <span>Autonomous AI Agent will find & lock optimal slots based on battery %</span>
        </div>
      </div>

      {/* Preview Modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md animate-fade-in">
          <div className="w-full max-w-md p-6 rounded-2xl glass-card relative border border-slate-800 shadow-2xl">
            <button
              onClick={() => setModalOpen(false)}
              className="absolute top-4 right-4 p-1 rounded-full hover:bg-slate-800 text-slate-400 hover:text-white transition-colors cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="w-12 h-12 rounded-2xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400 mb-4">
              <Bot className="w-6 h-6" />
            </div>

            <div className="flex items-center space-x-2 mb-2">
              <h3 className="text-lg font-bold text-white">Reserve with AI Agent</h3>
              <span className="px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-300 border border-amber-500/30 text-[10px] font-bold uppercase tracking-wider">
                Preview / Coming Soon
              </span>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed mb-4">
              Our autonomous AI Agent will continuously monitor live station traffic, compute optimal charging windows based on your vehicle's current state of charge, and negotiate instant reservations on your behalf.
            </p>

            <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800/80 space-y-2 mb-5 text-xs">
              <div className="flex items-center space-x-2 text-slate-300">
                <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
                <span>Zero-touch automatic station selection</span>
              </div>
              <div className="flex items-center space-x-2 text-slate-300">
                <Sparkles className="w-4 h-4 text-amber-400 shrink-0" />
                <span>Predictive queue wait-time minimization</span>
              </div>
            </div>

            <button
              onClick={() => setModalOpen(false)}
              className="w-full py-2.5 px-4 rounded-xl gradient-btn text-white text-xs font-semibold flex items-center justify-center space-x-2 cursor-pointer"
            >
              <span>Got It</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </>
  );
};
