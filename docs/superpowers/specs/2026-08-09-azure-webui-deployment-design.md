# Azure WebUI deployment design

## Goal

Publish the Task 13 Harness WebUI for assessment without disrupting the
existing CampusHub web application on the same Azure VM.

## Existing environment

- VM: `campushub-server` in East Asia.
- Existing `deploy-frontend-1` publishes host port 80.
- No host Nginx service is installed.
- Host port 8000 is unused.
- Azure-assigned DNS name:
  `campushub-nju.eastasia.cloudapp.azure.com`.

## Architecture

Run the Harness image as a new Docker container named `harness-webui` with the
host-to-container mapping `8000:8000`. It runs independently of the existing
`deploy-*` containers and persists Harness state in a dedicated `/opt/harness`
directory on the VM. Azure Network Security Group rules expose TCP 8000.

The public assessment URL is:

`http://campushub-nju.eastasia.cloudapp.azure.com:8000`

The existing site retains sole ownership of port 80. The Harness CLI remains
available by overriding the image's default WebUI command.

## Security and operations

- No API keys are built into the image. Any provider credential is supplied at
  runtime through the VM environment or a secret mechanism.
- Only TCP 8000 is added to Azure ingress; SSH 22 and the existing 80 rule are
  unchanged.
- The deployment uses a dedicated container name, directory, and Docker volume
  mount, avoiding existing application state.
- Rollback stops and removes only `harness-webui` and leaves `deploy-*`
  containers untouched.

## Acceptance criteria

- The existing service remains reachable on port 80.
- The Harness root page responds on port 8000 locally and via its Azure DNS
  URL.
- Restarting `harness-webui` preserves its `.harness` state.
