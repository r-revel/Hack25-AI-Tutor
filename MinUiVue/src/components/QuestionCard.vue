<template>
  <div class="question-card">
    <h3>{{ question.question_text }}</h3>
    <div class="options">
      <div 
        v-for="option in options" 
        :key="option.key"
        :class="['option', { selected: selectedAnswer === option.key }]"
        @click="selectAnswer(option.key)"
      >
        {{ option.key.toUpperCase() }}. {{ option.text }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  question: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['answer'])

const selectedAnswer = ref('')

const options = computed(() => [
  { key: 'a', text: props.question.option_a },
  { key: 'b', text: props.question.option_b },
  { key: 'c', text: props.question.option_c },
  { key: 'd', text: props.question.option_d }
])

const selectAnswer = (key) => {
  selectedAnswer.value = key
  emit('answer', { 
    question_id: props.question.id, 
    user_answer: key.toUpperCase() 
  })
}
</script>

<style scoped>
.question-card {
  padding: 20px;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  margin: 20px 0;
}
.options {
  margin-top: 20px;
}
.option {
  padding: 12px;
  margin: 8px 0;
  border: 1px solid #ddd;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}
.option:hover {
  background: #f5f5f5;
}
.option.selected {
  background: #e3f2fd;
  border-color: #2196F3;
}
</style>