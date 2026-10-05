import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Sistema de Reconhecimento Facial | ESP32-CAM (TCC IFSP)",
  description: "Painel de controle e monitoramento de reconhecimento facial em tempo real para controle de acesso",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR">
      <body className="antialiased min-h-screen">
        {children}
      </body>
    </html>
  );
}
