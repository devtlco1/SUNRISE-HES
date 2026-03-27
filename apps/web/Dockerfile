FROM node:22-alpine

WORKDIR /workspace

COPY package.json /workspace/package.json
COPY tsconfig.base.json /workspace/tsconfig.base.json
COPY packages/shared-types /workspace/packages/shared-types
COPY apps/web /workspace/apps/web

RUN npm install --workspaces

CMD ["npm", "--workspace", "apps/web", "run", "dev", "--", "--hostname", "0.0.0.0", "--port", "3000"]
