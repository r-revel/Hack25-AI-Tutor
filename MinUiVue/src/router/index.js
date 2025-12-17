import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/store'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/AuthView.vue'),
    meta: { public: true }
  },
  {
    path: '/',
    name: 'topics',
    component: () => import('@/views/TopicsView.vue')
  },
  {
    path: '/topics/:id',
    name: 'topic',
    component: () => import('@/views/TopicDetailView.vue')
  },
  {
    path: '/test/:sessionId',
    name: 'test',
    component: () => import('@/views/TestView.vue')
  },
  {
    path: '/history',
    name: 'history',
    component: () => import('@/views/HistoryView.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()
  const isAuthenticated = !!authStore.token
  
  if (!to.meta.public && !isAuthenticated) {
    next('/login')
  } else {
    next()
  }
})

export default router