<template>
  <div class="test-result">
    <h2>Результаты теста</h2>
    <div class="score">
      <div class="percentage">{{ result.percentage }}%</div>
      <div class="correct">
        Правильных: {{ result.correct_answers }} из {{ result.total_questions }}
      </div>
    </div>
    <button @click="$emit('retry')">Пройти заново</button>
    <button @click="$emit('back-to-topics')">К темам</button>
  </div>
</template>

<script setup>
defineProps({
  result: {
    type: Object,
    required: true
  }
})

defineEmits(['retry', 'back-to-topics'])
</script>

<style scoped>
.test-result {
  text-align: center;
  padding: 30px;
  border: 1px solid #ddd;
  border-radius: 10px;
  background: #f8f9fa;
}
.score {
  margin: 20px 0;
}
.percentage {
  font-size: 48px;
  font-weight: bold;
  color: #4CAF50;
}
.correct {
  font-size: 18px;
  color: #666;
  margin-top: 10px;
}
button {
  margin: 10px;
  padding: 10px 20px;
  background: #2196F3;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}
button:hover {
  background: #1976D2;
}
</style>