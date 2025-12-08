<script setup>
defineProps({
    url: String,
    downloadOnly: Boolean
})

const emit = defineEmits(['update:url', 'update:downloadOnly', 'submit'])
</script>

<template>
    <div class="relative flex min-h-screen w-full flex-col">
        <div class="layout-container flex h-full grow flex-col">
            <div class="flex flex-1 justify-center py-5 px-4 sm:px-8 md:px-20 lg:px-40">
                <div class="layout-content-container flex w-full flex-col max-w-[960px] flex-1">
                    <!-- TopNavBar -->
                    <header class="flex items-center justify-between whitespace-nowrap border-b border-gray-200 dark:border-b-[#282e39] px-4 sm:px-6 lg:px-10 py-3">
                        <div class="flex items-center gap-4 text-gray-800 dark:text-white">
                            <div class="size-5 text-primary">
                                <svg fill="currentColor" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
                                    <path clip-rule="evenodd" d="M47.2426 24L24 47.2426L0.757355 24L24 0.757355L47.2426 24ZM12.2426 21H35.7574L24 9.24264L12.2426 21Z" fill-rule="evenodd"></path>
                                </svg>
                            </div>
                            <h2 class="text-lg font-bold leading-tight tracking-[-0.015em] text-gray-900 dark:text-white">V2T 视频转文字</h2>
                        </div>
                    </header>
                    <main class="flex-grow">
                        <!-- HeroSection -->
                        <div class="pt-16 sm:pt-24 pb-12 sm:pb-16">
                            <div class="flex min-h-[400px] flex-col gap-6 items-center justify-center p-4 text-center">
                                <div class="flex flex-col gap-2">
                                    <h1 class="text-4xl font-black leading-tight tracking-[-0.033em] text-gray-900 dark:text-white sm:text-5xl">一键提取视频精华</h1>
                                    <h2 class="text-sm font-normal leading-normal text-gray-600 dark:text-gray-300 sm:text-base">粘贴视频链接，自动生成文字版内容、大纲和原始转录</h2>
                                </div>
                                <label class="flex flex-col min-w-40 h-14 w-full max-w-[480px] sm:h-16">
                                    <div class="flex w-full flex-1 items-stretch rounded-lg h-full shadow-sm">
                                        <div class="text-gray-400 dark:text-[#9da6b9] flex border border-gray-300 dark:border-[#3b4354] bg-white dark:bg-[#1c1f27] items-center justify-center pl-4 rounded-l-lg border-r-0">
                                            <span class="material-symbols-outlined text-xl">link</span>
                                        </div>
                                        <input
                                            :value="url"
                                            @input="emit('update:url', $event.target.value)"
                                            @keypress.enter="emit('submit')"
                                            class="form-input flex w-full min-w-0 flex-1 resize-none overflow-hidden text-gray-900 dark:text-white focus:outline-none focus:ring-0 border border-gray-300 dark:border-[#3b4354] bg-white dark:bg-[#1c1f27] h-full placeholder:text-gray-400 dark:placeholder:text-[#9da6b9] px-[15px] border-r-0 border-l-0 text-sm font-normal leading-normal sm:text-base"
                                            placeholder="https://www.bilibili.com/video/..."
                                        />
                                        <div class="flex items-center justify-center rounded-r-lg border-l-0 border border-gray-300 dark:border-[#3b4354] bg-white dark:bg-[#1c1f27] pr-2">
                                            <button
                                                @click="emit('submit')"
                                                class="flex min-w-[84px] max-w-[480px] cursor-pointer items-center justify-center overflow-hidden rounded-md h-10 px-4 sm:h-12 sm:px-5 bg-primary text-white text-sm font-bold leading-normal tracking-[0.015em] hover:bg-primary/90 focus:ring-0 focus:outline-none sm:text-base"
                                            >
                                                <span class="truncate">开始转换</span>
                                            </button>
                                        </div>
                                    </div>
                                </label>
                                <!-- 仅下载选项 -->
                                <label class="flex items-center gap-2 cursor-pointer select-none">
                                    <input
                                        type="checkbox"
                                        :checked="downloadOnly"
                                        @change="emit('update:downloadOnly', $event.target.checked)"
                                        class="w-4 h-4 rounded border-gray-300 dark:border-gray-600 text-primary focus:ring-primary focus:ring-offset-0 bg-white dark:bg-[#1c1f27]"
                                    />
                                    <span class="text-sm text-gray-600 dark:text-gray-400">仅下载音视频，不转录</span>
                                </label>
                            </div>
                        </div>
                        <!-- SectionHeader -->
                        <div class="py-8">
                            <h4 class="text-sm font-bold leading-normal tracking-[0.015em] px-4 py-2 text-center text-gray-500 dark:text-[#9da6b9]">支持主流视频平台</h4>
                        </div>
                        <!-- Platform Icons -->
                        <div class="flex flex-wrap gap-8 px-4 items-center justify-center opacity-60">
                            <span class="text-gray-600 dark:text-gray-400 text-sm font-medium">哔哩哔哩</span>
                            <span class="text-gray-600 dark:text-gray-400 text-sm font-medium">抖音</span>
                            <span class="text-gray-600 dark:text-gray-400 text-sm font-medium">小红书</span>
                            <span class="text-gray-600 dark:text-gray-400 text-sm font-medium">YouTube</span>
                        </div>
                    </main>
                    <!-- Footer -->
                    <footer class="flex flex-col gap-6 px-5 py-10 text-center mt-16 border-t border-gray-200 dark:border-[#282e39]">
                        <p class="text-base font-normal leading-normal text-gray-500 dark:text-[#9da6b9]">V2T - 视频转文字工具</p>
                    </footer>
                </div>
            </div>
        </div>
    </div>
</template>
