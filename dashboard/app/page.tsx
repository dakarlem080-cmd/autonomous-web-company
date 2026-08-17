"use client";

import { useEffect, useState } from "react";

const API =
  process.env.NEXT_PUBLIC_API_URL ||
  "https://autonomous-web-company-production.up.railway.app";

type Project = {
  id: number;
  name: string;
  domain: string;
  dry_run: boolean;
  active: boolean;
};

type Analytics = {
  project: Project;
  period_days: number;
  gsc: {
    configured: boolean;
    clicks: number;
    impressions: number;
    ctr: number;
    opportunities: {
      query: string;
      page: string;
      clicks: number;
      impressions: number;
      ctr: number;
      position: number;
    }[];
  };
  ga4: {
    configured: boolean;
    users: number;
    sessions: number;
    engagement_rate: number;
  };
};

async function json<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    throw new Error(`${response.status} ${await response.text()}`);
  }
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
  const [error, setError] = useState("");

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
      if (target) {
        setSelected(target);
        const [projectAnalytics, projectRuns] = await Promise.all([
          json<Analytics>(`${API}/api/projects/${target}/analytics`),
          json<any[]>(`${API}/api/projects/${target}/runs`),
        ]);
        setAnalytics(projectAnalytics);
        setRuns(projectRuns);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Brain API unavailable");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

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

  return (
    <main>
      <header className="top">
        <div>
          <small>AUTONOMOUS WEB COMPANY</small>
          <h1>Control Center</h1>
          <p>Live control plane for the autonomous brain. No demo data.</p>
        </div>
        <div className={`status ${status?.status === "online" ? "ok" : "bad"}`}>
          <span /> {status?.status || "connecting"}
        </div>
      </header>

      {error && <div className="alert">{error}</div>}

      <section className="toolbar">
        <label>
          Project
          <select
            value={selected ?? ""}
            onChange={(event) => load(Number(event.target.value))}
          >
            {projects.length === 0 && <option value="">No projects</option>}
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name} — {project.domain}
              </option>
            ))}
          </select>
        </label>
        <button disabled={!selected || running} onClick={runBrain}>
          {running ? "Running…" : "Run brain"}
        </button>
        <button
          className="secondary"
          onClick={() => load(selected ?? undefined)}
        >
          Refresh
        </button>
      </section>

      {loading ? (
        <div className="panel">Loading live data…</div>
      ) : !analytics ? (
        <div className="panel empty">
          <h2>No project connected</h2>
          <p>
            Create a project through the Brain API before analytics can be
            shown.
          </p>
        </div>
      ) : (
        <>
          <section className="cards">
            <Metric
              label="Search clicks"
              value={
                analytics.gsc.configured
                  ? analytics.gsc.clicks.toLocaleString()
                  : "Not configured"
              }
            />
            <Metric
              label="Impressions"
              value={
                analytics.gsc.configured
                  ? analytics.gsc.impressions.toLocaleString()
                  : "Not configured"
              }
            />
            <Metric
              label="CTR"
              value={
                analytics.gsc.configured
                  ? `${analytics.gsc.ctr}%`
                  : "Not configured"
              }
            />
            <Metric
              label="Users"
              value={
                analytics.ga4.configured
                  ? analytics.ga4.users.toLocaleString()
                  : "Not configured"
              }
            />
            <Metric
              label="Sessions"
              value={
                analytics.ga4.configured
                  ? analytics.ga4.sessions.toLocaleString()
                  : "Not configured"
              }
            />
            <Metric
              label="Engagement"
              value={
                analytics.ga4.configured
                  ? `${analytics.ga4.engagement_rate}%`
                  : "Not configured"
              }
            />
          </section>

          <section className="grid2">
            <div className="panel">
              <div className="panelHead">
                <div>
                  <h2>Search opportunities</h2>
                  <p>
                    Real Google Search Console data · last {analytics.period_days} days
                  </p>
                </div>
                <span>{analytics.gsc.opportunities.length}</span>
              </div>

              {!analytics.gsc.configured ? (
                <Empty text="GSC is not configured." />
              ) : analytics.gsc.opportunities.length === 0 ? (
                <Empty text="No search rows returned." />
              ) : (
                <div className="table">
                  {analytics.gsc.opportunities.map((opportunity, index) => (
                    <div
                      className="tr"
                      key={`${opportunity.query}-${index}`}
                    >
                      <div>
                        <strong>{opportunity.query || "—"}</strong>
                        <small>{opportunity.page || "—"}</small>
                      </div>
                      <span>
                        {opportunity.clicks.toLocaleString()} clicks
                      </span>
                      <span>
                        {opportunity.impressions.toLocaleString()} imp.
                      </span>
                      <span>{opportunity.ctr.toFixed(2)}%</span>
                      <span>Pos {opportunity.position.toFixed(1)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="panel">
              <div className="panelHead">
                <div>
                  <h2>Integrations</h2>
                  <p>Actual runtime configuration</p>
                </div>
              </div>
              <Integration
                name="Google Search Console"
                on={!!status?.integrations?.gsc}
              />
              <Integration
                name="Google Analytics 4"
                on={!!status?.integrations?.ga4}
              />
              <Integration name="GitHub" on={!!status?.integrations?.github} />
              <Integration name="Vercel" on={!!status?.integrations?.vercel} />
              <Integration
                name="Autonomy mode"
                on={!status?.dry_run}
                text={status?.dry_run ? "Dry run" : "Autonomous"}
              />
            </div>
          </section>

          <section className="panel">
            <div className="panelHead">
              <div>
                <h2>Execution history</h2>
                <p>Runs recorded by the Brain API</p>
              </div>
            </div>

            {runs.length === 0 ? (
              <Empty text="No runs yet." />
            ) : (
              <div className="table">
                {runs.slice(0, 10).map((run) => (
                  <div className="tr run" key={run.id}>
                    <strong>Run #{run.id}</strong>
                    <span className={`pill ${run.status}`}>
                      {run.status}
                    </span>
                    <span>
                      {run.finished_at
                        ? new Date(run.finished_at).toLocaleString()
                        : "running"}
                    </span>
                    <span>{run.error || ""}</span>
                  </div>
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </main>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function Integration({
  name,
  on,
  text,
}: {
  name: string;
  on: boolean;
  text?: string;
}) {
  return (
    <div className="integration">
      <span className={on ? "dot on" : "dot"} />
      <strong>{name}</strong>
      <small>{text || (on ? "Connected" : "Not configured")}</small>
    </div>
  );
}

function Empty({ text }: { text: string }) {
  return <div className="empty">{text}</div>;
}
