<template>
  <svg class="assistant-avatar" viewBox="0 0 48 48" role="img" aria-label="Assistante virtuelle">
    <defs>
      <clipPath id="assistant-avatar-clip"><rect width="48" height="48" rx="13" /></clipPath>
    </defs>
    <g clip-path="url(#assistant-avatar-clip)">
      <rect width="48" height="48" fill="#f4ecdf" />
      <!-- shoulders / top, tinted with the brand accent -->
      <path d="M4 48c0-9.5 8-14.5 20-14.5S44 38.5 44 48Z" fill="var(--ai-accent, #a9793f)" opacity="0.9" />
      <path d="M20 32h8v6l-4 2-4-2Z" fill="#eab68d" />
      <!-- hair (back) -->
      <path d="M11 26c0-11.6 5.4-17 13-17s13 5.4 13 17v8c-2.4-3.4-5-2-5-2H16s-2.6-1.4-5 2Z" fill="#4a3a2e" />
      <!-- face -->
      <path d="M15 23c0-7.2 3.9-11 9-11s9 3.8 9 11-3.9 12-9 12-9-4.8-9-12Z" fill="#f1c49c" />
      <!-- fringe -->
      <path d="M15 22c0-7.6 4-11 9-11s9 3.4 9 11c-1.8-3.6-4.8-5-9-5s-7.2 1.4-9 5Z" fill="#4a3a2e" />
      <!-- brows -->
      <path d="M18.6 20.4c1.3-.8 2.7-.8 4 0" stroke="#4a3a2e" stroke-width="0.9" fill="none" stroke-linecap="round" />
      <path d="M25.4 20.4c1.3-.8 2.7-.8 4 0" stroke="#4a3a2e" stroke-width="0.9" fill="none" stroke-linecap="round" />
      <!-- eyes -->
      <ellipse cx="20.6" cy="23.2" rx="1.25" ry="1.6" fill="#3a2e28" />
      <ellipse cx="27.4" cy="23.2" rx="1.25" ry="1.6" fill="#3a2e28" />
      <!-- blush -->
      <ellipse cx="18.6" cy="26.4" rx="1.7" ry="1.1" fill="#eaa982" opacity="0.55" />
      <ellipse cx="29.4" cy="26.4" rx="1.7" ry="1.1" fill="#eaa982" opacity="0.55" />
      <!-- smile -->
      <path d="M21 27.4c1.8 1.9 4.2 1.9 6 0" stroke="#c6785a" stroke-width="1.3" fill="none" stroke-linecap="round" />
      <!-- headset band + earpiece + mic -->
      <path
        d="M13 24c0-8.4 4.9-13 11-13s11 4.6 11 13"
        stroke="#2c2521"
        stroke-width="2.1"
        fill="none"
        stroke-linecap="round"
      />
      <rect x="10.8" y="22.5" width="4.2" height="7" rx="2.1" fill="#2c2521" />
      <path d="M12.9 29c0 3.8 2.9 6.2 6.6 6.6" stroke="#2c2521" stroke-width="1.6" fill="none" stroke-linecap="round" />
      <circle cx="19.8" cy="35.8" r="1.5" fill="#2c2521" />
    </g>
  </svg>
</template>

<script lang="ts" setup></script>

<style scoped>
.assistant-avatar {
  display: block;
  width: 100%;
  height: 100%;
}
</style>
