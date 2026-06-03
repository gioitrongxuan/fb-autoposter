#!/bin/bash
# Run once on EC2 to set up fb-autoposter from scratch.
# Usage: bash setup.sh
set -e

DOMAIN="autoposter-facebook.streamdy.com"
PORT=8001
APP_DIR="/home/ubuntu/fb-autoposter"
SERVICE="fb-autoposter"
EMAIL="gioi-duong@dimage.co.jp"

echo "=== [1/7] Cloning repo ==="
cd ~
git clone https://github.com/gioitrongxuan/fb-autoposter.git
cd fb-autoposter

echo "=== [2/7] Creating virtualenv & installing deps ==="
python3 -m venv venv
venv/bin/pip install -q --upgrade pip
venv/bin/pip install -q -r requirements.txt

echo "=== [3/7] Creating .env ==="
if [ ! -f .env ]; then
  cp .env.example .env
  echo ""
  echo ">>> QUAN TRỌNG: Điền credentials vào file .env trước khi tiếp tục:"
  echo ">>> nano $APP_DIR/.env"
  echo ""
  read -p "Nhấn Enter sau khi đã điền .env..."
fi

echo "=== [4/7] Creating systemd service ==="
sudo tee /etc/systemd/system/${SERVICE}.service > /dev/null << EOF
[Unit]
Description=Facebook Auto Poster
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
ExecStart=${APP_DIR}/venv/bin/uvicorn main:app --host 0.0.0.0 --port ${PORT} --workers 1
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable ${SERVICE}
sudo systemctl start ${SERVICE}

echo "=== [5/7] Creating nginx config ==="
sudo tee /etc/nginx/sites-available/${SERVICE} > /dev/null << EOF
server {
    listen 80;
    server_name ${DOMAIN};

    location / {
        proxy_pass http://127.0.0.1:${PORT};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_read_timeout 60;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/${SERVICE} /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

echo "=== [6/7] Getting SSL certificate ==="
sudo certbot --nginx -d ${DOMAIN} --non-interactive --agree-tos -m ${EMAIL} --redirect

echo "=== [7/7] Final restart ==="
sudo systemctl restart ${SERVICE}

echo ""
echo "✅ Setup hoàn tất!"
echo "   URL: https://${DOMAIN}"
echo "   Dashboard: https://${DOMAIN}/dashboard"
echo ""
sudo systemctl status ${SERVICE} --no-pager -l
