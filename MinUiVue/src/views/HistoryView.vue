<template>
  <div class="history">
    <h1>История тестов</h1>
    <div class="sessions">
      <div v-for="session in testStore.history" :key="session.id" class="session-card">
        <div>Тема: {{ session.topic_id }}</div>
        <div>Начато: {{ formatDate(session.started_at) }}</div>
        <div>Завершено: {{ session.completed_at ? formatDate(session.completed_at) : 'Не завершен' }}</div>
        <div>Результат: {{ session.total_score }}%</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useTestStore } from '@/store'
import testAPI from '@/api/test'

const testStore = useTestStore()

onMounted(async () => {
  try {
    const response = await testAPI.getHistory()
    testStore.history = response.data
  } catch (error) {
    console.error('Failed to load history:', error)
  }
})

const formatDate = (dateString) => {
  return new Date(dateString).toLocaleString()
}
</script>

<style scoped>
.history {
  padding: 20px;
}
.sessions {
  display: flex;
  flex-direction: column;
  gap: 15px;
}
.session-card {
  padding: 15px;
  border: 1px solid #ddd;
  border-radius: 8px;
  background: #f9f9f9;
}
</style>