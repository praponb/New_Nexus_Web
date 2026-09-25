<script setup lang="ts">
// §7.2 names this screen /projects/[id]/generate; the canonical route is mission-control.
const route = useRoute()
await navigateTo(`/projects/${route.params.id}/mission-control`, { replace: true })
</script>

<template>
  <div />
</template>
