<template>
  <NuxtLink to="/dashboard" class="flex items-center gap-2.5">
    <svg viewBox="0 0 32 32" class="h-8 w-8" aria-hidden="true">
      <defs>
        <linearGradient id="nexus-logo" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stop-color="#6366f1" />
          <stop offset="1" stop-color="#06b6d4" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="9" fill="url(#nexus-logo)" />
      <path d="M9 23V9l14 14V9" fill="none" stroke="white" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" />
    </svg>
    <span class="text-lg font-bold tracking-tight text-white">Nexus</span>
  </NuxtLink>
</template>
