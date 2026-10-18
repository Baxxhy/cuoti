package zhiwei

import std.collection.*
import stdx.net.http.*

func headerParameters(value: String): HashMap<String, String> {
    let result = HashMap<String, String>()
    let parts = ArrayList<String>()
    var current = ArrayList<UInt8>()
    var quoted = false
    var escaped = false
    for (byte in value.toArray()) {
        if (escaped) { current.add(byte); escaped = false }
        else if (quoted && byte == 92) { escaped = true }
        else if (byte == 34) { quoted = !quoted }
        else if (!quoted && byte == 59) { parts.add(String.fromUtf8(current.toArray()).trimAscii()); current = ArrayList<UInt8>() }
        else { current.add(byte) }
    }
    if (quoted || escaped) { throw ApiError(422, "上传头格式不正确") }
    parts.add(String.fromUtf8(current.toArray()).trimAscii())
    result.add("", parts[0].toAsciiLower())
    for (index in 1..parts.size) {
        let pair = parts[index].split("=", 2)
        if (pair.size == 2) { result.add(pair[0].trimAscii().toAsciiLower(), pair[1].trimAscii()) }
    }
    return result
}

func bytesMatch(data: Array<UInt8>, needle: Array<UInt8>, start: Int64): Bool {
    if (start < 0 || start + needle.size > data.size) { return false }
    for (i in 0..needle.size) { if (data[start + i] != needle[i]) { return false } }
    return true
}

// KMP keeps adversarial, repeated boundary prefixes linear in the upload size.
func findBytes(data: Array<UInt8>, needle: Array<UInt8>, start: Int64): Int64 {
    let prefix = Array<Int64>(needle.size, repeat: 0)
    var matched: Int64 = 0
    for (i in 1..needle.size) {
        while (matched > 0 && needle[i] != needle[matched]) { matched = prefix[matched - 1] }
        if (needle[i] == needle[matched]) { matched++ }
        prefix[i] = matched
    }
    matched = 0
    for (i in start..data.size) {
        while (matched > 0 && data[i] != needle[matched]) { matched = prefix[matched - 1] }
        if (data[i] == needle[matched]) { matched++ }
        if (matched == needle.size) { return i - needle.size + 1 }
    }
    return -1
}

class ImageUpload {
    let bytes: Array<UInt8>
    let filename: String
    let fields: HashMap<String, String>
    let deferred: Bool
    init(bytes: Array<UInt8>, filename: String, deferred: Bool, fields: HashMap<String, String>) { this.fields = fields; this.bytes = bytes; this.filename = filename; this.deferred = deferred }
}

func readImageUpload(context: HttpContext, audio!: Bool=false): ImageUpload {
    let contentType = headerParameters(context.request.headers.getFirst("Content-Type") ?? "")
    if (contentType[""] != "multipart/form-data") { throw ApiError(422, "请选择上传图片") }
    let boundary = contentType.get("boundary") ?? ""
    if (boundary.isEmpty() || boundary.size > 70 || boundary.contains("\r") || boundary.contains("\n")) { throw ApiError(422, "上传分隔符无效") }
    let maxBytes: Int64 = 15 * 1024 * 1024 + 65536
    let buffer = Array<UInt8>(maxBytes + 1, repeat: 0)
    var length: Int64 = 0
    while (true) {
        let count = context.request.body.read(buffer[length..])
        if (count == 0) { break }
        length += count
        if (length > maxBytes) { throw ApiError(413, "图片不能超过 15 MB") }
    }
    let data = buffer[..length]
    let initial = ("--" + boundary + "\r\n").toArray()
    let delimiter = ("\r\n--" + boundary).toArray()
    let newline = "\r\n".toArray()
    let closing = "--".toArray()
    if (!bytesMatch(data, initial, 0)) { throw ApiError(422, "上传内容格式不正确") }
    var offset = initial.size
    var file: Option<Array<UInt8>> = None
    var filename = "上传错题"
    let fields = HashMap<String, String>()
    var deferred = false
    var ended = false
    var partCount: Int64 = 0
    while (!ended) {
        partCount++
        if (partCount > 32) { throw ApiError(422, "上传字段过多") }
        let endHeaders = findBytes(data, "\r\n\r\n".toArray(), offset)
        if (endHeaders < offset || endHeaders - offset > 8192) { throw ApiError(422, "上传头无效") }
        let headers = HashMap<String, String>()
        try {
            for (line in String.fromUtf8(data[offset..endHeaders]).split("\r\n")) {
                let pair = line.split(":", 2)
                if (pair.size != 2) { throw ApiError(422, "上传头无效") }
                headers.add(pair[0].trimAscii().toAsciiLower(), pair[1].trimAscii())
            }
        } catch (_: Exception) { throw ApiError(422, "上传头无效") }
        let disposition = headerParameters(headers.get("content-disposition") ?? "")
        if (disposition[""] != "form-data") { throw ApiError(422, "上传字段无效") }
        let start = endHeaders + 4
        var end = findBytes(data, delimiter, start)
        while (end >= 0 && !bytesMatch(data, newline, end + delimiter.size) && !bytesMatch(data, closing, end + delimiter.size)) {
            end = findBytes(data, delimiter, end + 1)
        }
        if (end < 0) { throw ApiError(422, "上传内容不完整") }
        let value = data[start..end]
        let name = disposition.get("name") ?? ""
        if (name == "file") {
            if (file.isSome() || !disposition.contains("filename")) { throw ApiError(422, "请上传一张图片") }
            if (value.isEmpty()) { if (audio) { throw ApiError(400,"音频文件为空") }; throw ApiError(422, "图片为空，请重新选择图片") }
            if (value.size > 15 * 1024 * 1024) { throw ApiError(413, "图片不能超过 15 MB") }
            file = Some(value)
            filename = disposition["filename"]
            if (filename.isEmpty()) { filename = "上传错题" }
            if (runeCount(filename) > 255) { throw ApiError(422, "文件名称过长") }
        } else {
            if (value.size > 4096) { throw ApiError(422, "上传字段过长") }
            try { fields.add(name, String.fromUtf8(value)) } catch (_: Exception) { throw ApiError(422,"上传字段无效") }
            if (name == "defer_processing") {
                try {
                    let text = String.fromUtf8(value).toAsciiLower()
                    if (text == "true" || text == "1" || text == "on" || text == "yes" || text == "t" || text == "y") { deferred = true }
                    else if (text == "false" || text == "0" || text == "off" || text == "no" || text == "f" || text == "n" || text.isEmpty()) { deferred = false }
                    else { throw ApiError(422, "处理方式无效") }
                } catch (_: Exception) { throw ApiError(422, "处理方式无效") }
            }
        }
        offset = end + delimiter.size
        if (bytesMatch(data, closing, offset)) { ended = true }
        else { offset += 2 }
    }
    if (let Some(bytes) <- file) { return ImageUpload(bytes, filename, deferred, fields) }
    throw ApiError(422, "缺少图片")
}
