# iot_devices.devices.LazyMesh.crypto

## Functions

| [`derive_routing_key`](#iot_devices.devices.LazyMesh.crypto.derive_routing_key)(→ bytes)   |    |
|--------------------------------------------------------------------------------------------|----|
| [`derive_crypto_key`](#iot_devices.devices.LazyMesh.crypto.derive_crypto_key)(→ bytes)     |    |
| [`aes_gcm_encrypt`](#iot_devices.devices.LazyMesh.crypto.aes_gcm_encrypt)(→ bytes)         |    |
| [`aes_gcm_decrypt`](#iot_devices.devices.LazyMesh.crypto.aes_gcm_decrypt)(→ bytes)         |    |

## Module Contents

### iot_devices.devices.LazyMesh.crypto.derive_routing_key(psk: bytes, hours_since_epoch: int) → bytes

### iot_devices.devices.LazyMesh.crypto.derive_crypto_key(psk: bytes, hours_since_epoch: int) → bytes

### iot_devices.devices.LazyMesh.crypto.aes_gcm_encrypt(key: bytes, payload: bytes, iv: bytes, tagLength: int) → bytes

### iot_devices.devices.LazyMesh.crypto.aes_gcm_decrypt(key: bytes, ciphertext: bytes, iv: bytes, tagLength: int) → bytes
