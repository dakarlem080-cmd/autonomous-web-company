import "./globals.css";
import "./settings/settings.css";

export const metadata={title:"Autonomous Web Company"};
export default function Layout({children}:{children:React.ReactNode}){return <html><body>{children}</body></html>}
