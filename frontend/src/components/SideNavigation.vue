<script setup lang="ts">
import { ref } from 'vue'
import type { SideNavItem, SideNavKey } from '@/types'

interface Props {
    items: SideNavItem[]
    disabledItems: SideNavItem[]
    focusedItem: SideNavKey | null
}

const props = defineProps<Props>()

defineEmits<{
    'scroll-to': [key: SideNavKey]
    'toggle-focus': [key: SideNavKey]
    'generate': [key: SideNavKey]
}>()

// 移动端菜单状态
const isMobileMenuOpen = ref(false)

const toggleMobileMenu = () => {
    isMobileMenuOpen.value = !isMobileMenuOpen.value
}

const closeMobileMenu = () => {
    isMobileMenuOpen.value = false
}

// 处理导航项点击
const handleItemClick = (key: SideNavKey, emit: (event: 'toggle-focus', key: SideNavKey) => void) => {
    emit('toggle-focus', key)
    closeMobileMenu()
}

// 处理跳转点击
const handleScrollClick = (key: SideNavKey, emit: (event: 'scroll-to', key: SideNavKey) => void) => {
    emit('scroll-to', key)
    closeMobileMenu()
}

// 处理生成点击
const handleGenerateClick = (key: SideNavKey, emit: (event: 'generate', key: SideNavKey) => void) => {
    emit('generate', key)
    closeMobileMenu()
}

// 检查项目是否被聚焦
const isItemFocused = (key: SideNavKey): boolean => {
    return props.focusedItem === key
}
</script>

<template>
    <!-- 移动端汉堡菜单按钮 -->
    <button
        class="lg:hidden fixed top-4 left-4 z-50 p-2 rounded-lg bg-white dark:bg-dark-card shadow-lg border border-gray-200 dark:border-dark-border"
        @click="toggleMobileMenu"
    >
        <span class="material-symbols-outlined text-gray-700 dark:text-gray-300">
            {{ isMobileMenuOpen ? 'close' : 'menu' }}
        </span>
    </button>

    <!-- 移动端遮罩层 -->
    <Transition name="fade">
        <div
            v-if="isMobileMenuOpen"
            class="lg:hidden fixed inset-0 bg-black/50 z-40"
            @click="closeMobileMenu"
        />
    </Transition>

    <!-- 侧边导航栏 -->
    <nav
        :class="[
            'fixed lg:sticky top-0 left-0 h-screen w-64 bg-white dark:bg-dark-card border-r border-gray-200 dark:border-dark-border z-50 flex flex-col transition-transform duration-300 ease-in-out',
            isMobileMenuOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        ]"
    >
        <!-- 标题区域 -->
        <div class="p-4 border-b border-gray-200 dark:border-dark-border">
            <h2 class="text-lg font-semibold text-gray-900 dark:text-white">
                内容导航
            </h2>
        </div>

        <!-- 导航项列表 -->
        <div class="flex-1 overflow-y-auto py-2">
            <!-- 已生成内容 -->
            <div v-if="items.length > 0">
                <div
                    v-for="item in items"
                    :key="item.key"
                    class="group flex items-center justify-between px-4 py-3 cursor-pointer transition-colors hover:bg-gray-100 dark:hover:bg-dark-border"
                    :class="{
                        'bg-primary/10 dark:bg-primary/20': isItemFocused(item.key),
                        'opacity-60': !item.hasContent && !item.isLoading
                    }"
                    @click="handleItemClick(item.key, $emit)"
                >
                    <div class="flex items-center gap-3 flex-1 min-w-0">
                        <span
                            class="material-symbols-outlined text-xl"
                            :class="isItemFocused(item.key) ? 'text-primary' : 'text-gray-500 dark:text-gray-400'"
                        >
                            {{ item.icon }}
                        </span>
                        <span
                            class="text-sm font-medium truncate"
                            :class="isItemFocused(item.key) ? 'text-primary' : 'text-gray-700 dark:text-gray-300'"
                        >
                            {{ item.label }}
                        </span>
                        <!-- 加载指示器 -->
                        <span
                            v-if="item.isLoading"
                            class="animate-spin h-4 w-4 border-2 border-primary border-t-transparent rounded-full flex-shrink-0"
                        />
                    </div>

                    <!-- 跳转按钮 -->
                    <button
                        class="p-1.5 rounded-lg opacity-0 group-hover:opacity-100 hover:bg-gray-200 dark:hover:bg-dark-border-light transition-all flex-shrink-0"
                        title="跳转到此区块"
                        @click.stop="handleScrollClick(item.key, $emit)"
                    >
                        <span class="material-symbols-outlined text-lg text-gray-500 dark:text-gray-400">
                            arrow_forward
                        </span>
                    </button>
                </div>
            </div>

            <!-- 分隔线 -->
            <div
                v-if="disabledItems.length > 0 && items.length > 0"
                class="my-2 mx-4 border-t border-gray-200 dark:border-dark-border"
            />

            <!-- 可生成内容 -->
            <div v-if="disabledItems.length > 0">
                <p class="px-4 py-2 text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">
                    可生成
                </p>
                <div
                    v-for="item in disabledItems"
                    :key="item.key"
                    class="group flex items-center justify-between px-4 py-3 cursor-pointer transition-colors hover:bg-gray-100 dark:hover:bg-dark-border text-gray-400 dark:text-gray-500 hover:text-primary dark:hover:text-primary"
                    @click="handleGenerateClick(item.key, $emit)"
                >
                    <div class="flex items-center gap-3 flex-1 min-w-0">
                        <span class="material-symbols-outlined text-xl">
                            {{ item.icon }}
                        </span>
                        <span class="text-sm font-medium truncate">
                            {{ item.label }}
                        </span>
                    </div>

                    <!-- 生成按钮 -->
                    <span class="material-symbols-outlined text-lg flex-shrink-0">
                        add_circle
                    </span>
                </div>
            </div>

            <!-- 空状态 -->
            <div
                v-if="items.length === 0 && disabledItems.length === 0"
                class="px-4 py-8 text-center text-gray-400 dark:text-gray-500"
            >
                <span class="material-symbols-outlined text-4xl mb-2">hourglass_empty</span>
                <p class="text-sm">
                    等待内容加载...
                </p>
            </div>
        </div>

        <!-- 聚焦模式提示 -->
        <Transition name="slide-up">
            <div
                v-if="focusedItem"
                class="p-3 border-t border-gray-200 dark:border-dark-border bg-primary/5 dark:bg-primary/10"
            >
                <div class="flex items-center gap-2 text-sm text-primary">
                    <span class="material-symbols-outlined text-lg">visibility</span>
                    <span>聚焦模式</span>
                </div>
                <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    点击当前项或其他项切换
                </p>
            </div>
        </Transition>
    </nav>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
    transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
    opacity: 0;
}

.slide-up-enter-active,
.slide-up-leave-active {
    transition: all 0.3s ease;
}

.slide-up-enter-from,
.slide-up-leave-to {
    opacity: 0;
    transform: translateY(10px);
}
</style>
