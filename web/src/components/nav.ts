import {
  ChartCandlestick,
  FlaskConical,
  LayoutDashboard,
  NotebookPen,
  Radar,
  Settings,
  type LucideIcon,
} from "lucide-react";

export type NavItem = {
  title: string;
  href: string;
  icon: LucideIcon;
  description: string;
};

export const mainNav: NavItem[] = [
  { title: "Painel", href: "/", icon: LayoutDashboard, description: "Como estou e o que tem hoje" },
  { title: "Scanner", href: "/scanner", icon: Radar, description: "Onde tem setup agora" },
  {
    title: "Laboratório",
    href: "/laboratorio",
    icon: FlaskConical,
    description: "Quais setups têm vantagem comprovada",
  },
  { title: "Ativos", href: "/ativos", icon: ChartCandlestick, description: "Gráficos e indicadores" },
  { title: "Diário", href: "/diario", icon: NotebookPen, description: "O que eu operei e por quê" },
];

export const secondaryNav: NavItem[] = [
  { title: "Ajustes", href: "/ajustes", icon: Settings, description: "Capital, risco e preferências" },
];
