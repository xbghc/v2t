<script setup>
defineProps({
    size: {
        type: String,
        default: '5'
    }
})
</script>

<template>
    <div
        :class="`size-${size}`"
        class="text-primary"
    >
        <svg
            fill="currentColor"
            viewBox="0 0 48 48"
            xmlns="http://www.w3.org/2000/svg"
        >
            <path
                clip-rule="evenodd"
                d="M47.2426 24L24 47.2426L0.757355 24L24 0.757355L47.2426 24ZM12.2426 21H35.7574L24 9.24264L12.2426 21Z"
                fill-rule="evenodd"
            />
        </svg>
    </div>
</template>
