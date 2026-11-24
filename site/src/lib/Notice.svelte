<script lang="ts">
  import type { Snippet } from 'svelte';
  let { tone = 'warn', ondismiss, children }: {
    tone?: 'warn' | 'info'; ondismiss?: () => void; children: Snippet;
  } = $props();
</script>

<div class="notice {tone}" role="status">
  <span>{@render children()}</span>
  {#if ondismiss}
    <button type="button" aria-label="Dismiss notice" onclick={ondismiss}>Dismiss</button>
  {/if}
</div>

<style>
  .notice { display: flex; justify-content: space-between; align-items: center; gap: 1rem; padding: 0.5rem 1rem; border-bottom: 1px solid; }
  .warn { background: #fef3c7; color: #422006; border-color: #f59e0b; }
  .info { background: #dbeafe; color: #172554; border-color: #3b82f6; }
  .notice :global(a) { color: inherit; font-weight: 700; }
  button { font: inherit; font-weight: 600; background: transparent; border: 1px solid currentColor; border-radius: 5px; color: inherit; padding: 0.2rem 0.6rem; cursor: pointer; }
</style>
