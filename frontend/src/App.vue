<script setup lang="ts">
import { RouterView, RouterLink } from 'vue-router'
</script>

<template>
  <nav>
    <RouterLink to="/" class="logo">📖 日本語学習</RouterLink>
    <RouterLink to="/">首页</RouterLink>
    <RouterLink to="/favorites">收藏</RouterLink>
    <RouterLink to="/learned">已学习</RouterLink>
  </nav>

  <main>
    <RouterView />
  </main>
</template>
