"use client";
import {useEffect} from "react";
const API=process.env.NEXT_PUBLIC_API_URL||"https://autonomous-web-company-production.up.railway.app";
export default function AuthBootstrap(){
 useEffect(()=>{
  const original=window.fetch.bind(window);
  window.fetch=async (input:RequestInfo|URL,init:RequestInit={})=>{
   const url=typeof input==="string"?input:input instanceof URL?input.toString():input.url;
   if(url.startsWith(API)) init={...init,credentials:"include"};
   const response=await original(input,init);
   if(response.status===401 && !location.pathname.startsWith("/login")) location.href="/login";
   return response;
  };
  return()=>{window.fetch=original};
 },[]);
 return null;
}
