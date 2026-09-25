<script setup lang="ts">
const open = defineModel<boolean>('open', { default: false })
defineProps<{ title: string; message: string; confirmLabel?: string; loading?: boolean }>()
const emit = defineEmits<{ confirm: [] }>()
</script>

<template>
  <BaseModal v-model:open="open" :title="title">
    <p class="text-sm text-slate-300">{{ message }}</p>
    <div class="mt-6 flex justify-end gap-2">
      <BaseButton variant="ghost" @click="open = false">Cancel</BaseButton>
      <BaseButton variant="danger" :loading="loading" @click="emit('confirm')">{{ confirmLabel || 'Delete' }}</BaseButton>
    </div>
  </BaseModal>
</template>
