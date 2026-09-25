export interface RequirementPreset {
  key: string
  label: string
  content: string
}

export const REQUIREMENT_PRESETS: RequirementPreset[] = [
  {
    key: 'ecommerce',
    label: 'E-Commerce Store',
    content: `# E-Commerce Store

## Overview
An online storefront where shoppers browse products, add them to a cart and place orders.

## Features
- Product catalog with name, description, price, stock quantity, category and image URL.
- Category filter and text search on the product list.
- Product detail page with an "Add to cart" button and quantity selector.
- Cart page: change quantities, remove items, see the running total.
- Checkout form (name, email, shipping address) that creates an order and clears the cart.
- Orders page listing past orders with status (pending, shipped, delivered) and totals.

## Data
- Category, Product, Order, OrderItem.

## Non-functional
- Clean, modern dark UI; responsive on mobile.
- Stock must not go below zero when an order is placed.
`,
  },
  {
    key: 'saas',
    label: 'SaaS Dashboard',
    content: `# SaaS Metrics Dashboard

## Overview
An internal dashboard for tracking customers, subscriptions and monthly recurring revenue (MRR).

## Features
- Customers: create, edit, delete; fields company name, contact email, plan, signup date, status (trial, active, churned).
- Plans: name, monthly price, seat limit.
- Dashboard page with KPI cards: total MRR, active customers, trials, churn this month.
- Customers table with sorting by signup date and filtering by status and plan.
- Customer detail page showing plan history.

## Data
- Plan, Customer, PlanChange (customer, old plan, new plan, changed_at).

## Non-functional
- MRR is computed from active customers' plans on the backend.
- Responsive layout with a sidebar navigation.
`,
  },
  {
    key: 'social',
    label: 'Social Feed',
    content: `# Social Feed

## Overview
A lightweight social feed where people post short updates, like and comment.

## Features
- Create a post with author name and text (max 280 characters).
- Feed page showing newest posts first with like count and comment count.
- Like / unlike a post (likes stored per author name).
- Post detail page with comments; add a comment with author name and text.
- Filter the feed by author.

## Data
- Post, Comment, Like.

## Non-functional
- Optimistic UI updates for likes.
- Character counter on the post composer.
`,
  },
  {
    key: 'custom',
    label: 'Custom',
    content: `# My Web App

## Overview
Describe what the app does and who uses it.

## Features
- Feature one: what the user can do and what they see.
- Feature two: ...

## Data
- List the main entities and their fields.

## Non-functional
- Any constraints: validation rules, sorting, design preferences.
`,
  },
]
