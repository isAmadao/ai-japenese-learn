<script setup lang="ts">
/**
 * ErrorMessage — unified error display with optional retry.
 *
 * Usage:
 *   <ErrorMessage message="加载失败" @retry="loadData" />
 *   <ErrorMessage message="加载失败" />   <!-- no retry button -->
 */
defineProps<{
  message: string
}>()

defineEmits<{
  retry: []
}>()
</script>

<template>
  <div class="error-msg">
    <p>⚠ {{ message }}</p>
    <button class="btn btn-primary btn-sm" style="margin-top: 12px" @click="$emit('retry')">
      重试
    </button>
  </div>
</template>
