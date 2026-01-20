import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import InitialPage from '@/components/InitialPage.vue'
import ResultPage from '@/components/ResultPage.vue'

const routes: RouteRecordRaw[] = [
    {
        path: '/',
        name: 'home',
        component: InitialPage,
    },
    {
        path: '/task/:id',
        name: 'task',
        component: ResultPage,
        props: true,
    },
    {
        path: '/:pathMatch(.*)*',
        redirect: '/',
    },
]

const router = createRouter({
    history: createWebHistory('/v2t/'),
    routes,
})

export default router
