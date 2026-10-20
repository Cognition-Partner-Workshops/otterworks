// PM2 process file on notify-01 and notify-02. This is the runbook:
//   pm2 start ecosystem.config.js --env production && pm2 save
// Redis runs on the same box (127.0.0.1:6379); the app assumes it is there.
module.exports = {
  apps: [
    {
      name: 'notify-svc',
      script: 'src/server.js',
      cwd: '/opt/notify-svc',
      instances: 2,
      exec_mode: 'cluster',
      max_memory_restart: '300M',
      cron_restart: '30 3 * * *',
      out_file: '/var/log/notify/out.log',
      error_file: '/var/log/notify/err.log',
      merge_logs: true,
      env_production: {
        NODE_ENV: 'production'
      }
    }
  ]
};
