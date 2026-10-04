import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import {
  Bot,
  TrendingUp,
  Brain,
  BarChart3,
  Zap,
  Shield,
  ArrowRight,
  Sparkles,
} from "lucide-react";
import { fadeInUp, staggerChildren } from "@/lib/animations";

const features = [
  {
    icon: Bot,
    title: "Multi-Agent Orchestration",
    description: "Five AI agents work in a coordinated pipeline to monitor, forecast, decide, order, and track inventory automatically.",
    gradient: "from-cyan-500 to-blue-500",
  },
  {
    icon: TrendingUp,
    title: "AI Demand Forecasting",
    description: "Leverages Google Trends and historical data to predict demand patterns with high confidence scoring.",
    gradient: "from-purple-500 to-indigo-500",
  },
  {
    icon: Brain,
    title: "Autonomous Decision Engine",
    description: "AI-powered decision manager evaluates forecasts and autonomously approves or escalates reorder actions.",
    gradient: "from-pink-500 to-rose-500",
  },
  {
    icon: BarChart3,
    title: "Real-Time Analytics",
    description: "Live dashboards with animated charts showing inventory health, agent performance, and KPI metrics.",
    gradient: "from-amber-500 to-orange-500",
  },
  {
    icon: Shield,
    title: "Undo & Rollback",
    description: "Full audit trail with one-click undo/redo for any AI-generated action, ensuring complete control.",
    gradient: "from-emerald-500 to-teal-500",
  },
  {
    icon: Zap,
    title: "WebSocket Live Updates",
    description: "Real-time pipeline visualization with live agent reasoning, status updates, and activity feeds.",
    gradient: "from-violet-500 to-purple-500",
  },
];

export default function LandingPage() {
  return (
    <div className="relative min-h-screen overflow-hidden bg-[#FAFBFD]">
      {/* Background glow effects */}
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute left-1/4 top-0 h-[500px] w-[500px] rounded-full bg-purple-300/30 blur-[120px]" />
        <div className="absolute right-1/4 top-1/3 h-[400px] w-[400px] rounded-full bg-cyan-300/25 blur-[100px]" />
        <div className="absolute bottom-0 left-1/2 h-[300px] w-[600px] -translate-x-1/2 rounded-full bg-pink-300/25 blur-[100px]" />
      </div>

      {/* ─── Hero ─────────────────────────────────────────── */}
      <motion.section
        variants={staggerChildren}
        initial="initial"
        animate="animate"
        className="relative z-10 mx-auto flex max-w-5xl flex-col items-center px-6 pb-20 pt-24 text-center"
      >
        <motion.div
          variants={fadeInUp}
          className="mb-6 flex items-center gap-2 rounded-full border border-purple-200 bg-purple-50 px-4 py-1.5"
        >
          <Sparkles className="h-3.5 w-3.5 text-purple-600" />
          <span className="text-xs font-medium text-purple-700">
            Powered by Multi-Agent AI
          </span>
        </motion.div>

        <motion.h1
          variants={fadeInUp}
          className="text-5xl font-extrabold tracking-tight sm:text-6xl md:text-7xl"
        >
          <span className="text-slate-900">Inventory Management</span>
          <br />
          <span className="bg-gradient-to-r from-purple-600 via-pink-500 to-cyan-600 bg-clip-text text-transparent">
            Reimagined with AI
          </span>
        </motion.h1>

        <motion.p
          variants={fadeInUp}
          className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-slate-600"
        >
          An autonomous AI pipeline that monitors stock, forecasts demand, makes
          reorder decisions, and tracks deliveries — all in real time with full
          transparency and undo control.
        </motion.p>

        <motion.div variants={fadeInUp} className="mt-10 flex items-center gap-4">
          <Link
            to="/dashboard"
            className="group flex items-center gap-2 rounded-xl bg-gradient-to-r from-purple-500 to-pink-500 px-6 py-3 font-semibold text-white shadow-lg shadow-purple-500/25 transition-shadow hover:shadow-purple-500/40"
          >
            Open Dashboard
            <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
          </Link>
          <Link
            to="/agents"
            className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-6 py-3 font-semibold text-slate-700 transition-colors hover:bg-slate-50 hover:border-slate-300"
          >
            View Agent Pipeline
          </Link>
        </motion.div>
      </motion.section>

      {/* ─── Feature Grid ─────────────────────────────────── */}
      <motion.section
        variants={staggerChildren}
        initial="initial"
        whileInView="animate"
        viewport={{ once: true, margin: "-100px" }}
        className="relative z-10 mx-auto max-w-6xl px-6 pb-32"
      >
        <motion.h2
          variants={fadeInUp}
          className="mb-12 text-center text-3xl font-bold text-slate-900"
        >
          Everything you need for{" "}
          <span className="bg-gradient-to-r from-purple-600 to-cyan-600 bg-clip-text text-transparent">
            intelligent inventory
          </span>
        </motion.h2>

        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((feat) => {
            const Icon = feat.icon;
            return (
              <motion.div
                key={feat.title}
                variants={fadeInUp}
                whileHover={{ y: -4 }}
                className="group rounded-2xl border border-slate-200 bg-white p-6 shadow-sm transition-all hover:border-purple-200 hover:shadow-md"
              >
                <div
                  className={`mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br ${feat.gradient} shadow-lg`}
                >
                  <Icon className="h-5 w-5 text-white" />
                </div>
                <h3 className="mb-2 text-sm font-bold text-slate-900">{feat.title}</h3>
                <p className="text-xs leading-relaxed text-slate-600">{feat.description}</p>
              </motion.div>
            );
          })}
        </div>
      </motion.section>

      {/* ─── Footer ───────────────────────────────────────── */}
      <footer className="relative z-10 border-t border-slate-200 py-8 text-center text-xs text-slate-400">
        AgenticInventory AI — Built with FastAPI, React & AutoGen
      </footer>
    </div>
  );
}
