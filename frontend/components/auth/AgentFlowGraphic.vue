<script setup lang="ts">
// A small animated diagram of the pipeline: requirement → Team Lead → FE ∥ BE → QA → zip.
const nodes = [
  { id: 'req', x: 40, y: 90, label: '.md', color: '#94a3b8' },
  { id: 'lead', x: 130, y: 90, label: 'Lead', color: '#818cf8' },
  { id: 'fe', x: 230, y: 40, label: 'FE', color: '#22d3ee' },
  { id: 'be', x: 230, y: 140, label: 'BE', color: '#34d399' },
  { id: 'qa', x: 330, y: 90, label: 'QA', color: '#fbbf24' },
  { id: 'zip', x: 420, y: 90, label: '.zip', color: '#e879f9' },
]
const edges = [
  ['req', 'lead'],
  ['lead', 'fe'],
  ['lead', 'be'],
  ['fe', 'qa'],
  ['be', 'qa'],
  ['qa', 'zip'],
]
const byId = Object.fromEntries(nodes.map((n) => [n.id, n]))
</script>

<template>
  <svg viewBox="0 0 460 180" class="w-full max-w-lg" role="img" aria-label="Agent pipeline diagram">
    <path
      v-for="([from, to], i) in edges"
      :key="i"
      :d="`M ${byId[from]!.x} ${byId[from]!.y} C ${(byId[from]!.x + byId[to]!.x) / 2} ${byId[from]!.y}, ${(byId[from]!.x + byId[to]!.x) / 2} ${byId[to]!.y}, ${byId[to]!.x} ${byId[to]!.y}`"
      fill="none"
      stroke="#6366f1"
      stroke-opacity="0.5"
      stroke-width="1.5"
      stroke-dasharray="4 8"
      class="animate-flow-dash"
    />
    <path
      d="M 330 90 C 330 170, 130 170, 130 105"
      fill="none"
      stroke="#fbbf24"
      stroke-opacity="0.35"
      stroke-width="1.2"
      stroke-dasharray="3 7"
      class="animate-flow-dash"
    />
    <g v-for="(n, i) in nodes" :key="n.id">
      <circle :cx="n.x" :cy="n.y" r="22" :fill="n.color" fill-opacity="0.08" :stroke="n.color" stroke-opacity="0.6">
        <animate attributeName="r" values="22;25;22" dur="2.4s" :begin="`${i * 0.35}s`" repeatCount="indefinite" />
      </circle>
      <text :x="n.x" :y="n.y + 4" text-anchor="middle" class="fill-slate-200 font-mono text-[11px]">{{ n.label }}</text>
    </g>
  </svg>
</template>
