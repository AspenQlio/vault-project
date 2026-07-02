# Vault - Hybrid Zero-Knowledge Password Manager

Vault is a robust, self-hosted, multidisciplinary password manager designed with a **Zero-Knowledge Architecture**. It features a native Python client (built with CustomTkinter), a high-performance C cryptographic core using Libsodium, a FastAPI backend service, and a cloud-hosted PostgreSQL database.

## 󰌾 Security Architecture & Design

Vault operates under a strict **Zero-Knowledge** philosophy. Your master password and plaintext credentials never leave your local machine.

* **Client-Side Encryption:** All cryptographic operations (encryption and decryption) are executed locally by a compiled C library (`libvault_crypto.so`) linking directly to `libsodium`.
* **Key Derivation:** The master password is run through local SHA-256 hashing routines with unique salts to derive an authentication hash (sent to the server) and a separate symmetric encryption key (kept strictly in volatile memory).
* **Blind Cloud Storage:** The cloud database (Neon PostgreSQL) only stores blind data (`user_id`, `nonce_hex`, and `encrypted_data_hex`). The hosting server and database provider are entirely blind to the contents, service names, usernames, or passwords being stored.

##  Features

* **Hybrid Storage Flow:** Full control over credential placement. Save items strictly offline in a local SQLite database or securely synchronize specific records to the cloud.
* **Granular Per-Item Sync:** Native individual synchronization directly within credential display cards, protected by explicit state confirmation prompts.
* **Automatic Multi-device Fetch:** Intelligent synchronization upon successful authentication. If a new or wiped device logs into an account, cloud records are automatically downloaded and safely populated into the local database without creating duplicates.
* **Dynamic Password Generator:** In-app cryptographically secure generation using adjustable length parameters (8–32 characters) along with granular toggles for uppercase characters, numbers, and special symbols.
* **Session Control & Hardening:** Includes a global 60-second inactivity auto-lock system that clears sensitive decryption keys from memory, alongside automatic 10-second clipboard clearing routines to mitigate memory-scraping attacks.
* **Complete Local Re-Encryption:** In-app mechanism to change your Master Password. The engine handles full decryption of the offline database in memory, applies a new key structure, redistributes updated nonce sequences, and securely updates the authentication state across the network API.

##  Project Structure

`vault-project/
├── client/
│   ├── main.py              # CustomTkinter GUI application & logic flow
│   └── vault_local.db       # Client-side SQLite tracking schema
├── server/
│   └── main.py              # FastAPI cloud router architecture
├── core_crypto/
│   ├── libvault_crypto.c    # C implementation using Libsodium
│   └── libvault_crypto.so   # Compiled shared library module
└── vault.sh                 # Unified launch script`

## 🚀 Getting Started

### Prerequisites

Ensure your system has the following components installed:
* Python 3.x
* A standard C compiler (`gcc`)
* `libsodium` library development packages
* PostgreSQL instance or a remote cloud provider (e.g., Neon.tech)

### Installation & Setup

1.  **Clone the repository:**
    `git clone https://github.com/yourusername/vault-project.git
    cd vault-project`

2.  **Compile the Cryptographic Core Library:**
    Navigate to your crypto directory and compile the shared object binary:
    `gcc -shared -o core_crypto/libvault_crypto.so -fPIC core_crypto/libvault_crypto.c -lsodium`

3.  **Configure Environment Dependencies:**
    Set up your virtual environment and install required packages:
    `python -bin/venv venv
    source venv/bin/activate
    pip install customtkinter requests pydantic sqlalchemy psycopg2-binary fastapi uvicorn`

4.  **Set Up the Server Environment:**
    Define your remote database connection inside `server/main.py` or provision it via environment injections (`DATABASE_URL`). Deploy to your cloud infrastructure provider (e.g., Render) or run it locally:
    `uvicorn server.main:app --reload`

5.  **Execute the Application:**
    Launch the compiled binary wrapper interface:
    `./vault.sh`

## 󰈀 API Endpoints Reference

The FastAPI web engine exposes the following clean route configurations:
* `POST /api/register` - Registers a unique username tied to a cryptographically isolated auth hash.
* `POST /api/login` - Matches credential payloads to confirm local application instance access.
* `POST /api/sync` - Accepts a unified blind storage footprint payload.
* `GET /api/sync/{username}` - Returns cloud sync structures associated with an active identity mapping.
* `DELETE /api/sync/{username}/{cred_id}` - Purges targeted remote structures permanently.
* `PUT /api/update_hash` - Updates remote authentication indexes safely during local re-encryption workflows.

## 󰗘 License

This project is open-source software licensed under the MIT License.