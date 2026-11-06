package zhiwei

import std.env.*
import stdx.encoding.hex.*
import stdx.encoding.base64.*
import stdx.encoding.json.*

foreign {
    func zw_sha256(data: CPointer<UInt8>, size: UInt64, output: CPointer<UInt8>): Int32
    func zw_media_write(root: CString, path: CString, data: CPointer<UInt8>, size: UInt64): Int32
    func zw_media_remove(root: CString, path: CString): Int32
}

func mediaRoot(): String { getVariable("CANGJIE_MEDIA_ROOT") ?? "media" }

public func sha256(data: Array<UInt8>): String {
    let output = Array<UInt8>(32, repeat: 0)
    unsafe {
        let source = acquireArrayRawData(data)
        let target = acquireArrayRawData(output)
        try {
            if (zw_sha256(source.pointer, UInt64(data.size), target.pointer) != 1) { throw IllegalStateException("摘要计算失败") }
        } finally { releaseArrayRawData(source); releaseArrayRawData(target) }
    }
    return toHexString(output).toAsciiLower()
}

func validStoragePath(path: String): Unit {
    if (!(path.startsWith("uploads/") || path.startsWith("reports/")) || path.contains("\u{0}") || path.contains("\\") || mediaRoot().contains("\u{0}")) {
        throw ApiError(422, "资源路径无效")
    }
    for (part in path.split("/")) { if (part.isEmpty() || part == "." || part == "..") { throw ApiError(422, "资源路径无效") } }
}

public func writeMedia(path: String, data: Array<UInt8>): Unit {
    validStoragePath(path)
    try (root = NativeString(mediaRoot()), name = NativeString(path)) {
        unsafe {
            let source = acquireArrayRawData(data)
            try {
                if (zw_media_write(root.value, name.value, source.pointer, UInt64(data.size)) != 0) { throw ApiError(503, "资源保存失败") }
            } finally { releaseArrayRawData(source) }
        }
    }
}

public func removeMedia(path: String): Unit {
    validStoragePath(path)
    try (root = NativeString(mediaRoot()), name = NativeString(path)) { unsafe { zw_media_remove(root.value, name.value) } }
}

public func readMedia(path: String): Array<UInt8> {
    validStoragePath(path)
    try (file = MediaFile(mediaRoot(), path)) {
        if (file.length <= 0 || file.length > 64 * 1024 * 1024) { throw ApiError(422, "图片文件大小无效") }
        let result = Array<UInt8>(file.length, repeat: 0)
        var offset: Int64 = 0
        while (offset < result.size) {
            let count = file.readAt(result[offset..], offset)
            if (count <= 0) { throw ApiError(503, "图片读取中断") }
            offset += count
        }
        return result
    }
    throw ApiError(503, "图片暂时不可用")
}

func algorithmImage(result: JsonObject): Array<UInt8> {
    let data = fromBase64String(jsonText(result, "image_base64")).getOrThrow()
    if (data.isEmpty() || data.size > 64 * 1024 * 1024 || sha256(data) != jsonText(result, "sha256")) {
        throw ApiError(503, "算法图片校验失败")
    }
    return data
}
