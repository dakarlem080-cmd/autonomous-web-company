"use client";
import { useEffect } from "react";
import "./globals.css";
import "./company.css";
import "./command-ui.css";
import "./settings/settings.css";

export default function Layout({children}:{children:React.ReactNode}){
 useEffect(()=>{
  const routes:Record<string,string>={"نظرة عامة":"/","الموظفون":"/settings?tab=employees","الاتصالات":"/settings?tab=connections","نماذج الذكاء":"/settings?tab=models","أدوات Google":"/settings?tab=google","النشاط":"/#activity","الإعدادات":"/settings",Overview:"/",Workforce:"/settings?tab=employees",Connections:"/settings?tab=connections","AI Models":"/settings?tab=models",Google:"/settings?tab=google",Activity:"/#activity",Settings:"/settings"};
  const items=Array.from(document.querySelectorAll<HTMLElement>(".navItem"));
  items.forEach(item=>{const label=(item.querySelector("span")?.textContent||item.textContent||"").trim();const href=routes[label];if(!href)return;if(item.tagName==="A")item.setAttribute("href",href);else item.onclick=()=>{window.location.href=href}});
  return()=>items.forEach(item=>{item.onclick=null});
 },[]);
 return <html><head><title>Autonomous Web Company</title></head><body>{children}</body></html>
}
