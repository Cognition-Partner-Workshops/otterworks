FROM node:24-alpine
WORKDIR /app
COPY --chown=node:node package.json server.mjs ./
COPY --chown=node:node public ./public
RUN mkdir /data && chown node:node /data
USER node
ENV HOST=0.0.0.0 STATE_FILE=/data/state.json
EXPOSE 3100
CMD ["node", "server.mjs"]
