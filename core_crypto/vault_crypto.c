#include <sodium.h>
#include <string.h>

// Initialize the libsodium library. This function must be called before any cryptographic operations.
int initialize_engine() {
    if (sodium_init() < 0) {
        return -1;
    }
    return 0;
}

// Derive the master key from the password using Argon2id, a memory-hard key derivation function.
// This provides protection against brute-force attacks through computational cost.
int derive_master_key(const char* password, char* output_hash) {
    if (crypto_pwhash_str(
            output_hash,
            password,
            strlen(password),
            crypto_pwhash_OPSLIMIT_INTERACTIVE,
            crypto_pwhash_MEMLIMIT_INTERACTIVE
        ) != 0) {
        return -1;
    }
    return 0;
}

// Encrypt credential data using XSalsa20-Poly1305, which provides both confidentiality and authenticity.
// The nonce must be unique for each encryption operation with the same key.
int encrypt_credential(const unsigned char* plaintext, unsigned long long plaintext_len, 
                      const unsigned char* nonce, const unsigned char* key, 
                      unsigned char* encrypted_output) {
    return crypto_secretbox_easy(encrypted_output, plaintext, plaintext_len, nonce, key);
}

// Decrypt and verify the authenticity of encrypted credentials using XSalsa20-Poly1305.
// The operation fails if the authentication tag does not match, indicating possible tampering.
int decrypt_credential(const unsigned char* encrypted, unsigned long long encrypted_len, 
                         const unsigned char* nonce, const unsigned char* key, 
                         unsigned char* output_message) {
    return crypto_secretbox_open_easy(output_message, encrypted, encrypted_len, nonce, key);
}