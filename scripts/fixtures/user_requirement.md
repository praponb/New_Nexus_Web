# Simple Todo List WebApp

## Overview
A single-page todo list for one person to keep track of everyday tasks.

## Features
- Add a task with a title (required, max 200 characters), an optional description and an optional due date.
- See all tasks in a list: incomplete tasks first, newest first.
- Mark a task as complete or incomplete with a checkbox; completed tasks are shown struck through.
- Edit a task's title inline.
- Delete a task.
- Filter the list by All / Active / Completed, and show how many tasks remain.

## Data
- Task: title, description, completed (default false), due_date (optional), created_at, updated_at.

## API
- REST endpoints under /api/ for listing (with an optional status filter), creating, updating and deleting tasks.

## Non-functional
- Clean, modern, responsive UI with a dark theme.
- Show friendly loading, empty and error states.
