import client from './client'

export default {
  getTopics(params) {
    return client.get('/topics', { params })
  },
  getTopic(id) {
    return client.get(`/topics/${id}`)
  }
}