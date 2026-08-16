"use client";
import {useEffect,useState} from "react";
const API=process.env.NEXT_PUBLIC_API_URL||"http://localhost:8000";
type P={id:number,name:string,domain:string,dry_run:boolean,active:boolean};
export default function Page(){
 const [p,setP]=useState<P[]>([]),[n,setN]=useState(""),[d,setD]=useState(""),[runs,setRuns]=useState<any[]>([]),[error,setError]=useState("");
 async function load(){try{setP(await(await fetch(`${API}/api/projects`)).json())}catch(e){setError("Brain API unavailable")}}
 useEffect(()=>{load()},[]);
 async function create(){await fetch(`${API}/api/projects`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({name:n,domain:d,dry_run:true})});setN("");setD("");load()}
 async function run(x:P){try{await fetch(`${API}/api/projects/${x.id}/run`,{method:"POST"});setRuns(await(await fetch(`${API}/api/projects/${x.id}/runs`)).json())}catch(e){setError("Brain API unavailable")}}
 return <main><small>AUTONOMOUS WEB COMPANY</small><h1>Control Center</h1><p>Dashboard only. The autonomous brain runs separately.</p>{error&&<div className="panel">{error}</div>}<section className="create"><input value={n} onChange={e=>setN(e.target.value)} placeholder="Project"/><input value={d} onChange={e=>setD(e.target.value)} placeholder="Domain"/><button onClick={create}>Create</button></section><section className="grid">{p.map(x=><article key={x.id}><small>{x.dry_run?"DRY RUN":"AUTONOMOUS"}</small><h2>{x.name}</h2><p>{x.domain}</p><button onClick={()=>run(x)}>Run brain</button></article>)}</section><section className="panel"><h2>Recent runs</h2>{runs.map(r=><div className="row" key={r.id}>#{r.id} — {r.status} {r.error}</div>)}</section></main>
}