<template>
  <div class="test-view">
    <div v-if="!result">
      <div class="test-header">
        <h2>Тест по теме: {{ topicTitle }}</h2>
        <div>Вопрос {{ currentQuestionIndex + 1 }} из {{ testStore.questions.length }}</div>
      </div>

      <QuestionCard v-if="currentQuestion" :question="currentQuestion" @answer="recordAnswer" />

      <div class="navigation">
        <button @click="prevQuestion" :disabled="currentQuestionIndex === 0">Назад</button>
        <button v-if="currentQuestionIndex < testStore.questions.length - 1" @click="nextQuestion">
          Следующий вопрос
        </button>
        <button v-else @click="submitTest" :disabled="!allAnswered">
          Завершить тест
        </button>
      </div>
    </div>

    <TestResult v-else :result="result" @retry="retryTest" @back-to-topics="goToTopics" />
  </div>
</template>

<script setup>
import testAPI from '@/api/test'
import QuestionCard from '@/components/QuestionCard.vue'
import TestResult from '@/components/TestResult.vue'
import { useTestStore, useTopicsStore } from '@/store'
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const testStore = useTestStore()
const topicsStore = useTopicsStore()

const sessionId = parseInt(route.params.sessionId)
const currentQuestionIndex = ref(0)
const result = ref(null)

const currentQuestion = computed(() =>
  testStore.questions[currentQuestionIndex.value]
)

const allAnswered = computed(() => {
  return testStore.questions.length === Object.keys(testStore.answers).length
})

const topicTitle = computed(() => {
  const topic = topicsStore.topics.find(t => t.id === testStore.currentSession?.topic_id)
  return topic?.title || ''
})

onMounted(async () => {
  await loadQuestions()
})

const loadQuestions = async () => {
  try {
    const response = await testAPI.getQuestions(sessionId)
    testStore.questions = response.data
  } catch (error) {
    console.error('Failed to load questions:', error)
  }
}

const recordAnswer = (answer) => {
  testStore.answers[answer.question_id] = answer
}

const nextQuestion = () => {
  if (currentQuestionIndex.value < testStore.questions.length - 1) {
    currentQuestionIndex.value++
  }
}

const prevQuestion = () => {
  if (currentQuestionIndex.value > 0) {
    currentQuestionIndex.value--
  }
}

const submitTest = async () => {
  try {
    const answersArray = Object.values(testStore.answers)
    const response = await testAPI.submitTest(sessionId, { answers: answersArray })
    result.value = response.data
  } catch (error) {
    console.error('Failed to submit test:', error)
  }
}

const retryTest = () => {
  testStore.answers = {}
  result.value = null
  currentQuestionIndex.value = 0
}

const goToTopics = () => {
  router.push('/')
}
</script>

<style scoped>
.test-view {
  padding: 20px;
  max-width: 800px;
  margin: 0 auto;
}

.test-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.navigation {
  display: flex;
  justify-content: space-between;
  margin-top: 30px;
}

button {
  padding: 10px 20px;
  background: #2196F3;
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