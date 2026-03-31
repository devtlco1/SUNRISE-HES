"use client";

import { OperationalShell } from "../operational-shell";
import { TransformersSubstationsModule } from "./transformers-substations-module";

export function TransformersSubstationsPageClient() {
  return (
    <OperationalShell
      eyebrow="Operational Pages"
      title="Transformer / Substation Visibility MVP"
      description="Read-only infrastructure visibility across transformers, parent substations, and bounded linked operational context."
    >
      {({ authorizedFetch }) => (
        <TransformersSubstationsModule authorizedFetch={authorizedFetch} />
      )}
    </OperationalShell>
  );
}
