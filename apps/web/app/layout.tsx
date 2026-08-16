import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const sidebarPreferenceScript = `(function(){try{var collapsedWidth=74;var minExpandedWidth=200;var maxWidth=288;var snapWidth=150;var width=window.matchMedia("(max-width: 820px)").matches?collapsedWidth:220;var saved=window.localStorage.getItem("sensemu-sidebar-width");var legacy=window.localStorage.getItem("sensemu-sidebar-collapsed");if(saved!==null&&Number.isFinite(Number(saved))){var value=Number(saved);width=value<snapWidth?collapsedWidth:Math.min(maxWidth,Math.max(minExpandedWidth,value));}else if(legacy!==null){width=legacy==="true"?collapsedWidth:220;}var root=document.documentElement;root.style.setProperty("--persisted-sidebar-width",width+"px");root.dataset.sidebarCollapsed=width<minExpandedWidth?"true":"false";}catch(error){}})();`;

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "SenseMu · 视觉 AI 工作平台",
  description: "从数据、训练、评测到发布与交易的视觉 AI 工作平台。",
  icons: {
    icon: "/sensemu-logo-mark.svg",
    shortcut: "/sensemu-logo-mark.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: sidebarPreferenceScript }} />
      </head>
      <body className={`${geistSans.variable} ${geistMono.variable}`}>
        {children}
      </body>
    </html>
  );
}
