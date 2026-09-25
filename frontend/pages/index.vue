<script setup lang="ts">
// Authenticated users land on the dashboard; the global middleware sends everyone else to /auth/login.
await navigateTo('/dashboard', { replace: true })
</script>

<template>
  <div />
</template>
