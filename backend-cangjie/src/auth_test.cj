package zhiwei

import std.fs.*
import std.unittest.*
import std.unittest.testmacro.*
import stdx.encoding.json.*

func vectors(): JsonObject {
    return (JsonValue.fromStr(String.fromUtf8(File.readFrom("tests/auth_vectors.json"))) as JsonObject).getOrThrow()
}
func vector(data: JsonObject, name: String): String { (data[name] as JsonString).getOrThrow().getValue() }

@Test
class AuthenticationTest {
    @TestCase
    func pythonPasswordCompatibility() {
        let data = vectors()
        let password = vector(data, "password")
        let expected = vector(data, "encoded")
        @Expect(hashPassword(password, Array<UInt8>(16, { i => UInt8(i) })), expected)
        @Expect(verifyPassword(password, expected), true)
        @Expect(verifyPassword("wrong-password", expected), false)
        @Expect(verifyPassword(password, "pbkdf2_sha256$bad$bad"), false)
        @Expect(verifyPassword(password, "other$bad$bad"), false)
        @Expect(verifyPassword(password, ""), false)
        let first = hashPassword(password)
        let second = hashPassword(password)
        @Expect(first != second, true)
        @Expect(verifyPassword(password, first), true)
    }

    @TestCase
    func pythonTokensAndPasswordChanges() {
        let data = vectors()
        let secret = vector(data, "secret")
        let credential = vector(data, "encoded")
        let user = vector(data, "user_id")
        let token = vector(data, "token")
        @Expect(credentialTag(credential, secret), vector(data, "tag"))
        @Expect(readToken(token, secret, Some(credential)), Some(user))
        @Expect(readToken(token, secret, Some("changed")), None)
        @Expect(readToken(token, "wrong-secret", Some(credential)), None)
        @Expect(readToken(token + "x", secret, Some(credential)), None)
        @Expect(readToken("not.a.token", secret, Some(credential)), None)
        @Expect(readToken(createToken(user, secret, credential, unixNow() - 1), secret, Some(credential)), None)
        @Expect(readToken(createToken(user, secret, credential, unixNow() + 60), secret, Some(credential)), Some(user))
    }
}
