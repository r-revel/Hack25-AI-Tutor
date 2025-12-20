<template>
  <div class="topic-detail">
    <div class="topic-header">
      <h1>{{ topic?.title }}</h1>
      <button @click="startTest" :disabled="!topic">Начать тест</button>
    </div>

    <ProgressChat :messages="topicsStore.progress" :topicId="topicId" @send-message="sendMessage" />
  </div>
</template>

<script setup>
import progressAPI from '@/api/progress'
import testAPI from '@/api/test'
import topicsAPI from '@/api/topics'
import ProgressChat from '@/components/ProgressChat.vue'
import { useTestStore, useTopicsStore } from '@/store'
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const topicsStore = useTopicsStore()
const testStore = useTestStore()

const topicId = computed(() => parseInt(route.params.id))

const topic = computed(() => topicsStore.currentTopic)

onMounted(async () => {
  await loadTopic()
  await loadProgress()
})

const loadTopic = async () => {
  try {
    const response = await topicsAPI.getTopic(topicId.value)
    topicsStore.currentTopic = response.data
  } catch (error) {
    console.error('Failed to load topic:', error)
  }
}

const loadProgress = async () => {
  try {
    const response = await progressAPI.getProgress(topicId.value)
    topicsStore.progress = response.data
  } catch (error) {
    console.error('Failed to load progress:', error)
  }
}

const sendMessage = async (message) => {
  try {
    const response = await progressAPI.addMessage(topicId.value, {
      message,
      is_user: true,
      topic_id: topicId.value
    })
    topicsStore.progress = response.data;
  } catch (error) {
    console.error('Failed to send message:', error)
  }
}

const startTest = async () => {
  try {
    const response = await testAPI.startTest(topicId.value)
    testStore.currentSession = response.data
    router.push(`/test/${response.data.id}`)
  } catch (error) {
    console.error('Failed to start test:', error)
  }
}
</script>

<style scoped>
.topic-detail {
  padding: 20px;
}

.topic-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

button {
  padding: 10px 20px;
  background: #4CAF50;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

button:disabled {
  background: #cccccc;
  cursor: not-allowed;
}
</style>