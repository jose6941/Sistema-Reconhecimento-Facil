import { CLASSES_BADGE, infoStatus } from "@/lib/status";

interface StatusBadgeProps {
  status?: string | null;
  /** "aovivo" usa os rótulos da aba Ao vivo; "auditoria" os das tabelas. */
  variante?: "aovivo" | "auditoria";
  tamanho?: "sm" | "md";
}

export function StatusBadge({ status, variante = "auditoria", tamanho = "sm" }: StatusBadgeProps) {
  const info = infoStatus(status);
  const texto = variante === "aovivo" ? info.rotuloAoVivo : info.rotulo;
  const fonte = tamanho === "md" ? "text-[12px]" : "text-[11px]";

  return (
    <span
      className={`inline-block shrink-0 ${fonte} px-2 py-0.5 rounded-md font-medium border ${CLASSES_BADGE[info.tom]}`}
    >
      {texto}
    </span>
  );
}
