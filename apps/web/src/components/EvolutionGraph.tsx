"use client";

import { memo, useMemo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MarkerType,
  Handle,
  Position,
  type Node,
  type Edge,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { Candidate } from "@/lib/api";
import { EmptyState } from "@/components/ui";

type Props = {
  candidates: Candidate[];
  selectedId: string | null;
  onSelect: (id: string) => void;
};

type NodeData = {
  candidate: Candidate;
  selected: boolean;
  onPath: boolean;
  faded: boolean;
  fitRank: number;
};

function statusTone(c: Candidate): "search" | "promising" | "near" | "violation" {
  if (c.violated) return "violation";
  const f = c.fitness ?? 0;
  if (f >= 0.75) return "near";
  if (f >= 0.35) return "promising";
  return "search";
}

const TONE = {
  search: {
    border: "rgba(117,83,255,0.38)",
    bg: "rgba(21,15,35,0.92)",
    chip: "chip-blue",
    label: "search",
  },
  promising: {
    border: "rgba(106,95,193,0.42)",
    bg: "rgba(32,24,52,0.95)",
    chip: "chip-purple",
    label: "promising",
  },
  near: {
    border: "rgba(242,183,18,0.55)",
    bg: "rgba(42,32,28,0.95)",
    chip: "chip-amber",
    label: "near",
  },
  violation: {
    border: "rgba(225,86,124,0.75)",
    bg: "rgba(225,86,124,0.16)",
    chip: "chip-violation",
    label: "violation",
  },
} as const;

function CandidateNode({ data }: NodeProps) {
  const d = data as NodeData;
  const c = d.candidate;
  const colors = TONE[statusTone(c)];
  const fitScale = 0.92 + d.fitRank * 0.08;

  return (
    <div
      className={`evo-node${d.selected ? " is-selected" : ""}${
        d.onPath ? " is-path" : ""
      }${d.faded ? " is-faded" : ""}${c.violated ? " is-violation" : ""}`}
      style={{
        borderColor: d.selected
          ? "var(--pink)"
          : d.onPath
            ? "var(--violation)"
            : colors.border,
        background: colors.bg,
        transform: `scale(${fitScale})`,
        opacity: d.faded ? 0.28 : d.onPath || d.selected ? 1 : 0.72,
      }}
    >
      <Handle type="target" position={Position.Left} style={{ opacity: 0 }} />
      <div className="evo-node-meta">
        <span className={`chip ${colors.chip} evo-chip`}>{colors.label}</span>
        <span className="evo-gen">g{c.generation}</span>
      </div>
      <div className="evo-node-id" title={c.id}>
        {c.id.length > 10 ? `${c.id.slice(0, 8)}…` : c.id}
      </div>
      <div className="evo-node-fit">
        <span className="lbl">fit</span>
        <span className="val">
          {c.fitness == null ? "—" : c.fitness.toFixed(2)}
        </span>
      </div>
      <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />
    </div>
  );
}

const nodeTypes = { candidate: memo(CandidateNode) };

function lineageIds(candidates: Candidate[], tipId: string | null): Set<string> {
  const set = new Set<string>();
  if (!tipId) return set;
  const byId = new Map(candidates.map((c) => [c.id, c]));
  let cur: string | null = tipId;
  while (cur) {
    set.add(cur);
    const node = byId.get(cur);
    cur = node?.parent_id ?? node?.genome?.parent_id ?? null;
  }
  return set;
}

export function EvolutionGraph({ candidates, selectedId, onSelect }: Props) {
  const path = useMemo(() => {
    const violator = candidates.find((c) => c.violated);
    return lineageIds(candidates, selectedId || violator?.id || null);
  }, [candidates, selectedId]);

  const hasPathFocus = path.size > 0;

  const { nodes, edges } = useMemo(() => {
    const byGen = new Map<number, Candidate[]>();
    for (const c of candidates) {
      const g = c.generation ?? 0;
      if (!byGen.has(g)) byGen.set(g, []);
      byGen.get(g)!.push(c);
    }
    const gens = [...byGen.keys()].sort((a, b) => a - b);
    const builtNodes: Node[] = [];
    const builtEdges: Edge[] = [];
    const xGap = 148;
    const yGap = 72;
    const lanePadY = 36;

    const fitnessVals = candidates
      .map((c) => c.fitness)
      .filter((f): f is number => f != null);
    const fMin = fitnessVals.length ? Math.min(...fitnessVals) : 0;
    const fMax = fitnessVals.length ? Math.max(...fitnessVals) : 1;
    const fSpan = Math.max(fMax - fMin, 0.001);

    gens.forEach((gen, gi) => {
      const row = [...(byGen.get(gen) || [])].sort(
        (a, b) => (b.fitness ?? 0) - (a.fitness ?? 0)
      );

      builtNodes.push({
        id: `lane-g${gen}`,
        type: "default",
        position: { x: gi * xGap - 4, y: 0 },
        data: { label: `Gen ${gen}` },
        draggable: false,
        selectable: false,
        style: {
          width: 104,
          padding: "2px 0",
          background: "transparent",
          border: "none",
          color: "var(--muted)",
          fontSize: 10,
          fontFamily: "var(--font-mono)",
          fontWeight: 600,
          letterSpacing: "0.06em",
          textTransform: "uppercase" as const,
          textAlign: "center" as const,
          pointerEvents: "none",
        },
      });

      row.forEach((c, ri) => {
        const onPath = path.has(c.id);
        const faded = hasPathFocus && !onPath && c.id !== selectedId;
        const fitRank =
          c.fitness == null ? 0.35 : (c.fitness - fMin) / fSpan;

        builtNodes.push({
          id: c.id,
          type: "candidate",
          position: { x: gi * xGap, y: lanePadY + ri * yGap },
          data: {
            candidate: c,
            selected: c.id === selectedId,
            onPath,
            faded,
            fitRank,
          },
          zIndex: onPath || c.id === selectedId ? 10 : 1,
        });

        const parent = c.parent_id || c.genome?.parent_id;
        if (parent) {
          const edgeOnPath = path.has(c.id) && path.has(parent);
          builtEdges.push({
            id: `${parent}-${c.id}`,
            source: parent,
            target: c.id,
            type: "smoothstep",
            animated: edgeOnPath,
            style: {
              stroke: edgeOnPath
                ? "var(--violation)"
                : faded
                  ? "rgba(144,147,193,0.12)"
                  : "rgba(144,147,193,0.28)",
              strokeWidth: edgeOnPath ? 2.25 : 1,
              opacity: faded ? 0.35 : 1,
            },
            markerEnd: {
              type: MarkerType.ArrowClosed,
              width: edgeOnPath ? 14 : 10,
              height: edgeOnPath ? 14 : 10,
              color: edgeOnPath ? "#E1567C" : "#6b6e96",
            },
          });
        }
      });
    });

    return { nodes: builtNodes, edges: builtEdges };
  }, [candidates, selectedId, path, hasPathFocus]);

  if (candidates.length === 0) {
    return (
      <EmptyState
        title="No candidates evaluated"
        className="h-full min-h-[320px] justify-center"
      >
        <p>The campaign will populate the graph as genomes are scored.</p>
      </EmptyState>
    );
  }

  return (
    <div className="evo-canvas">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.22 }}
        proOptions={{ hideAttribution: true }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable
        onNodeClick={(_, n) => {
          if (n.id.startsWith("lane-")) return;
          onSelect(n.id);
        }}
        minZoom={0.28}
        maxZoom={1.6}
      >
        <Background gap={20} size={1} color="rgba(144,147,193,0.09)" />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
