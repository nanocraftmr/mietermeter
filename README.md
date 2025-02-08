# mietermeter
## Requirements

*   **Docker**
*   **Git**

## Quick Start

1.  **Clone repo:**
    ```bash
    git clone https://github.com/nanocraftmr/mietermeter
    cd mietermeter
    ```

2.  **Configure Environment Variables:**

    *   Edit the `.env` file to set your environment variables:

        ```
        HDGIP1="your_hdgip1_address"       # Replace with the actual HDG IP address for Brenner 1
        HDGIP2="your_hdgip2_address"       # Replace with the actual HDG IP address for Brenner 2
        SUPABASE_URL="your_supabase_url"  # Replace with your Supabase URL
        SUPABASE_KEY="your_supabase_key"  # Replace with your Supabase API key
        ```

3.  **Build the Docker Image:**

    ```bash
    docker-compose build
    ```

4.  **Start the Application:**

    ```bash
    docker-compose up -d
    ```

## Usage

*   **Starting the Application:**

    ```bash
    docker-compose up -d
    ```

*   **Stopping the Application:**

    ```bash
    docker-compose down
    ```

*   **Viewing Logs:**

    ```bash
    docker-compose logs hdg_app
    ```
    ```bash
    docker-compose logs -f hdg_app
    ```

## Troubleshooting

*   **Environment Variables Not Set:** If you see an error message about missing environment variables, double-check your `.env` file and make sure the keys and values are correct.  Also, ensure the .env file is in the same directory as `docker-compose.yml`. After changes restart the docker (docker-compose down, then up).

*   **Other Errors:** look up the docs or create an issue
