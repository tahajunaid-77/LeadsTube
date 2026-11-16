import "./globals.css";

export const metadata = {
  title: "LeadTube",
  description: "Find YouTube leads in your niche, write your email, send to Smartlead.",
  icons: { icon: "/favicon.svg", apple: "/favicon.svg" },
};
export const viewport = { themeColor: "#2457d6" };

// Apply the saved light/dark theme before the page paints (no flash).
const themeScript = `try{var t=localStorage.getItem("leads.theme");if(t){t=JSON.parse(t);if(t)document.documentElement.dataset.theme=t}}catch(e){}`;

export default function RootLayout({ children }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        {/* eslint-disable-next-line @next/next/no-page-custom-font */}
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet" />
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
