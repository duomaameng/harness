# Azure WebUI Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish the Harness WebUI at `http://campushub-nju.eastasia.cloudapp.azure.com:8000` without changing the existing CampusHub service on port 80.

**Architecture:** Deploy the already-built Task 13 Docker configuration from the isolated `codex/task-13-delivery` branch to a new `harness-webui` container. The container is bound only to host TCP 8000 and uses `/opt/harness` as its isolated persisted workspace; the existing `deploy-*` containers remain untouched.

**Tech Stack:** Azure VM (Ubuntu 24.04), Azure Network Security Group, Docker, FastAPI/Uvicorn, GitHub.

## Global Constraints

- Do not modify, restart, remove, or reconfigure `deploy-frontend-1`, `deploy-backend-1`, `deploy-db-1`, or host port 80.
- Use container name `harness-webui`, host port `8000`, and server directory `/opt/harness` only.
- Do not place API keys in Git, Dockerfiles, shell history, or command output.
- Deploy the committed `codex/task-13-delivery` branch from `https://github.com/duomaameng/harness.git`.
- The public check URL is `http://campushub-nju.eastasia.cloudapp.azure.com:8000`.

---

### Task 1: Publish the deployment branch and start the isolated WebUI container

**Files:**
- Create on VM: `/opt/harness/repo/` (Git checkout)
- Create on VM: `/opt/harness/workspace/` (persistent Harness repository and `.harness` state)
- Create on VM: Docker container `harness-webui`
- Modify: GitHub remote branch `codex/task-13-delivery`

**Interfaces:**
- Consumes: `Dockerfile` and `harness.api:app` in the committed Task 13 branch.
- Produces: local endpoint `http://127.0.0.1:8000/` served by the `harness-webui` container.

- [ ] **Step 1: Write the failing deployment check**

  On the VM, verify that no WebUI is already reachable on the reserved port:

  ```bash
  curl --fail --max-time 5 http://127.0.0.1:8000/
  ```

  Expected: non-zero exit because no process currently listens on port 8000.

- [ ] **Step 2: Run the failing deployment check and record the failure**

  Run the command from Step 1 before any deployment command. Preserve its
  connection-refused output in the deployment transcript.

- [ ] **Step 3: Publish and deploy the minimal container**

  From the isolated local worktree, publish the exact branch:

  ```powershell
  git push -u origin codex/task-13-delivery
  ```

  Then on the VM, run exactly:

  ```bash
  sudo mkdir -p /opt/harness
  sudo chown "$USER":"$USER" /opt/harness
  git clone --branch codex/task-13-delivery --single-branch https://github.com/duomaameng/harness.git /opt/harness/repo
  mkdir -p /opt/harness/workspace
  docker build -t context-aware-harness:task13 /opt/harness/repo
  docker run -d --name harness-webui --restart unless-stopped -p 8000:8000 -v /opt/harness/workspace:/workspace context-aware-harness:task13
  ```

- [ ] **Step 4: Run the passing local deployment check**

  ```bash
  curl --fail --max-time 10 http://127.0.0.1:8000/
  docker ps --filter name=^/harness-webui$ --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
  ```

  Expected: `curl` exits 0 and the container reports `0.0.0.0:8000->8000/tcp`.

- [ ] **Step 5: Commit repository documentation only if deployment commands changed**

  No source change is expected. If a deployment command needs correction,
  update `README.md` in the local Task 13 worktree and commit only that file:

  ```bash
  git add README.md
  git commit -m "docs: clarify Azure WebUI deployment"
  git push
  ```

### Task 2: Expose TCP 8000 in Azure and verify the public URL

**Files:**
- Modify: Azure Network Security Group inbound rule for `campushub-server`

**Interfaces:**
- Consumes: Task 1 local endpoint on VM TCP 8000.
- Produces: public endpoint `http://campushub-nju.eastasia.cloudapp.azure.com:8000/`.

- [ ] **Step 1: Write the failing public reachability check**

  From the local Windows terminal, run:

  ```powershell
  curl.exe --fail --max-time 10 http://campushub-nju.eastasia.cloudapp.azure.com:8000/
  ```

  Expected: non-zero exit before the Azure TCP 8000 inbound rule exists.

- [ ] **Step 2: Run the failing public reachability check and record the failure**

  Run the command from Step 1 before changing the network rule. Preserve the
  timeout or connection-refused output in the deployment transcript.

- [ ] **Step 3: Add the minimal Azure ingress rule**

  In Azure Portal, open `campushub-server` > **网络** > the linked Network
  Security Group > **入站安全规则** > **创建**. Set:

  ```text
  Source: Any
  Source port ranges: *
  Destination: Any
  Service: Custom
  Destination port ranges: 8000
  Protocol: TCP
  Action: Allow
  Priority: 310
  Name: allow-harness-webui-8000
  ```

  Create the rule without changing the existing SSH or HTTP rules.

- [ ] **Step 4: Run the passing public reachability check**

  ```powershell
  curl.exe --fail --max-time 20 http://campushub-nju.eastasia.cloudapp.azure.com:8000/
  Start-Process 'http://campushub-nju.eastasia.cloudapp.azure.com:8000'
  ```

  Expected: `curl.exe` exits 0 and the browser displays the Harness WebUI.

- [ ] **Step 5: Commit repository documentation only if the public URL differs**

  If the URL differs from the global constraint, update the Docker section of
  `README.md`, commit it, and push the branch:

  ```bash
  git add README.md
  git commit -m "docs: publish WebUI URL"
  git push
  ```

### Task 3: Verify persistence and document safe rollback

**Files:**
- Modify: `/opt/harness/workspace/.harness/` on VM (runtime state only)
- Modify: `README.md` only if a verified runtime detail differs

**Interfaces:**
- Consumes: running `harness-webui` container and persistent workspace from Task 1.
- Produces: verified restart resilience and a container-scoped rollback command.

- [ ] **Step 1: Write the failing persistence check**

  On the VM, stop the container and verify the endpoint is unavailable:

  ```bash
  docker stop harness-webui
  curl --fail --max-time 5 http://127.0.0.1:8000/
  ```

  Expected: `curl` exits non-zero while the container is stopped.

- [ ] **Step 2: Run the failing persistence check and record the failure**

  Run both commands from Step 1. Do not stop or modify any `deploy-*` container.

- [ ] **Step 3: Restart only the Harness container**

  ```bash
  docker start harness-webui
  ```

- [ ] **Step 4: Run the passing persistence and isolation checks**

  ```bash
  curl --fail --max-time 20 http://127.0.0.1:8000/
  docker ps --filter name=^/deploy-frontend-1$ --format '{{.Names}} {{.Status}}'
  ```

  Expected: the Harness endpoint succeeds and `deploy-frontend-1` remains running.

- [ ] **Step 5: Commit repository documentation only if rollback changed**

  The rollback command is intentionally container-scoped:

  ```bash
  docker stop harness-webui
  docker rm harness-webui
  ```

  If documentation needs updating after the verified deployment, commit only
  the relevant README change:

  ```bash
  git add README.md
  git commit -m "docs: document Harness WebUI rollback"
  git push
  ```
