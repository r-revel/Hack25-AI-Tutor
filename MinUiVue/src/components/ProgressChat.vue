<template>
  <div class="progress-chat">
    <div class="messages">
      <div 
        v-for="msg in messages" 
        :key="msg.id" 
        :class="['message', msg.is_user ? 'user' : 'ai']"
      >
        {{ msg.message }}
        <div class="time">{{ formatTime(msg.created_at) }}</div>
      </div>
    </div>
    <div class="input-area">
      <input 
        v-model="newMessage" 
        @keyup.enter="send" 
        placeholder="Введите сообщение..."
      >
      <button @click="send">Отправить</button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  messages: {
    type: Array,
    default: () => []
  },
  topicId: {
    type: Number,
    required: true
  }
})

const emit = defineEmits(['send-message'])

const newMessage = ref('')

const send = () => {
  if (newMessage.value.trim()) {
    emit('send-message', newMessage.value)
    newMessage.value = ''
  }
}

const formatTime = (dateString) => {
  return new Date(dateString).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}
</script>

<style scoped>
.progress-chat {
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  height: 500px;
  display: flex;
  flex-direction: column;
}
.messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}
.message {
  margin: 10px 0;
  padding: 10px 15px;
  border-radius: 18px;
  max-width: 70%;
  word-wrap: break-word;
}
.message.user {
  background: #007AFF;
  color: white;
  margin-left: auto;
}
.message.ai {
  background: #f0f0f0;
  margin-right: auto;
}
.time {
  font-size: 12px;
  opacity: 0.7;
  margin-top: 5px;
}
.input-area {
  display: flex;
  padding: 15px;
  border-top: 1px solid #e0e0e0;
}
input {
  flex: 1;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 4px;
  margin-right: 10px;
}
button {
  padding: 10px 20px;
  background: #4CAF50;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}
</style>