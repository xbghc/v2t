<script setup>
defineProps({
    step: {
        type: String,
        required: true
    },
    text: {
        type: String,
        required: true
    },
    percent: {
        type: Number,
        required: true
    }
})
</script>

<template>
    <div class="px-4 pb-4">
        <div class="bg-white dark:bg-[#1c1f27] border border-gray-200 dark:border-[#282e39] rounded-lg p-4">
            <div class="flex items-center justify-between mb-2">
                <span class="text-sm font-medium text-gray-700 dark:text-gray-300">{{ step }}</span>
                <span class="text-sm text-gray-500 dark:text-gray-400">{{ text }}</span>
            </div>
            <div class="w-full bg-gray-200 dark:bg-[#3b4354] rounded-full h-2">
                <div
                    class="bg-primary h-2 rounded-full transition-all duration-500"
                    :style="{ width: percent + '%' }"
                ></div>
            </div>
        </div>
    </div>
</template>
