import client from './client'

export default {
  startTest(topicId) {
    return client.post(`/topics/${topicId}/start-test`)
  },
  getQuestions(sessionId) {
    return client.get(`/test/${sessionId}/questions`)
  },
  submitTest(sessionId, data) {
    return client.post(`/test/${sessionId}/submit`, data)
  },
  getHistory(params) {
    return client.get('/test/history', { params })
  }
}