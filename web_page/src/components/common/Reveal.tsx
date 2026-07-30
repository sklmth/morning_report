import type { CSSProperties, ReactNode } from 'react';
import { motion } from 'framer-motion';
import { reveal } from '@/lib/motion';
import { useReducedMotion } from '@/hooks/useReducedMotion';

type RevealProps = { children: ReactNode; className?: string; style?: CSSProperties };

export function Reveal({ children, className, style }: RevealProps) {
  const reducedMotion = useReducedMotion();
  return (
    <motion.div
      className={className}
      style={style}
      initial={reducedMotion ? false : 'hidden'}
      whileInView="visible"
      viewport={{ once: true, amount: 0.18 }}
      variants={reducedMotion ? undefined : reveal}
    >
      {children}
    </motion.div>
  );
}
