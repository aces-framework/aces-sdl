import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
import viteTsconfigPaths from 'vite-tsconfig-paths';
import svgrPlugin from 'vite-plugin-svgr';
import envCompatible from 'vite-plugin-env-compatible';
import wasmPack from 'vite-plugin-wasm-pack';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react(),
    viteTsconfigPaths(),
    svgrPlugin(),
    envCompatible(),
    wasmPack([], ['@open-cyber-range/wasm-sdl-parser'])],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8085',
        ws: true,
      },
    },
    port: 3000,
  },
  build: {
    target: 'es2015',
    outDir: './build',
    emptyOutDir: true,
  },
});
