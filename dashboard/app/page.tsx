"use client";

import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "https://autonomous-web-company-production.up.railway.app";

type Project = { id: number; name: string; domain: string; dry_run: boolean; active: boolean };
type Analytics = {
  project: Project;
  period_days: number;
  gsc: { configured: boolean; clicks: number; impressions: number; ctr: number; opportunities: any[] };
  ga4: { configured: boolean; users: number; sessions: number; engagement_rate: number };
};

async function json<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) throw new Error(`${response.status} ${await response.text()}`);
  return response.json();
}

export default function Page() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [runs, setRuns] = useState<any[]>([]);
  const [status, setStatus] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    name: "Plastic Surgeon Istanbul",
    domain: "plasticsurgeonistanbul.com",
    repo: "",
    branch: "main",
    goal: "organic_traffic",
    language: "en",
  });

  async function load(id?: number) {
    try {
      setError("");
      const [projectList, brainStatus] = await Promise.all([
        json<Project[]>(`${API}/api/projects`),
        json<any>(`${API}/api/status`),
      ]);
      setProjects(projectList);
      setStatus(brainStatus);
      const target = id ?? selected ?? projectList[0]?.id;
      if (!target) {
        setSelected(null);
        setAnalytics(null);
        setRuns([]);
        return;
      }
      setSelected(target);
      const [projectAnalytics, projectRuns] = await Promise.all([
        json<Analytics>(`${API}/api/projects/${target}/analytics`),
        json<any[]>(`${API}/api/projects/${target}/runs`),
      ]);
      setAnalytics(projectAnalytics);
      setRuns(projectRuns);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Brain API unavailable");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function createProject(event: React.FormEvent) {
    event.preventDefault();
    setCreating(true);
    try {
      const project = await json<Project>(`${API}/api/projects`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...form, dry_run: true }),
      });
      await load(project.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Project creation failed");
    } finally {
      setCreating(false);
    }
  }

  async function runBrain() {
    if (!selected) return;
    setRunning(true);
    try {
      await json(`${API}/api/projects/${selected}/run`, { method: "POST" });
      await load(selected);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Run failed");
    } finally {
      setRunning(false);
    }
  }

  const online = status?.status === "online";
  const autonomous = !status?.dry_run;
  const project = projects.find((item) => item.id === selected);

  return (
    <main className="shell">
      <header className="top">
        <div className="brand">
          <div className="brandMark">A</div>
          <div>
            <div className="eyebrow">AUTONOMOUS WEB COMPANY</div>
            <h1>Control Center</h1>
            <p>Your website, managed autonomously.</p>
          </div>
        </div>
        <div className="topActions">
          <a className="settingsLink" href="/settings">Settings</a>
          <div className={`live ${online ? "on" : ""}`}><i />{online ? "Brain online" : "Connecting"}</div>
        </div>
      </header>

      {error && <div className="alert"><span className="alertIcon">!</span><div>{error}</div></div>}

      {loading ? (
        <div className="card loading">Connecting to Brain…</div>
      ) : projects.length === 0 ? (
        <section className="hero card">
          <div className="heroCopy">
            <div className="step"><span>01</span> PROJECT</div>
            <h2>Start your first website</h2>
            <p>Create a real project for the Brain. Nothing is published automatically while Dry Run is enabled.</p>
            <div className="dryRunNote"><span className="noteDot" /><div><strong>Dry Run is on</strong><small>Safe mode · no production changes</small></div></div>
          </div>
          <form className="form" onSubmit={createProject}>
            <label>Project name<input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required /></label>
            <label>Domain<input value={form.domain} onChange={(e) => setForm({ ...form, domain: e.target.value })} required /></label>
            <label>GitHub repository <em>optional</em><input placeholder="owner/repository" value={form.repo} onChange={(e) => setForm({ ...form, repo: e.target.value })} /></label>
            <button disabled={creating}><span>{creating ? "Creating project…" : "Create project"}</span><b>→</b></button>
          </form>
        </section>
      ) : (
        <>
          <section className="project card">
            <div>
              <span className="eyebrow">YOUR PROJECT</span>
              <h2>{project?.name}</h2>
              <a href={`https://${project?.domain}`} target="_blank" rel="noreferrer">{project?.domain} ↗</a>
              <div className="badges"><Badge on /><Badge on={autonomous} text={autonomous ? "Autonomous" : "Dry Run"} /></div>
            </div>
            <div className="projectActions">
              <select value={selected ?? ""} onChange={(e) => load(Number(e.target.value))}>
                {projects.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
              <button disabled={running} onClick={runBrain}>{running ? "Running…" : "Run Brain"}</button>
              <button className="ghost" onClick={() => load(selected ?? undefined)}>Refresh</button>
            </div>
          </section>

          {analytics && (
            <>
              <div className="sectionTitle">Performance <span>Live data · {analytics.period_days} days</span></div>
              <section className="metrics">
                <Metric label="Search clicks" value={analytics.gsc.configured ? analytics.gsc.clicks.toLocaleString() : "—"} />
                <Metric label="Impressions" value={analytics.gsc.configured ? analytics.gsc.impressions.toLocaleString() : "—"} />
                <Metric label="CTR" value={analytics.gsc.configured ? `${analytics.gsc.ctr}%` : "—"} />
                <Metric label="Users" value={analytics.ga4.configured ? analytics.ga4.users.toLocaleString() : "—"} />
              </section>

              <div className="grid">
                <section className="card">
                  <div className="cardHead">
                    <div><h3>Brain</h3><p>{autonomous ? "Analyzes, decides, executes and monitors automatically." : "Analysis and planning only. Production changes are disabled."}</p></div>
                    <Badge on={online} text={online ? "Online" : "Offline"} />
                  </div>
                  <div className="brainRows">
                    <Row k="Last run" v={runs[0]?.finished_at ? new Date(runs[0].finished_at).toLocaleString() : "Never"} />
                    <Row k="Next run" v="Automatic · every 24h" />
                    <Row k="Mode" v={autonomous ? "Autonomous" : "Dry Run"} />
                  </div>
                </section>

                <section className="card">
                  <div className="cardHead">
                    <div><h3>Connections</h3><p>Live configuration</p></div>
                    <a className="miniLink" href="/settings">Manage</a>
                  </div>
                  <Integration name="GitHub" on={!!status?.integrations?.github} />
                  <Integration name="Vercel" on={!!status?.integrations?.vercel} />
                  <Integration name="Search Console" on={!!status?.integrations?.gsc} />
                  <Integration name="Analytics" on={!!status?.integrations?.ga4} />
                </section>
              </div>

              <section className="card activity">
                <div className="cardHead"><div><h3>Activity</h3><p>Recent Brain executions</p></div></div>
                {runs.length === 0 ? (
                  <div className="empty">No runs yet.</div>
                ) : (
                  runs.slice(0, 8).map((run) => (
                    <div className="activityRow" key={run.id}>
                      <strong>Run #{run.id}</strong>
                      <Badge on={run.status === "cycle_complete"} text={run.status} />
                      <span>{run.finished_at ? new Date(run.finished_at).toLocaleString() : "Running"}</span>
                    </div>
                  ))
                )}
              </section>
            </>
          )}
        </>
      )}
    </main>
  );
}

function Metric({ label, value }: { label: string; value: string }) { return <div className="metric"><span>{label}</span><strong>{value}</strong></div>; }
function Badge({ on, text = "Connected" }: { on: boolean; text?: string }) { return <span className={`badge ${on ? "good" : "muted"}`}><i />{text}</span>; }
function Row({ k, v }: { k: string; v: string }) { return <div className="row"><span>{k}</span><strong>{v}</strong></div>; }
function Integration({ name, on }: { name: string; on: boolean }) { return <div className="integration"><strong>{name}</strong><Badge on={on} text={on ? "Connected" : "Not connected"} /></div>; }
