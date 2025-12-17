<template>
  <div class="topic-card" @click="$emit('click')">
    <div class="topic-image" v-if="topic.image">
      <img :src="topic.image" :alt="topic.title">
    </div>
    <div class="topic-content">
      <h3>{{ topic.title }}</h3>
      <p>Доступна: {{ topic.is_available ? 'Да' : 'Нет' }}</p>
      <small>Создано: {{ formatDate(topic.created_at) }}</small>
    </div>
  </div>
</template>

<script setup>
defineProps({
  topic: {
    type: Object,
    required: true
  }
})

defineEmits(['click'])

const formatDate = (dateString) => {
  return new Date(dateString).toLocaleDateString()
}
</script>

<style scoped>
.topic-card {
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  transition: transform 0.2s;
}
.topic-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}
.topic-image img {
  width: 100%;
  height: 150px;
  object-fit: cover;
}
.topic-content {
  padding: 15px;
}
h3 {
  margin: 0 0 10px 0;
}
p, small {
  margin: 5px 0;
  color: #666;
}
</style>