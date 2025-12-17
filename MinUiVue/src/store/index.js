import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token'))
  const user = ref(JSON.parse(localStorage.getItem('user') || 'null'))

  const setAuth = (newToken, userData) => {
    token.value = newToken
    user.value = userData
    localStorage.setItem('token', newToken)
    localStorage.setItem('user', JSON.stringify(userData))
  }

  const logout = () => {
    token.value = null
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  }

  return { token, user, setAuth, logout }
})

export const useTopicsStore = defineStore('topics', () => {
  const topics = ref([])
  const currentTopic = ref(null)
  const progress = ref([])

  return { topics, currentTopic, progress }
})

export const useTestStore = defineStore('test', () => {
  const currentSession = ref(null)
  const questions = ref([])
  const answers = ref({})
  const result = ref(null)
  const history = ref([])

  return { currentSession, questions, answers, result, history }
})