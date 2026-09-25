<script setup lang="ts">
import { Bot, Package, ShieldCheck } from 'lucide-vue-next'

const highlights = [
  { icon: Bot, title: 'Four autonomous agents', text: 'A Team Lead architects, Frontend and Backend devs build in parallel, QA verifies.' },
  { icon: ShieldCheck, title: 'Self-correcting QA loop', text: 'Real builds, migrations and browser checks — failures are repaired automatically.' },
  { icon: Package, title: 'Ready-to-run delivery', text: 'Download a zip with Django 5 + Nuxt 3 and one command: ./start_servers.sh' },
]
</script>

<template>
  <div class="grid min-h-screen lg:grid-cols-2">
    <section class="relative hidden overflow-hidden border-r border-slate-800/70 lg:flex lg:flex-col lg:justify-between lg:p-12">
      <NexusLogo />
      <div class="space-y-10">
        <div>
          <h1 class="text-4xl font-bold leading-tight tracking-tight text-white">
            From <span class="font-mono text-3xl text-cyan-300">user_requirement.md</span><br />
            to a <span class="text-gradient">working full-stack app</span>.
          </h1>
          <p class="mt-4 max-w-md text-slate-400">
            Describe what you want. Watch a team of AI agents design, code, test and package it live.
          </p>
        </div>
        <AgentFlowGraphic />
        <ul class="space-y-4">
          <li v-for="h in highlights" :key="h.title" class="flex gap-3">
            <div class="grid h-9 w-9 shrink-0 place-items-center rounded-lg border border-slate-800 bg-slate-900/80">
              <component :is="h.icon" class="h-4 w-4 text-indigo-300" />
            </div>
            <div>
              <p class="text-sm font-medium text-slate-200">{{ h.title }}</p>
              <p class="text-sm text-slate-500">{{ h.text }}</p>
            </div>
          </li>
        </ul>
      </div>
      <p class="text-xs text-slate-600">Django 5 · DRF · Channels · Nuxt 3 · Tailwind</p>
    </section>
    <section class="flex items-center justify-center p-6 sm:p-12">
      <div class="w-full max-w-md">
        <div class="mb-8 lg:hidden"><NexusLogo /></div>
        <slot />
      </div>
    </section>
  </div>
</template>
