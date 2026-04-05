"use client";

import Link from "next/link";

/**
 * Intentionally empty operator canvas. Product surfaces are being rebuilt page-by-page
 * on top of the live API; no dashboard analytics or activity widgets here.
 */
export function DashboardModule() {
  return (
    <div className="hes-blank-desk-wrap">
      <section className="hes-blank-desk" aria-labelledby="blank-desk-heading">
        <h2 id="blank-desk-heading">Operational desk</h2>
        <p>
          The web client is in a controlled rebuild. Modules will return to the navigation
          as each surface is reimplemented against the current API contracts.
        </p>
        <p className="muted">
          This page stays minimal until the next approved module ships.
        </p>
        <div className="hes-blank-desk-actions">
          <Link className="secondary-button" href="/meters">
            Meters (first rebuild target)
          </Link>
        </div>
      </section>
    </div>
  );
}
