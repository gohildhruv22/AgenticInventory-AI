import { useState } from "react";
import { Outlet } from "react-router-dom";
import { motion } from "framer-motion";
import { Sidebar } from "./Sidebar";
import { Header } from "./Header";
import { useLocation } from "react-router-dom";

export function AppShell() {
  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();

  return (
    <div className="flex min-h-screen text-slate-900">
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((c) => !c)} />

      <motion.div
        className="flex flex-1 flex-col"
        initial={false}
        animate={{ marginLeft: collapsed ? 72 : 240 }}
        transition={{ duration: 0.25, ease: "easeInOut" }}
      >
        <Header />

        <main className="flex-1 overflow-y-auto p-6">
          {/*
            NOTE: We intentionally do NOT wrap <Outlet/> in <AnimatePresence mode="wait">.
            That combination is incompatible with React.lazy() pages — AnimatePresence
            waits for the exit animation to finish before mounting the new child, but the
            new child suspends on its lazy chunk, leaving the new <motion.div> stuck at
            its initial (opacity: 0) state → users see a blank page on client-side nav,
            while a hard refresh works because there is no exit animation to wait for.
            Keying a plain wrapper on `location.pathname` is enough to remount each page
            so its own `fadeInUp` section animations re-run cleanly.
          */}
          <div key={location.pathname}>
            <Outlet />
          </div>
        </main>
      </motion.div>
    </div>
  );
}
