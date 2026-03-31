import type { PlatformModuleDescriptor } from "@sunrise/shared-types";

const plannedModules: PlatformModuleDescriptor[] = [
  { key: "ami-ingestion", label: "AMI ingestion", status: "planned" },
  { key: "gis-topology", label: "GIS topology", status: "planned" },
  { key: "job-orchestration", label: "Job orchestration", status: "planned" },
];

export default function HomePage() {
  const apiBaseUrl =
    process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

  return (
    <main className="page-shell">
      <section className="hero">
        <p className="eyebrow">Sunrise HES Platform</p>
        <h1>Production-oriented HES/AMI monorepo scaffold</h1>
        <p className="lead">
          Modular foundation for FastAPI services, queue-based workers,
          PostGIS-ready persistence, and a Next.js operations console.
        </p>
      </section>

      <section className="panel">
        <h2>Environment</h2>
        <p>API base URL: {apiBaseUrl}</p>
      </section>

      <section className="panel">
        <h2>Meter Details / Commands Tab MVP</h2>
        <p>
          Open <code>/meters/&lt;meter-id&gt;</code> to use the bounded meter
          details commands tab for recent command visibility, command detail, and
          execute-now actions.
        </p>
      </section>

      <section className="panel">
        <h2>Commands Module MVP</h2>
        <p>
          Open <code>/commands</code> to use the bounded global commands module for
          recent command visibility and command detail across the stable operational
          families.
        </p>
      </section>

      <section className="panel">
        <h2>Planned modules</h2>
        <ul>
          {plannedModules.map((module) => (
            <li key={module.key}>
              {module.label} ({module.status})
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
