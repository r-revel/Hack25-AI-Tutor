<template>
  <div>
    <h1>Темы для изучения</h1>
    <div class="topics-grid">
      <TopicCard v-for="topic in topicsStore.topics" :key="topic.id" :topic="topic" @click="goToTopic(topic.id)" />
    </div>
  </div>
</template>

<script setup>
import topicsAPI from '@/api/topics'
import TopicCard from '@/components/TopicCard.vue'
import { useTopicsStore } from '@/store'
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const topicsStore = useTopicsStore()

onMounted(async () => {
  try {
    const response = await topicsAPI.getTopics()
    topicsStore.topics = response.data
  } catch (error) {
    console.error('Failed to load topics:', error)
  }
})

const goToTopic = (id) => {
  router.push(`/topics/${id}`)
}
</script>

<style scoped>
.topics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 20px;
  padding: 20px;
}
</style>