import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import {defineConfig} from 'vite';

export default defineConfig(() => {
  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, '.'),
      },
    },
    server: {
      // 可通过 DISABLE_HMR 环境变量关闭热更新。
      hmr: process.env.DISABLE_HMR !== 'true',
      // 关闭热更新时同步关闭文件监听。
      watch: process.env.DISABLE_HMR === 'true' ? null : {},
    },
  };
});
