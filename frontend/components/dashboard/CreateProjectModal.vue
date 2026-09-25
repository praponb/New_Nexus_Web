<script setup lang="ts">
import type { ProjectDetail } from '~/types/api'

const open = defineModel<boolean>('open', { default: false })
const emit = defineEmits<{ created: [project: ProjectDetail] }>()

const { create } = useProjects()
const name = ref('')
const description = ref('')
const loading = ref(false)
const error = ref('')

watch(open, (value) => {
  if (value) {
    name.value = ''
    description.value = ''
    error.value = ''
  }
})

async function submit() {
  if (!name.value.trim()) {
    error.value = 'Give your project a name.'
    return
  }
  loading.value = true
  error.value = ''
  try {
    const project = await create({ name: name.value.trim(), description: description.value.trim() })
    open.value = false
    emit('created', project)
  } catch (err: any) {
    error.value = err?.message || 'Could not create the project.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <BaseModal v-model:open="open" title="New WebApp Project" description="Name it now; you will add the requirement on the next screen.">
    <form class="space-y-4" @submit.prevent="submit">
      <BaseInput v-model="name" label="Project name" placeholder="Inventory SaaS App" :error="error" autofocus />
      <BaseInput v-model="description" label="Short description" placeholder="Multi-tenant inventory tracker" multiline :rows="3" />
      <div class="flex justify-end gap-2 pt-2">
        <BaseButton variant="ghost" @click="open = false">Cancel</BaseButton>
        <BaseButton type="submit" variant="glow" :loading="loading">Create project</BaseButton>
      </div>
    </form>
  </BaseModal>
</template>
