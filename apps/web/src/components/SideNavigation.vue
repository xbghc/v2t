<script setup lang="ts">
import { ref } from 'vue'
import type { SideNavItem, SideNavKey } from '@/types'
import IconClose from '~icons/material-symbols/close'
import IconMenu from '~icons/material-symbols/menu'
import IconArrowForward from '~icons/material-symbols/arrow-forward'
import IconAddCircle from '~icons/material-symbols/add-circle-outline'
import IconHourglassEmpty from '~icons/material-symbols/hourglass-empty'
import IconVisibility from '~icons/material-symbols/visibility-outline'

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

const isMobileMenuOpen = ref(false)

const toggleMobileMenu = () => {
    isMobileMenuOpen.value = !isMobileMenuOpen.value
}

const closeMobileMenu = () => {
    isMobileMenuOpen.value = false
}

const handleItemClick = (key: SideNavKey, emit: (event: 'toggle-focus', key: SideNavKey) => void) => {
    emit('toggle-focus', key)
    closeMobileMenu()
}

const handleScrollClick = (key: SideNavKey, emit: (event: 'scroll-to', key: SideNavKey) => void) => {
    emit('scroll-to', key)
    closeMobileMenu()
}

const handleGenerateClick = (key: SideNavKey, emit: (event: 'generate', key: SideNavKey) => void) => {
    emit('generate', key)
    closeMobileMenu()
}

const isItemFocused = (key: SideNavKey): boolean => {
    return props.focusedItem === key
}
</script>

<template>
    <!-- 移动端汉堡菜单按钮 -->
    <button
        class="fixed left-4 top-4 z-50 cursor-pointer rounded-lg border border-line bg-surface p-2 shadow-lg lg:hidden"
        @click="toggleMobileMenu"
    >
        <component :is="isMobileMenuOpen ? IconClose : IconMenu" class="text-ink-soft" />
    </button>

    <!-- 移动端遮罩层 -->
    <Transition name="fade">
        <div
            v-if="isMobileMenuOpen"
            class="fixed inset-0 z-40 bg-ink/40 lg:hidden"
            @click="closeMobileMenu"
        />
    </Transition>

    <!-- 侧边导航栏 -->
    <nav
        :class="[
            'fixed left-0 top-0 z-50 flex h-screen w-64 flex-col border-r border-line bg-surface transition-transform duration-300 ease-in-out lg:sticky',
            isMobileMenuOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0',
        ]"
    >
        <!-- 标题区域 -->
        <div class="flex items-center gap-2.5 border-b border-line px-4 py-4">
            <span class="flex h-7 w-7 items-center justify-center rounded-lg bg-ink">
                <svg width="15" height="15" viewBox="0 0 16 16" fill="none">
                    <rect x="2" y="6" width="2" height="4" rx="1" fill="#de8c2e" />
                    <rect x="6" y="2.5" width="2" height="11" rx="1" fill="#fff" />
                    <rect x="10" y="5" width="2" height="6" rx="1" fill="#fff" />
                </svg>
            </span>
            <span class="font-title text-base font-bold tracking-tight text-ink">Gist</span>
        </div>

        <!-- 导航项列表 -->
        <div class="flex-1 overflow-y-auto py-2">
            <div v-if="items.length > 0">
                <div
                    v-for="item in items"
                    :key="item.key"
                    class="group flex cursor-pointer items-center justify-between px-4 py-3 transition-colors hover:bg-surface-sunk"
                    :class="{
                        'bg-signal-soft': isItemFocused(item.key),
                        'opacity-50': !item.hasContent && !item.isLoading,
                    }"
                    @click="handleItemClick(item.key, $emit)"
                >
                    <div class="flex min-w-0 flex-1 items-center gap-3">
                        <component
                            :is="item.icon"
                            class="text-xl"
                            :class="isItemFocused(item.key) ? 'text-signal' : 'text-ink-faint'"
                        />
                        <span
                            class="truncate text-sm font-medium"
                            :class="isItemFocused(item.key) ? 'text-signal-ink' : 'text-ink-soft'"
                        >
                            {{ item.label }}
                        </span>
                        <span
                            v-if="item.isLoading"
                            class="h-4 w-4 flex-shrink-0 animate-spin rounded-full border-2 border-signal border-t-transparent"
                        />
                    </div>

                    <button
                        class="flex-shrink-0 cursor-pointer rounded-lg p-1.5 opacity-0 transition-all hover:bg-line group-hover:opacity-100"
                        title="跳转到此区块"
                        @click.stop="handleScrollClick(item.key, $emit)"
                    >
                        <IconArrowForward class="text-lg text-ink-faint" />
                    </button>
                </div>
            </div>

            <!-- 分隔线 -->
            <div
                v-if="disabledItems.length > 0 && items.length > 0"
                class="mx-4 my-2 border-t border-line"
            />

            <!-- 可生成内容 -->
            <div v-if="disabledItems.length > 0">
                <p class="px-4 py-2 font-mono text-[11px] uppercase tracking-wider text-ink-faint">
                    可生成
                </p>
                <div
                    v-for="item in disabledItems"
                    :key="item.key"
                    class="group flex cursor-pointer items-center justify-between px-4 py-3 text-ink-faint transition-colors hover:bg-surface-sunk hover:text-signal"
                    @click="handleGenerateClick(item.key, $emit)"
                >
                    <div class="flex min-w-0 flex-1 items-center gap-3">
                        <component :is="item.icon" class="text-xl" />
                        <span class="truncate text-sm font-medium">{{ item.label }}</span>
                    </div>
                    <IconAddCircle class="text-lg flex-shrink-0" />
                </div>
            </div>

            <!-- 空状态 -->
            <div
                v-if="items.length === 0 && disabledItems.length === 0"
                class="px-4 py-8 text-center text-ink-faint"
            >
                <IconHourglassEmpty class="mb-2 text-4xl" />
                <p class="text-sm">等待内容加载...</p>
            </div>
        </div>

        <!-- 聚焦模式提示 -->
        <Transition name="slide-up">
            <div
                v-if="focusedItem"
                class="border-t border-line bg-signal-soft p-3"
            >
                <div class="flex items-center gap-2 text-sm text-signal-ink">
                    <IconVisibility class="text-lg" />
                    <span>聚焦模式</span>
                </div>
                <p class="mt-1 text-xs text-ink-faint">点击当前项或其他项切换</p>
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
