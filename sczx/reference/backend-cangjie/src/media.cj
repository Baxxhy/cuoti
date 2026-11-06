package zhiwei

import std.convert.*
import std.env.*
import std.io.*
import stdx.encoding.hex.*
import stdx.encoding.json.*
import stdx.net.http.*

foreign {
    func zw_media_open(root: CString, path: CString): Int32
    func zw_media_stat(fd: Int32, field: Int32): Int64
    func zw_media_read(fd: Int32, output: CPointer<UInt8>, capacity: UInt64, offset: Int64): Int64
    func zw_media_close(fd: Int32): Unit
}

// SDK 1.0.5 checks a known empty body's size against Content-Length even for HEAD.
// An unknown-length empty stream lets HEAD advertise the actual resource length.
class HeadOnlyBody <: InputStream {
    public func read(_: Array<UInt8>): Int64 { 0 }
}

class MediaFile <: Resource {
    var descriptor: Int32 = -1
    public let length: Int64
    public let etag: String
    init(root: String, path: String) {
        if (root.contains("\u{0}") || path.contains("\u{0}") || path.contains("\\")) { throw ApiError(404, "资源不存在") }
        try (nativeRoot = NativeString(root), nativePath = NativeString(path)) {
            descriptor = unsafe { zw_media_open(nativeRoot.value, nativePath.value) }
        }
        if (descriptor < 0) { throw ApiError(404, "资源不存在") }
        length = unsafe { zw_media_stat(descriptor, 0) }
        let modified = unsafe { zw_media_stat(descriptor, 1) }
        let inode = unsafe { zw_media_stat(descriptor, 2) }
        if (length < 0) { unsafe { zw_media_close(descriptor) }; descriptor = -1; throw ApiError(404, "资源不存在") }
        etag = try { "\"" + toHexString(hmac256("media-etag-v1", "${path}:${length}:${modified}:${inode}")).toAsciiLower() + "\"" }
            catch (error: Exception) { unsafe { zw_media_close(descriptor) }; descriptor = -1; throw error }
    }
    public func isClosed(): Bool { descriptor < 0 }
    public func close(): Unit {
        if (descriptor >= 0) { unsafe { zw_media_close(descriptor) }; descriptor = -1 }
    }
    public func readAt(buffer: Array<UInt8>, offset: Int64): Int64 {
        if (isClosed()) { throw IllegalStateException("文件已关闭") }
        unsafe {
            let raw = acquireArrayRawData(buffer)
            try { return zw_media_read(descriptor, raw.pointer, UInt64(buffer.size), offset) }
            finally { releaseArrayRawData(raw) }
        }
    }
}

func mediaContentType(path: String): String {
    let name = path.toAsciiLower()
    for ((suffix, kind) in [(".png", "image/png"), (".jpg", "image/jpeg"), (".jpeg", "image/jpeg"),
        (".webp", "image/webp"), (".bmp", "image/bmp"), (".tif", "image/tiff"), (".gif", "image/gif"), (".svg", "image/svg+xml"),
        (".mp3", "audio/mpeg"), (".wav", "audio/wav"), (".webm", "audio/webm"), (".m4a", "audio/mp4"), (".ogg", "audio/ogg"), (".mp4", "video/mp4"),
        (".pdf", "application/pdf"), (".docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        (".zip", "application/zip"), (".json", "application/json"), (".txt", "text/plain; charset=utf-8")]) {
        if (name.endsWith(suffix)) { return kind }
    }
    return "application/octet-stream"
}

func mediaRange(header: String, length: Int64): (Int64, Int64) {
    try {
        if (!header.startsWith("bytes=")) { throw ApiError(416, "范围无效") }
        let parts = header[6..].split("-", 2)
        if (parts.size != 2 || length == 0) { throw ApiError(416, "范围无效") }
        if (parts[0].isEmpty()) {
            let suffix = Int64.parse(parts[1])
            if (suffix <= 0) { throw ApiError(416, "范围无效") }
            let count = if (suffix > length) { length } else { suffix }
            return (length - count, count)
        }
        let start = Int64.parse(parts[0])
        let requestedEnd = if (parts[1].isEmpty()) { length - 1 } else { Int64.parse(parts[1]) }
        if (start < 0 || start >= length || requestedEnd < start) { throw ApiError(416, "范围无效") }
        let end = if (requestedEnd >= length) { length - 1 } else { requestedEnd }
        return (start, end - start + 1)
    } catch (_: Exception) { throw ApiError(416, "范围无效") }
}

public func serveMedia(context: HttpContext, accounts: Accounts, storageRoot!: Option<String> = None, storagePath!: Option<String> = None): Unit {
    var started = false
    try {
        let method = context.request.method
        if (method != "GET" && method != "HEAD") {
            context.responseBuilder.header("Allow", "GET, HEAD")
            throw ApiError(405, "请求方法不支持")
        }
        if (!accounts.validMedia(context)) { throw ApiError(403, "资源链接已失效，请返回页面刷新") }
        let path = storagePath ?? context.request.url.path[1..]
        let root = storageRoot ?? (getVariable("CANGJIE_MEDIA_ROOT") ?? "media")
        try (file = MediaFile(root, path)) {
            context.responseBuilder.header("ETag", file.etag).header("Accept-Ranges", "bytes")
                .header("Cache-Control", "private, max-age=0, must-revalidate")
                .header("X-Content-Type-Options", "nosniff")
                .header("Content-Type", mediaContentType(path))
            for (tag in (context.request.headers.getFirst("If-None-Match") ?? "").split(",")) {
                let clean = tag.trimAscii()
                if (clean == "*" || clean == file.etag || clean == "W/" + file.etag) {
                    context.responseBuilder.status(304).body("")
                    return
                }
            }
            if (method == "HEAD") {
                context.responseBuilder.header("Content-Length", file.length.toString()).body(HeadOnlyBody())
                return
            }
            var offset: Int64 = 0
            var remaining = file.length
            let range = context.request.headers.getFirst("Range") ?? ""
            let ifRange = context.request.headers.getFirst("If-Range") ?? file.etag
            // A server may ignore multipart ranges; respond with the full resource.
            if (!range.isEmpty() && !range.contains(",") && ifRange == file.etag) {
                try {
                    let (start, count) = mediaRange(range, file.length)
                    offset = start
                    remaining = count
                    context.responseBuilder.status(206).header("Content-Range", "bytes ${start}-${start + count - 1}/${file.length}")
                } catch (error: ApiError) {
                    context.responseBuilder.header("Content-Range", "bytes */${file.length}")
                    throw error
                }
            }
            context.responseBuilder.header("Transfer-Encoding", "chunked")
            let writer = HttpResponseWriter(context)
            while (remaining > 0) {
                let capacity = if (remaining > 65536) { 65536 } else { remaining }
                let buffer = Array<UInt8>(capacity, repeat: 0)
                let count = file.readAt(buffer, offset)
                if (count <= 0) { throw IllegalStateException("文件读取中断") }
                started = true
                writer.write(buffer[..count])
                offset += count
                remaining -= count
            }
        }
    } catch (error: ApiError) {
        if (started) { throw error }
        let result = JsonObject(); result.put("detail", JsonString(error.message))
        jsonResponse(context, result, status: error.status)
    } catch (error: Exception) {
        if (started) { throw error }
        let result = JsonObject(); result.put("detail", JsonString("资源暂时不可用"))
        jsonResponse(context, result, status: 500)
    }
}
