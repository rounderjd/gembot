# Gembot Docker

This project runs the gembot application in a Docker container.

## Prerequisites

*   Docker
*   Docker Compose
*   Tailscale (running on the host machine)

## Setup

1.  **Copy Application Files:**

    Copy the contents of `/home/ubuntu/gemini-distributed-agent` into this directory (`/home/ubuntu/gembot-docker`).

2.  **Configure Environment:**

    Create a `.env` file from the example:

    ```bash
    cp .env.example .env
    ```

    Edit the `.env` file with your PostgreSQL connection details, using the Tailscale IP of your database server.

3.  **Build and Run:**

    ```bash
    docker-compose up --build -d
    ```

## Usage

*   **Web UI:** Access the web UI in your browser at `http://<your_host_ip>:<GEMBOT_PORT>`.
*   **CLI Menu:** Attach to the container to use the interactive CLI menu:

    ```bash
    docker exec -it gembot bash
    ```

    Then, run the gembot menu:

    ```bash
    /app/gembot.sh
    ```

## Tailscale Networking

This setup uses `network_mode: "host"` in the `docker-compose.yml`. This means the container shares the host's network stack, allowing it to connect to your PostgreSQL server over the Tailscale network.
