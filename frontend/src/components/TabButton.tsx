import type { ReactNode } from "react";

interface TabButtonProps {
  ativa: boolean;
  onClick: () => void;
  children: ReactNode;
}

export function TabButton({ ativa, onClick, children }: TabButtonProps) {
  return (
    <button
      role="tab"
      aria-selected={ativa}
      onClick={onClick}
      className={`flex-1 py-2 px-3 text-xs md:text-[13px] font-medium rounded-lg border transition-all cursor-pointer ${
        ativa
          ? "bg-white dark:bg-neutral-900 text-neutral-900 dark:text-neutral-100 border-neutral-300 dark:border-neutral-700 shadow-2xs"
          : "bg-neutral-100 dark:bg-neutral-800/60 text-neutral-600 dark:text-neutral-400 border-transparent hover:bg-neutral-200/60 dark:hover:bg-neutral-800"
      }`}
    >
      {children}
    </button>
  );
}
