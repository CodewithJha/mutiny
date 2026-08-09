"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect } from "react";

/** Alias route — detail lives under /tests/[id]. */
export default function RegressionDetailRedirect() {
  const params = useParams();
  const router = useRouter();
  const id = String(params.id);

  useEffect(() => {
    router.replace(`/tests/${id}`);
  }, [id, router]);

  return (
    <div className="page fade-in">
      <p className="text-sm text-muted">Opening test detail…</p>
    </div>
  );
}
