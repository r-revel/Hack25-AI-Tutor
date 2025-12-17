import client from './client'

export default {
  register(data) {
    return client.post('/register', data)
  },
  login(data) {
    return client.post('/login', data)
  }
}