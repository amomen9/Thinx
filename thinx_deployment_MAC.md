# Deploying Thinx on macOS with Docker

The macOS counterpart of **thinx_deployment.md**. I wrote it on 2026-09-24 from the Linux guide,
changing only what actually differs; the stack, the **.env** variables, the ports and the first
login are identical on both systems. Every box can be pasted as it stands.

Two things about macOS shape the whole file:

- Docker does not run on macOS directly. Docker Desktop runs a Linux virtual machine, so the
  memory and disk that matter are the ones given to that virtual machine, not the ones the Mac has.
- On Apple Silicon the database image is emulated. **franzinc/agraph:v8.0.1** is published for
  **linux/amd64** only, which is why the compose file pins **platform: linux/amd64** for that
  service. It works through Rosetta, and it is slower than on Linux. The backend, the interface and
  Ollama all have native arm64 images and are unaffected.

## What the stack provides

| Service | Container | Reachable at | Purpose |
|---|---|---|---|
| Web interface | vue_ui | http://localhost:8080 | What researchers use |
| API | flask_api | http://localhost:5000 | Flask backend |
| Database | agraph_db | http://localhost:10035 | AllegroGraph triple store, admin UI |
| AI | ollama_service | http://localhost:11434 | Local model for the Smart Mapper |

All four bind to **127.0.0.1** by default, so nothing is exposed to the network until we decide it
should be. See step 4.

---

## Step 1 - Install Docker Desktop

The Linux installer script does not work here, and there is no **systemctl**, **usermod** or
**newgrp** on macOS.

    brew install --cask docker-desktop || brew install --cask docker
    open -a Docker          # wait until the whale in the menu bar reports "running"
    docker --version && docker compose version

Without Homebrew, download Docker Desktop from docker.com and install it the usual way.

On Apple Silicon, Rosetta is needed for the database image:

    softwareupdate --install-rosetta --agree-to-license

Then open Docker Desktop, Settings, General, and switch on **Use Rosetta for x86_64/amd64
emulation**.

## Step 2 - Give the virtual machine enough memory, and check the ports

**free** and **ss** do not exist on macOS, and the Mac's own totals are not the limit that matters.

    sysctl -n hw.memsize | awk '{printf "Mac RAM:       %.0f GB\n", $1/1073741824}'
    docker info --format 'Docker VM RAM: {{.MemTotal}} bytes'
    df -h ~
    lsof -nP -iTCP:5000,8080,10035,11434 -sTCP:LISTEN || echo "All ports free"

In Docker Desktop, Settings, Resources, set the memory to at least **8 GB** for the **no-ai**
profile and **16 GB** for the full profile with the AI model. Disk: about 5 GB for **no-ai** and
about 15 GB for the full profile, inside the virtual machine's disk image.

## Step 3 - Get the code

Set the BRANCH variable value with the GitHub branch name ("Agata", "Loes", "Emre", "Ali" - case
sensitive). Git comes with the Xcode command line tools.

    BRANCH=
    command -v git || xcode-select --install
    git clone -b $BRANCH https://github.com/amomen9/Thinx.git ~/thinx
    cd ~/thinx && git log -1 --oneline

The code goes in the home directory, not in **/opt**. Docker Desktop shares **/Users**,
**/Volumes**, **/private** and **/tmp** with its virtual machine and nothing else, and this stack
bind-mounts the project directory into the containers, so a checkout under **/opt** would fail to
mount unless that path is added by hand in Settings, Resources, File sharing.

The first line of that log should be the security hardening commit. If it says
**Update push_to_allegrograph.py** instead, the branch has not been pushed yet and the clone holds
upstream code: copy the working tree across instead of cloning, or push the branch first.

## Step 4 - Decide how the platform will be reached

**Path A (recommended - works best for local).** The platform is used on the Mac itself, or from
another machine through an SSH tunnel. Nothing is published to the network and no extra
configuration is needed: the default **BIND_HOST=127.0.0.1** already does this.

**Path B.** Other machines open it by the Mac's IP address. This exposes the interface and the API
to the local network, so it is only for a network we trust, and TLS belongs in front of it before
anyone outside the team uses it. The address comes from:

    ipconfig getifaddr en0 || ipconfig getifaddr en1

Then three variables in step 5 have to change:

    BIND_HOST=0.0.0.0
    VITE_API_URL=http://192.168.1.50:5000      # the Mac's IP
    CORS_ORIGINS=http://192.168.1.50:8080      # how the browser addresses it

Remote access also needs Remote Login switched on in System Settings, General, Sharing, if the SSH
tunnel of Path A is used from another machine.

The database and the AI service stay on 127.0.0.1 in both paths. There is no reason for anything
else to reach them directly.

## Step 5 - Create .env

**SECRET_KEY** and **AGRAPH_SUPER_PASSWORD** are required; the stack refuses to start without them.

macOS ships BSD sed, which needs an explicit empty backup suffix after **-i**. The Linux form of
these two lines fails here with "invalid command code".

    cd ~/thinx
    cp .env.example .env
    sed -i '' "s|^SECRET_KEY=.*|SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))')|" .env
    sed -i '' "s|^AGRAPH_SUPER_PASSWORD=.*|AGRAPH_SUPER_PASSWORD=$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 24)|" .env
    chmod 600 .env
    grep -E '^(COMPOSE_PROFILES|BIND_HOST|FLASK_ENV|VITE_API_URL|CORS_ORIGINS)=' .env
    echo "Database password: $(grep '^AGRAPH_SUPER_PASSWORD=' .env | cut -d= -f2)"

That database password has to be written down; it is typed into the interface once, in step 10. It
is applied when the database volume is first created, so changing it in **.env** later does not
change the database.

Set **COMPOSE_PROFILES=no-ai** in **.env** if the virtual machine has less than about 16 GB.
Everything works except the AI Smart Mapper.

## Step 6 - Build and start

    cd ~/thinx
    ./start.sh              # or: docker compose --profile full up -d --build
    docker compose ps

The first build takes about 5 to 15 minutes: it installs the Python and Node dependencies. Docker
Desktop must be running before this, otherwise the commands fail with "Cannot connect to the Docker
daemon".

## Step 7 - Wait for startup and verify

    cd ~/thinx
    echo -n "Waiting"
    until curl -sf -o /dev/null http://localhost:10035/ && curl -sf -o /dev/null http://localhost:5000/api/health; do
      sleep 5; echo -n "."
    done; echo " up"

    curl -s http://localhost:5000/api/health; echo
    curl -s http://localhost:5000/api/session; echo      # setup_required: true on a fresh install
    curl -s -o /dev/null -w "Frontend: HTTP %{http_code}\n" http://localhost:8080
    set -a; . ./.env; set +a
    curl -s -o /dev/null -w "DB login: HTTP %{http_code} (200 = password OK)\n" \
      -u "admin:$AGRAPH_SUPER_PASSWORD" http://localhost:10035/repositories

    # The API is closed without a session, so this one SHOULD say 401:
    curl -s -o /dev/null -w "Unauthenticated /api/connections: HTTP %{http_code} (401 expected)\n" \
      http://localhost:5000/api/connections

The database takes longer to answer here than on Linux, because it is emulated. If the wait loop is
still running after about 5 minutes, press Ctrl+C and look at **docker compose logs --tail=50**.

## Step 8 - Pull the AI model (full profile only)

```shell
docker exec ollama_service ollama pull llama3     # ~4.7 GB, the model the API asks for by default

# Other models:
# Lighter:
# docker exec -it ollama_service ollama pull phi3

# Another Heavy model:
# docker exec -it ollama_service ollama pull phi4

# Get list of installed models:
docker exec ollama_service ollama list

```

Any other Ollama model works too; pull it here, then it can be picked in the interface.

A container on macOS has no access to the Mac's GPU, so a model running in **ollama_service** uses
the CPU only and is noticeably slower than the same model on a Linux box with a GPU. A lighter model
such as **phi3** is the easy answer. The faster alternative is a native Ollama, which does use
Metal:

    brew install ollama
    ollama serve            # leave running, or: brew services start ollama
    ollama pull llama3

To point the stack at it, run the **no-ai** profile and add one line to the backend service in
**docker-compose.yml**:

    - OLLAMA_HOST=http://host.docker.internal:11434

## Step 9 - Open the interface

- **Path A**, on the Mac itself: open http://localhost:8080
- **Path A**, from another machine: run the tunnel below, keep it open, then browse to
  http://localhost:8080
- **Path B**: open http://mac-ip:8080

The tunnel for the second case, run on the other machine and left open:

    ssh -N -L 8080:localhost:8080 -L 5000:localhost:5000 -L 10035:localhost:10035 user@mac

A Mac has no reserved port ranges, so 10035 can be mapped straight through. From a Windows machine
that is not true: 10035 usually falls inside a range reserved for Hyper-V, so map the database to
11035 instead and open http://localhost:11035 for the admin interface. Keep **8080** and **5000**
identical on both sides in every case: the API only accepts the browser origins listed in
**CORS_ORIGINS**, and the interface calls the API at **VITE_API_URL**.

Then, in the interface:

- **Register.** The first account created becomes the administrator. Minimum password length is 12.
   Set **ALLOW_REGISTRATION=false** in **.env** afterwards if only administrators should add accounts.

## Step 10 - Connect the interface to the database

- **Log in**, open the connection manager and add a connection

1. **Local connection**:

For local connection:

| Field | Value |
|---|---|
| Host | **allegrograph** (not localhost: the backend reaches the database over the Docker network) |
| Port | **10035** |
| Repository | **humantrafficking** |
| Username | **admin** |
| Password | the **AGRAPH_SUPER_PASSWORD** from step 5 |

2. **Remote connection**:

We'll get back to the remote connections later.

- For any connection, tick **Test connection before saving**, save, then activate the connection.
   The repository is created automatically on first connect.

## Step 11 (optional) - Load the HDS ontology

Run this after step 10, once the repository exists.

    cd ~/thinx
    set -a; . ./.env; set +a
    curl -s -w "HTTP %{http_code} (2xx = loaded)\n" -u "admin:$AGRAPH_SUPER_PASSWORD" \
      -H "Content-Type: text/turtle" --data-binary @hds_cdm.ttl \
      http://localhost:10035/repositories/humantrafficking/statements

For test data, upload the files in **Mock data/** through the workflow in the interface.

---

## Day-to-day commands

    cd ~/thinx
    docker compose logs -f backend      # services: allegrograph, ollama, backend, frontend
    docker compose stop                 # pause, keeps data
    docker compose start
    docker compose down                 # removes containers, keeps data
    # docker compose down -v            # DELETES all data, including the database and accounts

    # Update to the latest code on this branch
    git pull && docker compose up -d --build

    # Back up the database and the accounts and connections
    docker compose stop allegrograph backend
    for v in agraph_data_volume backend_data_volume; do
      docker run --rm -v $v:/data -v "$PWD":/backup alpine tar czf /backup/$v-$(date +%F).tgz -C /data .
    done
    docker compose start allegrograph backend

Back up **.env** as well, somewhere other than the Mac itself. Without **AGRAPH_SUPER_PASSWORD** a
restored database volume cannot be opened. Quitting Docker Desktop stops every container, so the
stack has to be started again after a reboot or a logout.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| "Cannot connect to the Docker daemon" | Docker Desktop is not running. **open -a Docker** and wait for the whale icon. |
| sed reports "invalid command code" or "extra characters at the end of the command" | The Linux form of **sed -i** was used. BSD sed needs **sed -i ''**. Step 5. |
| "mounts denied" or an empty **/workspace** in the container | The checkout is outside the paths Docker Desktop shares. Move it under the home directory, or add the path in Settings, Resources, File sharing. Step 3. |
| The database container never becomes healthy on Apple Silicon | Rosetta is off, or the virtual machine has too little memory. Step 1 and step 2. |
| Everything is very slow | The database runs emulated on Apple Silicon and the AI model runs on the CPU. Give the virtual machine more memory, use a lighter model, or run Ollama natively. Step 8. |
| Compose exits with "set AGRAPH_SUPER_PASSWORD in .env" | **.env** is missing or incomplete. Step 5. |
| Everything answers 401 in the browser | No session. Log in again; if it repeats, the browser origin is not in **CORS_ORIGINS**, or **VITE_API_URL** does not match how the API is reached. |
| "Network Error" in the interface | Same cause as above. Recheck step 4 and step 5, then **docker compose up -d**. |
| "Blocked request. This host is not allowed" | The Vite dev server rejects unknown hostnames. Use the IP address or the SSH tunnel. |
| Connection test fails in the interface | The host must be **allegrograph**, and the password the one from step 5. |
| AI features unavailable | Model not pulled (step 8), or the profile is **no-ai**. |

---

## What differs from the Linux guide

Everything not listed here is identical, including the **.env** variables, the ports, the first
login, steps 6, 7, 10 and 11, and the day-to-day commands.

| Step | On Linux | On macOS |
|---|---|---|
| 1 | get.docker.com script, systemctl, usermod | Docker Desktop, plus Rosetta on Apple Silicon |
| 2 | free, ss, df on the host | sysctl and lsof, and the limits come from Docker Desktop's virtual machine |
| 3 | apt-get, clone into **/opt/thinx** | Xcode command line tools, clone into **~/thinx** because Docker Desktop only shares a few paths |
| 5 | **sed -i "s|...|"** | **sed -i '' "s|...|"** |
| 8 | GPU available to the container | CPU only in the container; native Ollama for Metal |
| 9 | Tunnel maps 10035 straight through | The same, the Windows reserved range only applies when tunnelling from Windows |
| Database | Runs natively | Emulated amd64, so slower |

The appendix of **thinx_deployment.md** records what a deployment of upstream **main** needed before
branch "Ali" fixed it. That history applies to both systems and is not repeated here.
