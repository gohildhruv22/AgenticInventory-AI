import type { Variants, Transition } from "framer-motion";

export const fadeInUp: Variants = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -10 },
};

export const scaleIn: Variants = {
  initial: { scale: 0.95, opacity: 0 },
  animate: { scale: 1, opacity: 1 },
  exit: { scale: 0.95, opacity: 0 },
};

export const slideInLeft: Variants = {
  initial: { x: -20, opacity: 0 },
  animate: { x: 0, opacity: 1 },
  exit: { x: -20, opacity: 0 },
};

export const slideInRight: Variants = {
  initial: { x: 20, opacity: 0 },
  animate: { x: 0, opacity: 1 },
  exit: { x: 20, opacity: 0 },
};

export const staggerChildren: Variants = {
  animate: {
    transition: { staggerChildren: 0.06 },
  },
};

export const pulseGlow: Variants = {
  animate: {
    boxShadow: [
      "0 0 20px rgba(139,92,246,0.2)",
      "0 0 40px rgba(139,92,246,0.4)",
      "0 0 20px rgba(139,92,246,0.2)",
    ],
  },
};

export const pulseGlowTransition: Transition = {
  repeat: Infinity,
  duration: 2,
  ease: "easeInOut",
};

export const defaultTransition: Transition = {
  duration: 0.3,
  ease: [0.25, 0.1, 0.25, 1],
};

export const springTransition: Transition = {
  type: "spring",
  stiffness: 300,
  damping: 24,
};

export const pageTransition: Variants = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.35, ease: "easeOut" } },
  exit: { opacity: 0, y: -8, transition: { duration: 0.2 } },
};

/* ─── Micro-interaction presets (T128) ─────────────────────── */
export const hoverLift = {
  whileHover: { y: -2, scale: 1.01 },
  whileTap: { scale: 0.98 },
  transition: { type: "spring" as const, stiffness: 400, damping: 20 },
};

export const buttonPress = {
  whileHover: { scale: 1.03 },
  whileTap: { scale: 0.97 },
};

export const cardHover = {
  whileHover: { y: -4, boxShadow: "0 12px 40px rgba(0,0,0,0.3)" },
  transition: { type: "spring" as const, stiffness: 300, damping: 20 },
};

export const shimmer: Variants = {
  animate: {
    backgroundPosition: ["200% 0%", "-200% 0%"],
    transition: { repeat: Infinity, duration: 2, ease: "linear" },
  },
};
