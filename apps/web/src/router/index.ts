import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import InitialPage from '@/pages/InitialPage.vue'
import ResultPage from '@/pages/ResultPage.vue'
import { reportPageview } from '@/api/metrics'

const routes: RouteRecordRaw[] = [
    {
        path: '/',
        name: 'home',
        component: InitialPage,
    },
    {
        path: '/w/:id',
        name: 'workspace',
        component: ResultPage,
        props: true,
    },
    {
        // 后台管理（运营统计）。懒加载，避免后台代码进主包。
        path: '/admin',
        name: 'admin',
        component: () => import('@/pages/AdminDashboard.vue'),
    },
    {
        path: '/:pathMatch(.*)*',
        redirect: '/',
    },
]

const router = createRouter({
    history: createWebHistory('/'),
    routes,
})

// 全站 PV/UV 埋点：每次路由切换上报，admin 自身访问不计入统计
router.afterEach((to) => {
    if (to.name !== 'admin') {
        reportPageview(to.path)
    }
})

export default router
