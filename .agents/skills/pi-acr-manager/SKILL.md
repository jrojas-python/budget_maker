---
name: pi-acr-manager
description: "Build, push Docker images to Azure Container Registry (ACR) and update Azure Container Apps. Use this skill whenever the user says 'sube la imagen', 'haz deploy de la imagen', 'sube el contenedor', 'haz deploy del proyecto', 'deploy to ACR', 'push image', 'actualiza el contenedor', 'deploy container', 'sube al registro', 'publica la imagen', or any variation of deploying/pushing a Docker image to ACR and updating a Container App. Also trigger when the user explicitly mentions 'pi-acr-manager'. This skill handles the full cycle: build, tag, push, and container app update with verification."
---

# PI ACR Manager

End-to-end workflow for building Docker images, pushing them to Azure Container Registry, and updating Azure Container Apps.

## Workflow

### Step 1 — Gather parameters

Before doing anything, collect these values. Use `vscode_askQuestions` to ask the user for all of them at once:

| Parameter | How to obtain |
|-----------|---------------|
| **Suscripción** | Ask the user |
| **Grupo de recursos** | Ask the user |
| **Nombre del ACR** | Ask the user |
| **Nombre de la imagen** | Ask the user |
| **Container App** | Ask the user |
| **Versión** | Read automatically from `__version__.py` (see below). If the file doesn't exist, ask the user. |

For version detection, search for `__version__.py` in the workspace using `file_search` with pattern `**/__version__.py`. Parse the file and extract the value assigned to `__version__`. This is the image tag.

### Step 2 — Set Azure subscription

```bash
az account set --subscription "<subscription>"
```

### Step 3 — Resolve ACR login server

```bash
az acr show --name <acr_name> --resource-group <resource_group> --query loginServer -o tsv
```

Save the result as `LOGIN_SERVER` — you'll need it for tagging and pushing.

### Step 4 — Build and push the image

Try **local Docker first**, then fall back to **cloud build**.

#### Option A — Local Docker build

```bash
# Login to ACR
az acr login --name <acr_name>

# Build
docker build -t <image_name>:<version> .

# Tag
docker tag <image_name>:<version> <LOGIN_SERVER>/<image_name>:<version>

# Push
docker push <LOGIN_SERVER>/<image_name>:<version>
```

If `az acr login` or `docker build` fail because Docker is not running or not installed, switch to Option B.

#### Option B — Cloud build (ACR Tasks)

This builds the image directly in the cloud — no local Docker needed.

Before running, check if a `.dockerignore` file exists. If not, create one to exclude heavy/unnecessary directories:

```
.venv
.git
.vscode
.agents
__pycache__
*.pyc
.env
.env-*
env.local
scripts
*.md
*.docx
.gitignore
.funcignore
.dockerignore
docker-compose.yml
azure-pipelines.yml
```

Then check the `Dockerfile` — if it pulls from Docker Hub (e.g., `FROM python:3.12-slim`), Docker Hub rate limits may block the cloud build. To handle this:

1. Check if the base image already exists in the ACR:
   ```bash
   az acr repository list --name <acr_name> -o table
   az acr repository show-tags --name <acr_name> --repository <base_image_name> -o table
   ```

2. If the base image exists in ACR, temporarily update the Dockerfile `FROM` line to reference the ACR copy:
   ```
   FROM <LOGIN_SERVER>/<base_image_name>:<tag>
   ```

3. Run the cloud build:
   ```bash
   az acr build --registry <acr_name> --resource-group <resource_group> --image <image_name>:<version> --file Dockerfile .
   ```

4. **Restore the Dockerfile** to its original `FROM` line after the build completes (whether it succeeded or failed). The Dockerfile in the repo must always reference the upstream image, not the ACR-specific one.

If the base image doesn't exist in ACR and Docker Hub rate limits hit, try importing it first:
```bash
az acr import --name <acr_name> --source docker.io/library/<image>:<tag> --image <image>:<tag> --force
```

### Step 5 — Verify image in ACR

```bash
az acr repository show-tags --name <acr_name> --repository <image_name> -o table
```

Confirm the version tag appears in the list.

### Step 6 — Update the Container App

```bash
az containerapp update \
  --name <container_app> \
  --resource-group <resource_group> \
  --image <LOGIN_SERVER>/<image_name>:<version>
```

### Step 7 — Verify deployment

Run these three checks:

1. **Image in use:**
   ```bash
   az containerapp show --name <container_app> --resource-group <resource_group> --query "properties.template.containers[0].image" -o tsv
   ```
   Confirm it matches `<LOGIN_SERVER>/<image_name>:<version>`.

2. **Active revision:**
   ```bash
   az containerapp revision list --name <container_app> --resource-group <resource_group> --query "[-1].{name:name, active:properties.active, replicas:properties.replicas, trafficWeight:properties.trafficWeight, createdTime:properties.createdTime}" -o table
   ```
   Confirm `Active=True` and `TrafficWeight=100`.

3. **Image exists in ACR:**
   ```bash
   az acr repository show-tags --name <acr_name> --repository <image_name> -o table
   ```

### Step 8 — Final summary

Present a summary to the user in this format:

```
## Resumen de despliegue

- **Imagen**: <image_name>:<version>
- **ACR**: <acr_name> (<LOGIN_SERVER>)
- **Digest**: <sha256 digest from build output>
- **Container App**: <container_app>
- **Revisión activa**: <revision name>
- **Réplicas**: <count>
- **Tráfico**: <weight>%
- **Estado**: ✅ Desplegado exitosamente / ❌ Error (con detalle)
```

## Error handling

- If any `az` command fails, show the error and suggest potential fixes (wrong subscription, permissions, resource not found)
- If Docker Hub rate limit is hit, use the ACR-cached base image strategy described in Step 4 Option B
- If the Container App update fails, check if the ACR credentials are configured in the Container App
- Always restore the Dockerfile if it was temporarily modified
