# Deploying Thinx on a Linux machine with Docker

Step-by-step deployment. I wrote this on 2026-09-18 for upstream **main** (commit 0b4cd0d) and
updated it on 2026-09-20 for this branch. Every box can be pasted as it stands.

Branch "Ali" fixes most of the traps we had to work around the first time. I have kept the steps
that are no longer needed at the end of this file, under **Appendix**, so the history of what was
wrong is not lost.

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

## Step 1 - Install Docker (skip if both commands already print a version)

    docker --version && docker compose version

    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh && exit 0
    sudo usermod -aG docker $USER
    sudo systemctl enable --now docker
    newgrp docker
    docker run --rm hello-world

## Step 2 - Check resources and ports

    free -h    # no-ai: 4 GB RAM minimum | full (with AI): 16 GB recommended
    df -h /    # no-ai: ~5 GB free       | full: ~15 GB free
    sudo ss -tlnp | grep -E ':(5000|8080|10035|11434)\b' || echo "All ports free"

## Step 3 - Get the code
Set the BRANCH variable value with your GitHub branch name ("Agata", "Loes", "Emre", "Ali" - case sensitive)

    BRANCH=
	command -v git || sudo apt-get install -y git
    sudo mkdir -p /opt/thinx && sudo chown $USER:$USER /opt/thinx
    git clone -b $BRANCH https://github.com/amomen9/Thinx.git /opt/thinx
    cd /opt/thinx && git log -1 --oneline

The first line of that log should be the security hardening commit. If it says
**Update push_to_allegrograph.py** instead, the branch has not been pushed yet and the clone holds
upstream code: copy the working tree across instead of cloning, or push the branch first.

## Step 4 - Decide how the platform will be reached

**Path A (recommended - works best for local).** The platform is used on the machine itself, or from a laptop through an
SSH tunnel. Nothing is published to the network and no extra configuration is needed: the default
**BIND_HOST=127.0.0.1** already does this.

**Path B.** Other machines open it by the server's IP address. This exposes the interface and the API
to the local network, so it is only for a network we trust, and TLS belongs in front of it before
anyone outside the team uses it. Two variables in step 5 have to change:

    BIND_HOST=0.0.0.0
    VITE_API_URL=http://192.168.1.50:5000      # the server's IP
    CORS_ORIGINS=http://192.168.1.50:8080      # how the browser addresses it

The database and the AI service stay on 127.0.0.1 in both paths. There is no reason for anything
else to reach them directly.

## Step 5 - Create .env

**SECRET_KEY** and **AGRAPH_SUPER_PASSWORD** are required; the stack refuses to start without them.

    cd /opt/thinx
    cp .env.example .env
    sed -i "s|^SECRET_KEY=.*|SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))')|" .env
    sed -i "s|^AGRAPH_SUPER_PASSWORD=.*|AGRAPH_SUPER_PASSWORD=$(tr -dc 'A-Za-z0-9' </dev/urandom | head -c 24)|" .env
    chmod 600 .env
    grep -E '^(COMPOSE_PROFILES|BIND_HOST|FLASK_ENV|VITE_API_URL|CORS_ORIGINS)=' .env
    echo "Database password: $(grep '^AGRAPH_SUPER_PASSWORD=' .env | cut -d= -f2)"

That database password has to be written down; it is typed into the interface once, in step 9. It
is applied when the database volume is first created, so changing it in **.env** later does not
change the database.

Set **COMPOSE_PROFILES=no-ai** in **.env** if the machine has less than about 16 GB of RAM. Everything
works except the AI Smart Mapper.

## Step 6 - Build and start

    cd /opt/thinx
    ./start.sh              # or: docker compose --profile full up -d --build
    docker compose ps

The first build takes about 5 to 15 minutes: it installs the Python and Node dependencies.

## Step 7 - Wait for startup and verify

    cd /opt/thinx
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

If the wait loop is still running after about 5 minutes, press Ctrl+C and look at
**docker compose logs --tail=50**.

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

Any other Ollama model works too; pull it here, then you can pick it in the interface.

## Step 9 - Open the interface

- **Path A**, on the machine itself: open http://localhost:8080
- **Path A**, from a laptop: run the tunnel below, keep it open, then browse to http://localhost:8080
- **Path B**: open http://server-ip:8080

The tunnel for the second case, run on the laptop and left open:

    ssh -N -L 8080:localhost:8080 -L 5000:localhost:5000 -L 11035:localhost:10035 user@server

On Windows, port 10035 usually cannot be used locally because it falls inside a range Windows
reserves for Hyper-V, which is why the tunnel above maps the database to **11035** instead. The
database admin UI is then http://localhost:11035. Keep **8080** and **5000** identical on both sides:
the API only accepts the browser origins listed in **CORS_ORIGINS**, and the interface calls the API
at **VITE_API_URL**.

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

- Make sure that for any connection you tick **Test connection before saving**, save, then activate the connection. The repository is
   created automatically on first connect.


## Step 11 (optional) - Load the HDS ontology

Run this after step 10, once the repository exists.

    cd /opt/thinx
    set -a; . ./.env; set +a
    curl -s -w "HTTP %{http_code} (2xx = loaded)\n" -u "admin:$AGRAPH_SUPER_PASSWORD" \
      -H "Content-Type: text/turtle" --data-binary @hds_cdm.ttl \
      http://localhost:10035/repositories/humantrafficking/statements

For test data, upload the files in **Mock data/** through the workflow in the interface.

---

## Day-to-day commands

    cd /opt/thinx
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

Back up **.env** as well, somewhere other than the machine itself. Without
**AGRAPH_SUPER_PASSWORD** a restored database volume cannot be opened.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| Compose exits with "set AGRAPH_SUPER_PASSWORD in .env" | **.env** is missing or incomplete. Step 5. |
| Everything answers 401 in the browser | No session. Log in again; if it repeats, the browser origin is not in **CORS_ORIGINS**, or **VITE_API_URL** does not match how the API is reached. |
| "Network Error" in the interface | Same cause as above. Recheck step 4 and step 5, then **docker compose up -d**. |
| "Blocked request. This host is not allowed" | The Vite dev server rejects unknown hostnames. Use the IP address or the SSH tunnel. |
| Connection test fails in the interface | The host must be **allegrograph**, and the password the one from step 5. |
| AI features unavailable | Model not pulled (step 8), or the profile is **no-ai**. |
| Tunnel says "bind: Permission denied" on Windows | The local port is in a Windows reserved range. Use another local port, as with 11035 above. **netsh interface ipv4 show excludedportrange protocol=tcp** lists them. |

---

## Appendix - what the original instructions had to patch on upstream main

Kept for reference. **None of this is needed on branch Ali**; it records what our deployment of
upstream **main** (commit 0b4cd0d) required on 2026-09-18, and it is why we made these fixes.

**1. The database password did not match the documentation.** The compose file hardcoded
**admin1233** while the backend and every document used **admin123**:

    sed -i 's/AGRAPH_SUPER_PASSWORD=admin1233/AGRAPH_SUPER_PASSWORD=${AGRAPH_SUPER_PASSWORD:-admin123}/' docker-compose.yml

Now: the password comes from **.env** and the stack refuses to start without one.

**2. Every port was published on all interfaces**, and Docker writes its own firewall rules, so a
host firewall did not stop it:

    sed -i -E 's/- "([0-9]+:[0-9]+)"/- "127.0.0.1:\1"/' docker-compose.yml

Now: **BIND_HOST** defaults to 127.0.0.1.

**3. The allowed browser origins were hardcoded in the backend**, so opening the interface by server
IP failed with a CORS error that nothing explained:

    sed -i "s|\"http://localhost:8080\"]|\"http://localhost:8080\", \"http://$SERVER_IP:8080\"]|" backend/app.py

Now: **CORS_ORIGINS** in **.env**.

**4. start.sh started nothing at all**, because every service sits behind a Compose profile and the
script passed none, and **check-setup.sh** looked for the retired **docker-compose** binary and for
port 80 instead of 8080. Both were rewritten.

**5. The interface was documented as port 80** but published on 8080.

**6. Flask ran in debug mode**, published on all interfaces, with a Werkzeug version carrying a
high-severity remote-code-execution advisory. Now: production by default.

**7. A fresh installation created an admin account with the password admin.** Now: the user store
starts empty and the first account registered becomes the administrator.

See **SECURITY_FIXES.md** for the full list of what this branch changed and what is still open.
