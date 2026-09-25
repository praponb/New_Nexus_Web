<script setup lang="ts">
import type { Todo } from '~/stores/todos'

const props = defineProps<{ todo: Todo }>()
const emit = defineEmits<{
  toggle: [todo: Todo]
  remove: [todo: Todo]
  save: [todo: Todo, patch: Partial<Todo>]
}>()

const editing = ref(false)
const draft = ref(props.todo.title)

function save() {
  const title = draft.value.trim()
  if (title && title !== props.todo.title) emit('save', props.todo, { title })
  editing.value = false
}
</script>

<template>
  <li class="flex items-center gap-3 rounded-lg border border-slate-800 bg-slate-900/60 px-4 py-3">
    <input
      type="checkbox"
      class="h-4 w-4 accent-indigo-500"
      :checked="todo.completed"
      @change="emit('toggle', todo)"
    />
    <div class="min-w-0 flex-1">
      <input
        v-if="editing"
        v-model="draft"
        class="w-full rounded bg-slate-800 px-2 py-1 text-sm outline-none"
        @keyup.enter="save"
        @blur="save"
      />
      <p
        v-else
        class="truncate text-sm"
        :class="todo.completed ? 'text-slate-500 line-through' : 'text-slate-100'"
        @dblclick="editing = true"
      >
        {{ todo.title }}
      </p>
      <p v-if="todo.due_date" class="text-xs text-slate-500">Due {{ todo.due_date }}</p>
    </div>
    <button class="text-xs text-slate-400 hover:text-indigo-400" @click="editing = true">Edit</button>
    <button class="text-xs text-slate-400 hover:text-rose-400" @click="emit('remove', todo)">Delete</button>
  </li>
</template>
