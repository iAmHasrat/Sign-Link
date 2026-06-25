# Local HTTPS for WebRTC Development

Browsers expose `navigator.mediaDevices.getUserMedia()` only on secure origins. A LAN URL such as `http://172.16.166.159:5173` is not secure, so camera access is unavailable.

Use HTTPS for the Vite dev server:

```text
https://172.16.166.159:5173
```

## Package Installs

No extra npm package is required. The project uses Vite's built-in HTTPS server option with a local PFX certificate.

Existing frontend packages are enough:

```powershell
npm install --prefix frontend
```

## Generate Certificates

From the project root:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\create-dev-cert.ps1 -IpAddress 172.16.166.159 -Password signlink-dev
```

This creates:

```text
certs\sign-link-dev.pfx
certs\sign-link-dev.cer
```

The PFX is used by Vite. The CER must be trusted by each laptop that opens the dev URL.

## Trust Certificate

Run this on the main laptop and the second laptop:

```powershell
Import-Certificate -FilePath "C:\Users\Lenovo\OneDrive\Desktop\sign-link-web\certs\sign-link-dev.cer" -CertStoreLocation Cert:\CurrentUser\Root
```

On the second laptop, copy `sign-link-dev.cer` first, then import from its copied path.

## Vite Config

The preferred development setup is a Vite HTTPS proxy:

- Browser calls `https://172.16.166.159:5173/api`
- Vite forwards `/api` to `http://127.0.0.1:5001`
- Browser connects Socket.IO through `https://172.16.166.159:5173/socket.io`
- Vite forwards `/socket.io` WebSocket traffic to `http://127.0.0.1:5001`
- Browser calls `https://172.16.166.159:5173/landmark-api`
- Vite forwards `/landmark-api` to `http://127.0.0.1:8000`

This avoids browser mixed-content blocking while keeping the backend and FastAPI service simple in development.

`frontend/vite.config.js` configures:

```js
server: {
  host: '0.0.0.0',
  port: 5173,
  https: {
    pfx: fs.readFileSync('../certs/sign-link-dev.pfx'),
    passphrase: 'signlink-dev'
  },
  proxy: {
    '/api': 'http://127.0.0.1:5001',
    '/socket.io': {
      target: 'http://127.0.0.1:5001',
      ws: true
    },
    '/landmark-api': {
      target: 'http://127.0.0.1:8000',
      rewrite: (path) => path.replace(/^\/landmark-api/, '')
    }
  }
}
```

Frontend env should use same-origin paths:

```env
VITE_API_URL=/api
VITE_SOCKET_URL=
VITE_LANDMARK_API_URL=/landmark-api
VITE_BACKEND_PROXY_TARGET=http://127.0.0.1:5001
VITE_LANDMARK_PROXY_TARGET=http://127.0.0.1:8000
```

Backend CORS should include:

```env
FRONTEND_URLS=http://localhost:5173,https://localhost:5173,http://172.16.166.159:5173,https://172.16.166.159:5173
```

## Restart

Stop the old HTTP Vite server:

```powershell
Ctrl + C
```

Restart frontend:

```powershell
npm run dev:frontend
```

Open:

```text
https://172.16.166.159:5173
```

## Verify In Browser Console

```js
window.isSecureContext
navigator.mediaDevices
await navigator.mediaDevices.getUserMedia({ video: true, audio: true })
```

Expected:

```text
window.isSecureContext === true
navigator.mediaDevices exists
getUserMedia returns a MediaStream after permission is allowed
```
