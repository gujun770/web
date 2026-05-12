<template>
  <div class="smart-image">
    <img
      v-if="src && !failed"
      :src="src"
      :alt="alt"
      @error="failed = true"
    />
    <div v-else class="image-fallback">
      <van-icon name="photo-o" />
      <span>暂无图片</span>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  src: {
    type: String,
    default: ''
  },
  alt: {
    type: String,
    default: 'image'
  }
})

const failed = ref(false)

watch(
  () => props.src,
  () => {
    failed.value = false
  }
)
</script>

<style scoped>
.smart-image,
.smart-image img,
.image-fallback {
  width: 100%;
  height: 100%;
}

.smart-image img {
  display: block;
  object-fit: cover;
}

.image-fallback {
  display: grid;
  place-items: center;
  gap: 6px;
  background: #e8eef7;
  color: #8a94a6;
  font-weight: 700;
}

.image-fallback :deep(.van-icon) {
  font-size: 24px;
}

.image-fallback span {
  font-size: 13px;
}
</style>
