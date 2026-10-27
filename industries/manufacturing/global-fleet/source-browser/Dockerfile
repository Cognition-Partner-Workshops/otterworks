ARG RUN_IMAGE=public.ecr.aws/docker/library/nginx:1.27-alpine
FROM ${RUN_IMAGE}
COPY source-browser/nginx.conf /etc/nginx/conf.d/default.conf
COPY mainframe/ /srv/mainframe/
RUN find /srv/mainframe -type d -exec chmod 555 {} + && find /srv/mainframe -type f -exec chmod 444 {} +
EXPOSE 8080
