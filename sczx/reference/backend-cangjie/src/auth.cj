package zhiwei

import std.time.*
import stdx.encoding.base64.*
import stdx.encoding.hex.*
import stdx.encoding.json.*

foreign {
    func zw_random(output: CPointer<UInt8>, length: Int32): Int32
    func zw_pbkdf2(password: CPointer<UInt8>, length: Int32, salt: CPointer<UInt8>, saltLength: Int32, output: CPointer<UInt8>): Int32
    func zw_hmac(key: CPointer<UInt8>, keyLength: Int32, data: CPointer<UInt8>, dataLength: UInt64, output: CPointer<UInt8>): Int32
    func zw_equal(left: CPointer<UInt8>, right: CPointer<UInt8>, length: UInt64): Int32
}

public func randomBytes(length: Int32): Array<UInt8> {
    let bytes = Array<UInt8>(Int64(length), repeat: 0)
    unsafe {
        let output = acquireArrayRawData(bytes)
        try {
            if (zw_random(output.pointer, length) != 1) { throw Exception("安全随机数生成失败") }
        } finally { releaseArrayRawData(output) }
    }
    return bytes
}

public func newId(): String {
    let bytes = randomBytes(16)
    bytes[6] = (bytes[6] & 0x0f) | 0x40
    bytes[8] = (bytes[8] & 0x3f) | 0x80
    let hex = toHexString(bytes).toAsciiLower()
    return "${hex[..8]}-${hex[8..12]}-${hex[12..16]}-${hex[16..20]}-${hex[20..]}"
}

public func constantEqual(left: Array<UInt8>, right: Array<UInt8>): Bool {
    if (left.size != right.size) { return false }
    unsafe {
        let a = acquireArrayRawData(left)
        let b = acquireArrayRawData(right)
        try { return zw_equal(a.pointer, b.pointer, UInt64(left.size)) == 1 }
        finally { releaseArrayRawData(b); releaseArrayRawData(a) }
    }
}

func hmac256(secret: String, text: String): Array<UInt8> {
    let key = secret.toArray()
    let input = text.toArray()
    let output = Array<UInt8>(32, repeat: 0)
    unsafe {
        let k = acquireArrayRawData(key)
        let p = acquireArrayRawData(input)
        let result = acquireArrayRawData(output)
        try {
            if (zw_hmac(k.pointer, Int32(key.size), p.pointer, UInt64(input.size), result.pointer) != 1) {
                throw Exception("会话签名失败")
            }
        } finally { releaseArrayRawData(result); releaseArrayRawData(p); releaseArrayRawData(k) }
    }
    return output
}

func urlBase64(bytes: Array<UInt8>): String {
    return toBase64String(bytes).replace("+", "-").replace("/", "_")
}

func unpaddedBase64(bytes: Array<UInt8>): String {
    var value = urlBase64(bytes)
    while (value.endsWith("=")) { value = value[..value.size - 1] }
    return value
}

func decodeBase64(value: String): Array<UInt8> {
    var padded = value.replace("-", "+").replace("_", "/")
    while (padded.size % 4 != 0) { padded += "=" }
    return fromBase64String(padded).getOrThrow()
}

public func hashPassword(password: String): String { hashPassword(password, randomBytes(16)) }
public func hashPassword(password: String, salt: Array<UInt8>): String {
    let input = password.toArray()
    let output = Array<UInt8>(32, repeat: 0)
    unsafe {
        let p = acquireArrayRawData(input)
        let s = acquireArrayRawData(salt)
        let result = acquireArrayRawData(output)
        try {
            if (zw_pbkdf2(p.pointer, Int32(input.size), s.pointer, Int32(salt.size), result.pointer) != 1) {
                throw Exception("密码派生失败")
            }
        } finally { releaseArrayRawData(result); releaseArrayRawData(s); releaseArrayRawData(p) }
    }
    return "pbkdf2_sha256\$${urlBase64(salt)}\$${urlBase64(output)}"
}

public func verifyPassword(password: String, encoded: String): Bool {
    try {
        let parts = encoded.split("$")
        if (parts.size != 3 || parts[0] != "pbkdf2_sha256") { return false }
        let salt = decodeBase64(parts[1])
        if (salt.size != 16) { return false }
        let actual = hashPassword(password, salt)
        return constantEqual(actual.toArray(), encoded.toArray())
    } catch (_: Exception) { return false }
}

public func credentialTag(credential: String, secret: String): String {
    return toHexString(hmac256(secret, "credential:v1:${credential}")).toAsciiLower()
}

public func unixNow(): Int64 { DateTime.now().toUnixTimeStamp().toSeconds() }

public func createToken(userId: String, secret: String, credential: String, expiresAt: Int64): String {
    let claims = JsonObject()
    claims.put("sub", JsonString(userId))
    claims.put("exp", JsonInt(expiresAt))
    claims.put("credential", JsonString(credentialTag(credential, secret)))
    let payload = unpaddedBase64(claims.toString().toArray())
    return payload + "." + unpaddedBase64(hmac256(secret, payload))
}

public func readToken(token: String, secret: String, credential: Option<String>): Option<String> {
    try {
        if (token.size > 8192) { return None }
        let parts = token.split(".")
        if (parts.size != 2) { return None }
        let expected = unpaddedBase64(hmac256(secret, parts[0]))
        if (!constantEqual(parts[1].toArray(), expected.toArray())) { return None }
        let claims = (JsonValue.fromStr(String.fromUtf8(decodeBase64(parts[0]))) as JsonObject).getOrThrow()
        let expires = (claims["exp"] as JsonInt).getOrThrow().getValue()
        let userId = (claims["sub"] as JsonString).getOrThrow().getValue()
        if (expires <= unixNow() || userId.isEmpty() || userId.size > 36) { return None }
        if (let Some(value) <- credential) {
            let tag = (claims["credential"] as JsonString).getOrThrow().getValue()
            if (!constantEqual(tag.toArray(), credentialTag(value, secret).toArray())) { return None }
        }
        return Some(userId)
    } catch (_: Exception) { return None }
}
