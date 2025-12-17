import client from './client'

export default {
  getProgress(topicId) {
    return client.get(`/topics/${topicId}/progress`)
  },
  addMessage(topicId, data) {
    return client.post(`/topics/${topicId}/progress`, data)
  }
}