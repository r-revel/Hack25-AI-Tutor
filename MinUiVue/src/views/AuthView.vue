<template>
  <div class="auth-container">
    <h2>{{ isLogin ? 'Вход' : 'Регистрация' }}</h2>
    <form @submit.prevent="handleSubmit">
      <input v-model="form.username" placeholder="Имя пользователя">
      <input v-if="!isLogin" v-model="form.email" type="email" placeholder="Email">
      <input v-model="form.password" type="password" placeholder="Пароль">
      <button type="submit">{{ isLogin ? 'Войти' : 'Зарегистрироваться' }}</button>
    </form>
    <button @click="toggleMode">
      {{ isLogin ? 'Нет аккаунта? Зарегистрироваться' : 'Есть аккаунт? Войти' }}
    </button>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/store'
import authAPI from '@/api/auth'

const router = useRouter()
const authStore = useAuthStore()

const isLogin = ref(true)
const form = ref({
  username: '',
  email: '',
  password: ''
})

const toggleMode = () => {
  isLogin.value = !isLogin.value
  Object.keys(form.value).forEach(key => form.value[key] = '')
}

const handleSubmit = async () => {
  try {
    let response
    if (isLogin.value) {
      response = await authAPI.login({
        username: form.value.username,
        password: form.value.password
      })
    } else {
      response = await authAPI.register(form.value)
    }
    
    authStore.setAuth(response.data.access_token, response.data)
    router.push('/')
  } catch (error) {
    console.error('Auth error:', error)
    alert(error.response?.data?.detail || 'Ошибка авторизации')
  }
}
</script>

<style scoped>
.auth-container {
  max-width: 300px;
  margin: 100px auto;
  padding: 20px;
  border: 1px solid #ccc;
  border-radius: 8px;
}
input {
  display: block;
  width: 100%;
  margin: 10px 0;
  padding: 8px;
}
button {
  width: 100%;
  padding: 10px;
  margin: 5px 0;
}
</style>