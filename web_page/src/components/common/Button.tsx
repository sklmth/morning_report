import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { cn } from '@/lib/cn';

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  children: ReactNode;
  variant?: 'primary' | 'secondary' | 'ghost' | 'icon';
};

export function Button({ children, className, variant = 'secondary', ...props }: ButtonProps) {
  return <button className={cn('button', `button-${variant}`, className)} {...props}>{children}</button>;
}
