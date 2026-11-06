package zhiwei

import std.unittest.*
import std.unittest.testmacro.*

@Test
class MediaStorageTest {
    @TestCase
    func exclusiveStorageAndDigest() {
        let path = "uploads/storage-test/" + newId() + ".bin"
        let bytes = "abc".toArray()
        @Expect(sha256(bytes), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
        writeMedia(path, bytes)
        try {
            var rejected = false
            try { writeMedia(path, "overwrite".toArray()) } catch (_: ApiError) { rejected = true }
            @Expect(rejected, true)
            @Expect(String.fromUtf8(readMedia(path)), "abc")
            var traversal = false
            try { writeMedia("uploads/../outside", bytes) } catch (_: ApiError) { traversal = true }
            @Expect(traversal, true)
        } finally { removeMedia(path) }
        var missing = false
        try { readMedia(path) } catch (_: ApiError) { missing = true }
        @Expect(missing, true)
    }
}
