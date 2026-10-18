<template>
  <view class="page">
    <app-header title="搜索错题" back />
    <state-panel state="loading" />
  </view>
</template>
<script setup>
import { onLoad } from '@dcloudio/uni-app'
import { scopedQuestionURL } from '@/utils/learning.js'
onLoad((q) =>
  uni.redirectTo({
    url: scopedQuestionURL({ subject: q.subject || '', search: q.search || q.q || '' }),
  }),
)
</script>
