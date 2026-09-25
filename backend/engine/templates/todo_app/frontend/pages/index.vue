<script setup lang="ts">
import { useTodoStore, type TodoFilter } from '~/stores/todos'

const store = useTodoStore()
const title = ref('')
const dueDate = ref('')
const filters: TodoFilter[] = ['all', 'active', 'completed']

onMounted(() => store.load())

async function submit() {
  if (!title.value.trim()) return
  await store.add({ title: title.value, due_date: dueDate.value || null })
  title.value = ''
  dueDate.value = ''
}

function setFilter(filter: TodoFilter) {
  store.filter = filter
  store.load()
}
</script>

<template>
  <section class="space-y-6">
    <div>
      <h1 class="text-3xl font-bold">My tasks</h1>
      <p class="text-sm text-slate-400">{{ store.remaining }} remaining</p>
    </div>

    <form class="flex flex-wrap gap-2" @submit.prevent="submit">
      <input
        v-model="title"
        placeholder="What needs to be done?"
        class="min-w-0 flex-1 rounded-lg border border-slate-800 bg-slate-900 px-4 py-2 outline-none focus:border-indigo-500"
      />
      <input v-model="dueDate" type="date" class="rounded-lg border border-slate-800 bg-slate-900 px-3 py-2" />
      <button class="rounded-lg bg-indigo-500 px-4 py-2 font-medium hover:bg-indigo-400">Add</button>
    </form>

    <div class="flex gap-2">
      <button
        v-for="f in filters"
        :key="f"
        class="rounded-full px-3 py-1 text-xs capitalize"
        :class="store.filter === f ? 'bg-indigo-500 text-white' : 'bg-slate-800 text-slate-300'"
        @click="setFilter(f)"
      >
        {{ f }}
      </button>
    </div>

    <p v-if="store.error" class="rounded-lg bg-rose-500/10 px-4 py-2 text-sm text-rose-300">{{ store.error }}</p>
    <p v-else-if="store.loading" class="text-sm text-slate-500">Loading…</p>
    <p v-else-if="!store.items.length" class="text-sm text-slate-500">Nothing here yet.</p>

    <ul class="space-y-2">
      <TodoItem
        v-for="todo in store.items"
        :key="todo.id"
        :todo="todo"
        @toggle="store.toggle"
        @remove="store.remove"
        @save="store.update"
      />
    </ul>
  </section>
</template>
