# gi cmd: git init git add.git status

PS D:\AI\AI engineer projects\lighchat> py -3.11 -m venv env
connect to my instance:

https://eu-central-1.lightsail.aws.amazon.com/ls/remote/eu-west-3/instances/Ubuntu-1/terminal?protocol=ssh 
# RAM
free -h






so frist time:
git add .
git commit -m "fix: dockerfile torch version, add langchain-openai, full requirements"
git push origin main

podman-compose down
podman-compose up --build -d
podman-compose logs -f

and next time?










# Running containers
docker ps

#deploy local with automatic buld and run 
(env) PS D:\AI\AI engineer projects\lighchat>
podman-compose up --build
        │
        ├── 1. Reads docker-compose.yml
        ├── 2. Builds image from Dockerfile
        ├── 3. Creates container with all settings:
        │         - ports
        │         - volumes
        │         - env_file
        │         - environment vars
        │         - restart policy
        └── 4. Starts the # Deploy Locally

## Automatic (Recommended)
Build and run everything with one command:

```powershell
podman-compose up --build -d
```

This automatically:
1. Reads `docker-compose.yml`
2. Builds the image from `Dockerfile`
3. Creates the container with all settings (ports, volumes, env vars, restart policy)
4. Starts the container in the background

Check logs:
```powershell
podman-compose logs -f
```

---

## Manual (for debugging only)
```powershell
# Build image
podman build -t jitech-backend -f  .

# Run container
podman run -d -p 8000:8000 `
  -v "D:\AI\AI engineer projects\lighchat\vector_store:/app/vector_store" `
  --env-file .env `
  --name jitech-backend jitech-backend

# Check logs
podman logs jitech-backend
```

---

## Common Commands

| Action          | Command                        |
|-----------------|--------------------------------|
| Start (rebuild) | `podman-compose up --build -d` |
| Start existing  | `podman-compose up -d`         |
| Stop            | `podman-compose down`          |
| Logs            | `podman-compose logs -f`       |
| Full reset      | `podman-compose down --rmi all`|



how to start streamlit and backend at the same time?

as powershell with python:(env) PS D:\AI\AI engineer projects\lighchat> python start_both_any.py  
as bash: $ ./start_both.sh

how to copy trained data to aws cloud ?
scp -i "D:\AI\mycareer\AWS\LightsailDefaultKey-eu-west-3.pem" -r "D:\AI\AI engineer projects\chatwithmydata\tenants\azentio\jihad\data\vector_store\ai-roadmap-notes" ubuntu@51.45.26.105:/home/ubuntu/lighchat/vector_store/