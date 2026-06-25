# Deployment

## Frontend

1. Set `VITE_API_URL` and `VITE_SOCKET_URL` in `frontend/.env`.
2. Run `npm run build --prefix frontend`.
3. Deploy `frontend/dist` to Netlify, Vercel, Cloudflare Pages, or any static host.

## Backend

1. Provision MySQL 8 or compatible.
2. Run `database/schema.sql`.
3. Set production variables from `backend/.env.example`.
4. Run `npm ci --omit=dev --prefix backend`.
5. Run `npm start --prefix backend`.

For long-running Node hosting, run the backend behind a process manager such as PM2 or the hosting platform's managed process runner. Terminate TLS at the platform load balancer or reverse proxy, then pass HTTPS traffic to the Node server.

## Production Notes

- Use a long random `JWT_SECRET`.
- Restrict `FRONTEND_URL` to the deployed frontend origin.
- Put MySQL on a private network where the backend can reach it.
- Add TURN servers for reliable WebRTC across strict NATs.
- Store uploaded profile pictures in object storage rather than the API filesystem.
